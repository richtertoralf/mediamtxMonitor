"""Read-only configuration check (issue #14)."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

from bin.config_check import check_config, mask


ROOT = Path(__file__).resolve().parents[1]


class ConfigCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def write(self, text):
        path = Path(self.directory.name, "collector.yaml")
        path.write_text(text, encoding="utf-8")
        return path

    def report(self, text):
        lines, code = check_config(self.write(text), explicit=True)
        return "\n".join(lines), code

    def test_shipped_template_is_valid_and_fully_from_file(self):
        lines, code = check_config(ROOT / "config/collector.yaml", explicit=True)
        report = "\n".join(lines)
        self.assertEqual(code, 0, report)
        self.assertIn("Ergebnis: 0 Fehler, 0 Warnungen", report)
        self.assertIn("(ausdrücklich angegeben)", report)
        self.assertIn("[collector] – gelesen von mediamtx-collector.service", report)

    def test_missing_optional_values_show_compatible_defaults(self):
        report, code = self.report("collector:\n  interval_seconds: 2\n")
        self.assertEqual(code, 0, report)
        self.assertIn("interval_seconds = 2  (Datei)", report)
        self.assertIn("static_source_refresh_seconds = 5  (Default)", report)
        self.assertIn('api_base_url = "http://localhost:9997"  (Default;', report)

    def test_explicit_missing_file_is_an_error(self):
        lines, code = check_config(Path(self.directory.name, "fehlt.yaml"), explicit=True)
        report = "\n".join(lines)
        self.assertEqual(code, 1)
        self.assertIn("Datei fehlt oder ist nicht lesbar", report)
        self.assertIn("(ausdrücklich angegeben)", report)

    def test_unknown_duplicate_type_and_value_errors_are_named(self):
        report, code = self.report(
            "redis:\n  port: 1\n  port: 6380\n  extra: 1\n"
            "system_monitor: []\n"
            "node:\n  id: 'a b'\n"
            "collector:\n  interval_seconds: 0\n  ignore_path_prefixes: x\n"
            "bitrate:\n  ignore_loopback: 'false'\n  smooth_alpha: 2\n"
            "api_server:\n  listen_port: 70000\n"
            "logging:\n  level: LOUD\n"
            "frontend:\n  snapshot_refresh_ms: '1000'\n"
            "unbekannt: 1\n"
        )
        self.assertEqual(code, 1)
        for expected in (
            "Warnung: Unbekannter Schlüssel 'unbekannt' wird ignoriert.",
            "Warnung: Unbekannter Schlüssel redis.extra wird ignoriert.",
            "Fehler: Doppelter Schlüssel 'port' in Zeile 3",
            "Fehler: Abschnitt system_monitor muss ein Mapping sein",
            "Fehler: node: node.id darf nur Buchstaben",
            "Fehler: collector.interval_seconds muss größer als 0 sein.",
            "Fehler: collector.ignore_path_prefixes muss eine Liste",
            "Fehler: bitrate.ignore_loopback muss true oder false sein",
            "Fehler: bitrate.smooth_alpha muss größer als 0 und höchstens 1 sein.",
            "Fehler: api_server.listen_port muss ein Port zwischen 1 und 65535 sein.",
            "Fehler: logging.level muss einer von",
            "Fehler: frontend.snapshot_refresh_ms muss eine ganze Zahl sein",
        ):
            self.assertIn(expected, report)

    def test_secret_values_are_masked(self):
        report, _ = self.report(
            "api_base_url: 'http://admin:geheim@127.0.0.1:9997'\n"
            "webrtc_base_url: ''\n"
        )
        self.assertNotIn("geheim", report)
        self.assertNotIn("admin", report)
        self.assertIn('"http://***@127.0.0.1:9997"', report)
        self.assertEqual(mask("api_token", "abc"), "***")
        self.assertEqual(mask("host", "localhost"), "localhost")

    def test_invalid_preview_url_with_credentials_is_an_error(self):
        report, code = self.report("webrtc_base_url: 'http://u:p@host:8889'\n")
        self.assertEqual(code, 1)
        self.assertIn("webrtc_base_url darf keine Zugangsdaten enthalten.", report)

    def test_check_has_no_side_effects_and_needs_no_network_or_redis(self):
        path = self.write("redis:\n  host: redis.invalid\n")
        before = sorted(os.listdir(self.directory.name))
        probe = (
            "import socket, sys\n"
            "sys.modules['redis'] = None\n"
            "def blocked(*args, **kwargs):\n"
            "    raise AssertionError('network used')\n"
            "socket.socket = blocked\n"
            "socket.create_connection = blocked\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import config_check\n"
            "sys.exit(config_check.main([sys.argv[2]]))\n"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-c", probe, str(ROOT / "bin"), str(path)],
            cwd=self.directory.name, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('host = "redis.invalid"  (Datei)', result.stdout)
        self.assertEqual(sorted(os.listdir(self.directory.name)), before)
        self.assertEqual(path.read_text(encoding="utf-8"), "redis:\n  host: redis.invalid\n")


class CheckConfigCliTests(unittest.TestCase):
    def test_cli_runs_the_check_with_the_installed_python(self):
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory)
            (install / "venv/bin").mkdir(parents=True)
            (install / "venv/bin/python").symlink_to(sys.executable)
            (install / "bin").symlink_to(ROOT / "bin")
            (install / "config").mkdir()
            (install / "config/collector.yaml").write_text("node:\n  id: n1\n", encoding="utf-8")
            env = dict(os.environ, MEDIAMTX_MONITOR_INSTALL_DIR=str(install))
            run = lambda *args: subprocess.run(
                ["bash", str(ROOT / "mediamtx-monitor"), *args],
                env=env, capture_output=True, text=True, check=False,
            )
            standard = run("--check-config")
            self.assertEqual(standard.returncode, 0, standard.stderr)
            self.assertIn("(Standardpfad)", standard.stdout)
            self.assertIn('id = "n1"  (Datei)', standard.stdout)

            missing = run("--check-config", str(install / "fehlt.yaml"))
            self.assertEqual(missing.returncode, 1)
            self.assertIn("(ausdrücklich angegeben)", missing.stdout)


if __name__ == "__main__":
    unittest.main()
