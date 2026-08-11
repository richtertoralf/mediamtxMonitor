import json
import unittest

from bin import mediamtx_systeminfo
from bin.redis_store import RedisStore


class FakeRedis:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key):
        return self.values.get(key)


class SystemSnapshotStoreTests(unittest.TestCase):
    def setUp(self):
        self.original_store = mediamtx_systeminfo.snapshot_store

    def tearDown(self):
        mediamtx_systeminfo.snapshot_store = self.original_store

    def test_get_system_info_reads_through_snapshot_store(self):
        snapshot = {
            "cpu_percent": 20.5,
            "memory": {"total": 1000, "used": 400},
            "swap": {"total": 500, "used": 50},
            "disk": {"total": 2000, "used": 750},
            "loadavg": [0.1, 0.2, 0.3],
            "net_mbit_rx": 1.25,
            "net_mbit_tx": 2.5,
            "temperature": {},
        }
        redis_client = FakeRedis({
            mediamtx_systeminfo.REDIS_KEY: json.dumps(snapshot),
        })
        mediamtx_systeminfo.snapshot_store = RedisStore(redis_client)

        result = mediamtx_systeminfo.get_system_info()

        self.assertEqual(result["cpu_percent"], 20.5)
        self.assertEqual(result["memory_total_bytes"], 1000)
        self.assertEqual(result["net_mbit_tx"], 2.5)

    def test_missing_system_snapshot_keeps_empty_fallback(self):
        mediamtx_systeminfo.snapshot_store = RedisStore(FakeRedis())

        self.assertEqual(mediamtx_systeminfo.get_system_info(), {})


if __name__ == "__main__":
    unittest.main()
