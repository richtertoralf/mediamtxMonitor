"""Read-only reuse checks against fake API responses and isolated shell preflight."""
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import check_reuse_config as reuse

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = {"name": "~^__preview__/(.+)$", "runOnDemand": "ffmpeg ..."}


class ConfigChecks(unittest.TestCase):
    def check(self, responses, base="https://media.example:9998"):
        with patch.object(reuse, "urlopen", side_effect=[
            io.BytesIO(json.dumps(value).encode()) for value in responses
        ]) as request:
            reuse.check_config(base)
            return [call.args[0] for call in request.call_args_list]

    def test_effective_config_and_pagination(self):
        urls = self.check([
            {"webrtc": True, "webrtcAddress": ":8899", "webrtcEncryption": True},
            {"pageCount": 2, "items": [{"name": "foreign"}]},
            {"pageCount": 2, "items": [PREVIEW]},
        ])
        self.assertEqual(urls, ["https://media.example:9998" + suffix for suffix in [
            "/v3/config/global/get", "/v3/config/paths/list?page=0",
            "/v3/config/paths/list?page=1",
        ]])

    def test_missing_integration(self):
        for value in [False, None, "true"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check([{"webrtc": value}])
        for paths in [[], [{**PREVIEW, "runOnDemand": " "}]]:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                self.check([{"webrtc": True}, {"pageCount": 1, "items": paths}])

    def test_errors_do_not_expose_response_or_url_secrets(self):
        with patch.object(reuse, "urlopen", side_effect=OSError("private-token")):
            with self.assertRaises(ValueError) as error:
                reuse.check_config("https://media.example:9998")
            self.assertNotIn("private-token", str(error.exception))

    def test_url_validation(self):
        for url in ["http://localhost:9997", "https://media.example:9998/api", "http://[::1]:9998"]:
            reuse.validate_url(url)
        for url in ["ftp://host", "http://user:secret@host", "http://host?token=secret", "http://host:bad"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                reuse.validate_url(url)


class InstallerPreflight(unittest.TestCase):
    def run_preflight(self, config, runtime="1.21.0", reachable=True, port=9998, explicit=True, discovery_ok=True):
        source = (ROOT / "install.sh").read_text()
        version_function = source.split("version_is_at_least() {", 1)[1].split('\nversion_is_at_least "$MEDIAMTX_VERSION"', 1)[0]
        reader = source.split("read_runtime_version() {", 1)[1].split('\nif [ "${EUID', 1)[0]
        block = source.split('if [ "$INSTALL_MODE" = reuse ]; then', 1)[1].split('  existing_targets=(', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            config_file = directory / "mediamtx.yml"
            config_file.write_text(config)
            log = directory / "calls"
            binary = directory / "mediamtx"
            binary.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$CALL_LOG"\nif [ "$1" = --version ]; then echo v1.21.0; fi\n')
            binary.chmod(0o755)
            env = dict(os.environ, CALL_LOG=str(log), MEDIAMTX_CONFIG=str(config_file),
                       MEDIAMTX_BIN=str(binary), MEDIAMTX_API_URL=f"http://127.0.0.1:{port}" if explicit else "",
                       DISCOVERY_OK="true" if discovery_ok else "false", DISCOVERED_URL=f"http://127.0.0.1:{port}",
                       MEDIAMTX_WEBRTC_URL="https://preview.example:9443", PORTS_EXPLICIT="false",
                       MINIMUM_MEDIAMTX_VERSION="1.21.0", SCRIPT_DIR=str(ROOT))
            script = '''set -eu
fail() { echo "$*" >&2; exit 1; }
curl() { echo "curl ${@: -1}" >> "$CALL_LOG"; ''' + (
                "printf '%s' " + shlex.quote(json.dumps({"version": runtime, "started": "2026-09-15T10:00:00Z"}))
                if reachable else "return 7"
            ) + '''; }
python3() {
  if [[ "$1" == */check_reuse_config.py ]]; then
    echo "config-check ${*:2}" >> "$CALL_LOG"
    if [ "$2" = --discover-api ]; then
      [ "$DISCOVERY_OK" = true ] || return 1
      echo "$DISCOVERED_URL"
    fi
    return 0
  fi
  command python3 "$@"
}
version_is_at_least() {''' + version_function + '\nread_runtime_version() {' + reader + '\n' + block
            result = subprocess.run(["bash", "-c", script], env=env, text=True, capture_output=True)
            self.assertEqual(config_file.read_text(), config)
            return result, log.read_text()

    def test_yaml_spelling_is_irrelevant_to_preflight(self):
        for port in [9997, 9998]:
            for config in [
                'api: true\nwebrtc: true\npaths:\n  "~^__preview__/(.+)$": {}\n',
                "api: yes\nwebrtc: yes\npaths:\n  '~^__preview__/(.+)$': {}\n",
                'api : yes\nwebrtc : yes\npaths: {~^__preview__/(.+)$: {}}\n',
            ]:
                with self.subTest(port=port, config=config):
                    result, calls = self.run_preflight(config, port=port)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(f"curl http://127.0.0.1:{port}/v3/info", calls)
                    self.assertIn(f"config-check http://127.0.0.1:{port}", calls)
                    self.assertIn("--validate-conf=", calls)

    def test_unreachable_bootstrap_never_queries_config(self):
        result, calls = self.run_preflight("api: yes", reachable=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("konfigurierte MediaMTX-Control-API-Endpunkt", result.stderr)
        self.assertNotIn("config-check http", calls)
        self.assertNotIn("--validate-conf=", calls)

    def test_binary_runtime_mismatch_stops_before_config(self):
        result, calls = self.run_preflight("api: yes", runtime="1.20.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("kontrolliert neu gestartet", result.stderr)
        self.assertNotIn("config-check http", calls)

    def test_discovery_precedes_bootstrap_and_can_abort_it(self):
        result, calls = self.run_preflight("api: yes", explicit=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(calls.index("--discover-api"), calls.index("curl http"))
        result, calls = self.run_preflight("api: yes", explicit=False, discovery_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("curl http", calls)
        self.assertIn("API-Bootstrap abgebrochen", result.stderr)

    def test_newer_runtime_accepted(self):
        result, _ = self.run_preflight("api: yes", runtime="1.23.0")
        self.assertEqual(result.returncode, 0, result.stderr)


class FreshConfig(unittest.TestCase):
    def test_generated_ports_and_foreign_paths(self):
        source = (ROOT / "install.sh").read_text()
        code = source.split('from pathlib import Path\nimport re\nimport sys', 1)[1].split('\nPY', 1)[0]
        code = 'from pathlib import Path\nimport re\nimport sys' + code
        for api_port, webrtc_port in [(9997, 8889), (9998, 8899)]:
            with self.subTest(api_port=api_port), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                original = directory / "original.yml"
                output = directory / "output.yml"
                original.write_text('api: no\nrtsp: yes\nwebrtc: yes\napiAddress: :9997\napiEncryption: no\nwebrtcAddress: :8889\nwebrtcEncryption: no\npaths:\n  foreign:\n    source: publisher\n  all_others:\n')
                result = subprocess.run([sys.executable, "-c", code, str(original),
                    str(ROOT / "config/monitor-preview-path.yml"), str(output),
                    str(api_port), str(webrtc_port)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                import yaml
                config = yaml.safe_load(output.read_text())
                self.assertEqual(config["apiAddress"], f"127.0.0.1:{api_port}")
                self.assertEqual(config["webrtcAddress"], f":{webrtc_port}")
                self.assertFalse(config["apiEncryption"])
                self.assertEqual(config["paths"]["foreign"], {"source": "publisher"})


class YamlBootstrap(unittest.TestCase):
    def discover(self, text, *, environment=b"PATH=/usr/bin\0", command=None,
                 properties="MainPID=123\nEnvironmentFiles=\nPassEnvironment=\n"):
        command = command if command is not None else b"/usr/local/bin/mediamtx\0/example.yml\0"
        with patch.object(reuse.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, properties)), \
                patch.object(Path, "read_bytes", side_effect=[command, environment]), \
                patch.object(Path, "read_text", return_value=text):
            return reuse.discover_api_url("/example.yml", "/usr/local/bin/mediamtx")

    def test_yaml_boolean_spelling_and_configured_addresses(self):
        for boolean in ("true", "yes"):
            for address, expected in [
                (":9997", "http://127.0.0.1:9997"),
                ("0.0.0.0:9998", "http://127.0.0.1:9998"),
                ("127.0.0.2:9998", "http://127.0.0.2:9998"),
                ("[::]:9998", "http://[::1]:9998"),
            ]:
                with self.subTest(boolean=boolean, address=address):
                    self.assertEqual(self.discover(f'api: {boolean}\napiAddress: "{address}"'), expected)
        self.assertEqual(self.discover('api: yes\napiAddress: "media.example:9443"\napiEncryption: yes'),
                         "https://media.example:9443")

    def test_only_bootstrap_fields_are_interpreted(self):
        self.assertEqual(self.discover('api: yes\nwebrtc: no\npaths: null'), "http://127.0.0.1:9997")

    def test_overrides_and_ambiguous_service_require_explicit_endpoint(self):
        for name in ("MTX_API", "MTX_APIADDRESS", "MTX_APIENCRYPTION"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "ausdrücklich"):
                self.discover("api: yes", environment=f"{name}=private-value\0".encode())
        for overrides in [
            {"command": b"/wrapper\0/example.yml\0"},
            {"command": b"/usr/local/bin/mediamtx\0/other.yml\0"},
            {"properties": "MainPID=123\nEnvironmentFiles=/private.env\n"},
            {"properties": "MainPID=123\nPassEnvironment=MTX_APIADDRESS\n"},
            {"properties": "MainPID=0\n"},
        ]:
            with self.subTest(overrides=overrides), self.assertRaisesRegex(ValueError, "ausdrücklich"):
                self.discover("api: yes", **overrides)

    def test_invalid_config_errors_do_not_echo_contents(self):
        for text in ['api: false', 'api: "true"', 'api: yes\napiAddress: bad',
                     'api: yes\napiEncryption: "false"', 'secret: [private-value']:
            with self.subTest(text=text), self.assertRaises(ValueError) as error:
                self.discover(text)
            self.assertNotIn("private-value", str(error.exception))

    def test_missing_system_pyyaml_explains_dependency_before_io(self):
        import builtins
        original = builtins.__import__
        def without_yaml(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=without_yaml), \
                patch.object(reuse.subprocess, "run") as service:
            with self.assertRaisesRegex(ValueError, "python3-yaml"):
                reuse.discover_api_url("/example.yml", "/usr/local/bin/mediamtx")
            service.assert_not_called()
