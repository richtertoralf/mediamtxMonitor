"""Read-only operating status (mediamtx-monitor --status)."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bin.mediamtx_client import MediaMTXRequestError
from bin.monitor_status import Probes, build_status, dashboard_urls


ROOT = Path(__file__).resolve().parents[1]
NOW = 1_000_000.0


class ReadOnlyRedis:
    """Fake Redis that fails the test on any write."""

    def __init__(self, values):
        self.values = values
        self.calls = []

    def ping(self):
        self.calls.append("ping")
        return True

    def get(self, key):
        self.calls.append("get")
        return self.values.get(key)

    def __getattr__(self, name):
        raise AssertionError(f"Redis-Schreib- oder Fremdzugriff: {name}")


def probes(redis=None, services=None, reachable=True, mediamtx="v1.21.3", addresses=("192.0.2.10",)):
    def version(_url):
        if isinstance(mediamtx, Exception):
            raise mediamtx
        return mediamtx

    def client(_host, _port):
        if isinstance(redis, Exception):
            raise redis
        return redis

    return Probes(
        service_state=lambda unit: (services or {}).get(unit, "active"),
        addresses=lambda: list(addresses),
        http_reachable=lambda url: reachable,
        mediamtx_version=version,
        redis_client=client,
        hostname=lambda: "monitor-01",
        version=lambda: "0.8.7",
        now=lambda: NOW,
    )


def fresh_redis(stream_age=0.5, system_age=4.0):
    prefix = "mediamtx-monitor:node:local:"
    values = {}
    if stream_age is not None:
        values[prefix + "streams:latest:collected_at"] = json.dumps(NOW - stream_age)
    if system_age is not None:
        values[prefix + "system:latest"] = json.dumps({"timestamp": NOW - system_age})
    return ReadOnlyRedis(values)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def config(self, text="api_server:\n  listen_host: 0.0.0.0\n  listen_port: 8080\n"):
        path = Path(self.directory.name, "collector.yaml")
        path.write_text(text, encoding="utf-8")
        return path

    def status(self, path=None, **kwargs):
        report = build_status(path or self.config(), probes(**kwargs))
        return "\n".join(report.lines), report.hints

    def test_healthy_monitor_reports_ok_and_dashboard_urls(self):
        redis = fresh_redis()
        text, hints = self.status(redis=redis)
        self.assertEqual(hints, [], text)
        self.assertIn("MediaMTX Monitor 0.8.7 auf monitor-01", text)
        self.assertIn("lokal:          http://127.0.0.1:8080/  (erreichbar)", text)
        self.assertIn("mögliches Netz: http://192.0.2.10:8080/  (nicht geprüft;", text)
        self.assertNotIn("0.0.0.0:", text)
        self.assertIn("mediamtx-collector.service   active", text)
        self.assertIn("erreichbar, v1.21.3", text)
        self.assertIn("Streams:  vor 0.5 s (aktuell)", text)
        self.assertIn("System:   vor 4.0 s (aktuell)", text)
        self.assertIn("Ergebnis: OK", text)
        self.assertTrue(set(redis.calls) <= {"ping", "get"})

    def test_loopback_listener_offers_no_network_url(self):
        text, _ = self.status(
            self.config("api_server:\n  listen_host: 127.0.0.1\n  listen_port: 9090\n"),
            redis=fresh_redis(),
        )
        self.assertIn("lokal:          http://127.0.0.1:9090/", text)
        self.assertIn("mögliches Netz: keines (listen_host erlaubt nur lokalen Zugriff)", text)

    def test_wildcard_without_addresses_is_unknown(self):
        text, _ = self.status(redis=fresh_redis(), addresses=())
        self.assertIn("mögliches Netz: unbekannt (keine IPv4-Adresse ermittelt)", text)

    def test_problems_become_hints_and_unknown_values(self):
        text, hints = self.status(
            redis=fresh_redis(stream_age=60.0, system_age=None),
            services={"mediamtx-system.service": "inactive"},
            reachable=False,
            mediamtx=MediaMTXRequestError("refused"),
        )
        self.assertIn("mediamtx-system.service      inactive", text)
        self.assertIn("nicht erreichbar", text)
        self.assertIn("Streams:  vor 60.0 s (veraltet, Grenze 10 s)", text)
        self.assertIn("System:   unbekannt (noch keine Daten)", text)
        self.assertEqual(len(hints), 5, hints)
        self.assertIn("Ergebnis: 5 Hinweis(e)", text)

    def test_unreachable_redis_makes_data_age_not_checkable(self):
        text, hints = self.status(redis=ConnectionError("refused"))
        self.assertIn("Redis         localhost:6379  nicht erreichbar", text)
        self.assertIn("Streams:  nicht prüfbar", text)
        self.assertTrue(any("Redis nicht erreichbar" in hint for hint in hints))

    def test_missing_configuration_is_named_and_values_marked_as_defaults(self):
        text, hints = self.status(Path(self.directory.name, "fehlt.yaml"), redis=fresh_redis())
        self.assertIn("(nicht lesbar, angezeigt werden Defaults)", text)
        self.assertTrue(any("--check-config" in hint for hint in hints))

    def test_credentials_are_not_shown(self):
        text, _ = self.status(
            self.config("api_base_url: 'http://admin:geheim@127.0.0.1:9997'\n"),
            redis=fresh_redis(),
        )
        self.assertNotIn("geheim", text)
        self.assertIn("http://***@127.0.0.1:9997", text)

    def test_dashboard_urls_never_use_wildcards(self):
        for wildcard in ("0.0.0.0", "", "::"):
            local, network = dashboard_urls(wildcard, 8080, ["192.0.2.1"])
            self.assertEqual(local, ["http://127.0.0.1:8080/"])
            self.assertEqual(network, ["http://192.0.2.1:8080/"])
        self.assertEqual(dashboard_urls("192.0.2.5", 80, ["192.0.2.1"]),
                         ([], ["http://192.0.2.5:80/"]))
        self.assertEqual(dashboard_urls("::1", 80, []), (["http://[::1]:80/"], []))


class StatusCliTests(unittest.TestCase):
    def test_cli_runs_status_without_sudo_and_reports_unreachable_parts(self):
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory)
            (install / "venv/bin").mkdir(parents=True)
            (install / "venv/bin/python").symlink_to(sys.executable)
            (install / "bin").symlink_to(ROOT / "bin")
            (install / "VERSION").write_text("9.9.9\n", encoding="utf-8")
            (install / "config").mkdir()
            # Closed local ports: nothing on this host is contacted successfully.
            (install / "config/collector.yaml").write_text(
                "api_base_url: 'http://127.0.0.1:9'\nredis:\n  port: 9\n"
                "api_server:\n  listen_host: 127.0.0.1\n  listen_port: 9\n",
                encoding="utf-8",
            )
            fake_bin = install / "fake-bin"
            fake_bin.mkdir()
            systemctl = fake_bin / "systemctl"
            systemctl.write_text("#!/bin/sh\necho inactive\nexit 3\n", encoding="utf-8")
            systemctl.chmod(0o755)
            env = dict(os.environ, MEDIAMTX_MONITOR_INSTALL_DIR=str(install),
                       PATH=f"{fake_bin}:{os.environ['PATH']}")
            result = subprocess.run(
                ["bash", str(ROOT / "mediamtx-monitor"), "--status"],
                env=env, capture_output=True, text=True, check=False, timeout=60,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("MediaMTX Monitor 9.9.9", result.stdout)
        self.assertIn("mediamtx-api.service         inactive", result.stdout)
        self.assertIn("Ergebnis:", result.stdout)


if __name__ == "__main__":
    unittest.main()
