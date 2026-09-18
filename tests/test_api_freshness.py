import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from bin.redis_keys import mediamtx_started_key, mediamtx_version_key, stream_snapshot_freshness_key
from bin.redis_store import RedisStore


class FakeRedis:
    def __init__(self, values):
        self.values = values

    def get(self, key):
        return self.values.get(key)


class ApiFreshnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        redis_module = types.ModuleType("redis")
        redis_module.Redis = object
        fastapi_module = types.ModuleType("fastapi")

        class FakeFastAPI:
            def __init__(self, *args, **kwargs):
                pass

            def mount(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                return lambda function: function

        class FakeJSONResponse:
            def __init__(self, content):
                self.body = json.dumps(content).encode()

        fastapi_module.FastAPI = FakeFastAPI
        responses_module = types.ModuleType("fastapi.responses")
        responses_module.JSONResponse = FakeJSONResponse
        responses_module.FileResponse = object
        staticfiles_module = types.ModuleType("fastapi.staticfiles")
        staticfiles_module.StaticFiles = lambda *args, **kwargs: object()
        with mock.patch.dict(
            sys.modules,
            {
                "redis": redis_module,
                "fastapi": fastapi_module,
                "fastapi.responses": responses_module,
                "fastapi.staticfiles": staticfiles_module,
            },
        ):
            from bin import monitoring_api
        cls.api = monitoring_api

    def test_api_exposes_collector_timestamp_next_to_unchanged_streams(self):
        streams = [{"name": "path-x", "readers": []}]
        values = {
            self.api.REDIS_KEY: json.dumps(streams),
            stream_snapshot_freshness_key(self.api.REDIS_KEY): json.dumps(1234.5),
            self.api.SYSTEM_REDIS_KEY: json.dumps({}),
        }
        self.api.snapshot_store = RedisStore(FakeRedis(values))

        response = self.api.get_streams()
        payload = json.loads(response.body)

        self.assertEqual(payload["streams"], streams)
        self.assertEqual(payload["collected_at"], 1234.5)

    def test_api_exposes_only_browser_endpoint(self):
        self.api.snapshot_store = RedisStore(FakeRedis({}))
        with mock.patch.object(
            self.api, "preview_base_url", "https://preview.example:9443"
        ), mock.patch.dict(self.api.config, {
            "api_base_url": "http://internal.example:9998",
        }):
            payload = json.loads(self.api.get_streams().body)
        self.assertEqual(payload["webrtc_base_url"], "https://preview.example:9443")
        self.assertNotIn("api_base_url", payload)

    def test_configured_preview_base_is_used_without_asking_mediamtx(self):
        def fail(*_args, **_kwargs):
            raise AssertionError("MediaMTX darf nicht befragt werden.")

        with mock.patch.object(self.api, "derive_preview_base_url", fail):
            resolved = self.api.resolve_preview_base_url({
                "webrtc_base_url": "https://preview.example:9443",
                "api_base_url": "http://127.0.0.1:9997",
            })
        self.assertEqual(resolved, "https://preview.example:9443")

    def test_empty_preview_base_is_derived_from_the_mediamtx_listener(self):
        class FakeClient:
            def get_json(self, endpoint):
                assert endpoint == "/v3/config/global/get"
                return {
                    "webrtc": True,
                    "webrtcAddress": ":8889",
                    "webrtcEncryption": False,
                }

        with mock.patch.object(
            self.api, "primary_host_address", lambda: "10.0.0.5"
        ):
            derived = self.api.derive_preview_base_url(
                "http://127.0.0.1:9997", client=FakeClient()
            )
        self.assertEqual(derived, "http://10.0.0.5:8889")

    def test_disabled_webrtc_yields_no_preview_base(self):
        class FakeClient:
            def get_json(self, _endpoint):
                return {"webrtc": False, "webrtcAddress": ":8889"}

        derived = self.api.derive_preview_base_url(
            "http://127.0.0.1:9997", client=FakeClient()
        )
        self.assertEqual(derived, "")

    def test_unreachable_mediamtx_reports_instead_of_failing_the_service(self):
        def unreachable(*_args, **_kwargs):
            raise self.api.MediaMTXError("keine Verbindung")

        with mock.patch.object(
            self.api, "derive_preview_base_url", unreachable
        ), self.assertLogs(level="ERROR"):
            resolved = self.api.resolve_preview_base_url({
                "webrtc_base_url": "",
                "api_base_url": "http://127.0.0.1:9997",
            })
        self.assertEqual(resolved, "")

    def test_api_exposes_mediamtx_version_without_streams(self):
        values = {
            self.api.REDIS_KEY: json.dumps([]),
            mediamtx_version_key(self.api.REDIS_KEY): json.dumps("1.21.0"),
            mediamtx_started_key(self.api.REDIS_KEY): json.dumps("2026-09-15T10:00:00Z"),
            self.api.SYSTEM_REDIS_KEY: json.dumps({}),
        }
        self.api.snapshot_store = RedisStore(FakeRedis(values))

        response = self.api.get_streams()
        payload = json.loads(response.body)

        self.assertEqual(payload["streams"], [])
        self.assertEqual(payload["mediamtx_version"], "1.21.0")
        self.assertEqual(payload["mediamtx_started"], "2026-09-15T10:00:00Z")

    def test_api_preserves_system_hostname_and_ipv4_addresses(self):
        systeminfo = {
            "host": "mediamtx18",
            "server_ips": ["192.168.95.18", "172.16.90.18"],
        }
        values = {
            self.api.REDIS_KEY: json.dumps([]),
            self.api.SYSTEM_REDIS_KEY: json.dumps(systeminfo),
        }
        self.api.snapshot_store = RedisStore(FakeRedis(values))

        response = self.api.get_streams()
        payload = json.loads(response.body)

        self.assertEqual(payload["systeminfo"], systeminfo)

    def test_monitor_version_is_read_without_trailing_newline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            version_file = Path(temp_dir) / "VERSION"
            version_file.write_text("0.8.0\n", encoding="utf-8")

            self.assertEqual(self.api.load_monitor_version(version_file), "0.8.0")

    def test_missing_or_unreadable_version_does_not_fail(self):
        missing_file = Path("/missing/monitor/VERSION")
        self.assertIsNone(self.api.load_monitor_version(missing_file))
        with mock.patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertIsNone(self.api.load_monitor_version(Path("VERSION")))

    def test_api_exposes_monitor_version(self):
        values = {
            self.api.REDIS_KEY: json.dumps([]),
            self.api.SYSTEM_REDIS_KEY: json.dumps({}),
        }
        self.api.snapshot_store = RedisStore(FakeRedis(values))

        with mock.patch.object(self.api, "monitor_version", "0.8.0"):
            response = self.api.get_streams()

        payload = json.loads(response.body)
        self.assertEqual(payload["monitor_version"], "0.8.0")

    def test_api_remains_available_without_monitor_version(self):
        streams = [{"name": "path-x", "readers": []}]
        values = {
            self.api.REDIS_KEY: json.dumps(streams),
            self.api.SYSTEM_REDIS_KEY: json.dumps({}),
        }
        self.api.snapshot_store = RedisStore(FakeRedis(values))

        with mock.patch.object(self.api, "monitor_version", None):
            response = self.api.get_streams()

        payload = json.loads(response.body)
        self.assertIsNone(payload["monitor_version"])
        self.assertEqual(payload["streams"], streams)

    def test_explicit_invalid_namespace_is_not_silently_defaulted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "collector.yaml"
            config_path.write_text(
                "redis:\n  namespace: '   '\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "redis.namespace"):
                self.api.load_runtime_config(config_path)


if __name__ == "__main__":
    unittest.main()
