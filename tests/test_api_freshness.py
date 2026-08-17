import json
import sys
import types
import unittest
from unittest import mock

from bin.redis_keys import stream_snapshot_freshness_key
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


if __name__ == "__main__":
    unittest.main()
