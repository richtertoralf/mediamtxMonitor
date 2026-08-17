import json
import unittest

from bin import system_monitor
from bin.redis_store import RedisStore


class FakeRedis:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key):
        return self.values.get(key)


class SystemSnapshotStoreTests(unittest.TestCase):
    def setUp(self):
        self.original_store = system_monitor.snapshot_store

    def tearDown(self):
        system_monitor.snapshot_store = self.original_store

    def test_get_system_info_reads_through_snapshot_store(self):
        snapshot = {
            "host": "mediamtx-02",
            "server_ips": [
                "159.69.199.209",
                "192.168.97.3",
                "172.16.90.17",
            ],
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
            system_monitor.REDIS_KEY: json.dumps(snapshot),
        })
        system_monitor.snapshot_store = RedisStore(redis_client)

        result = system_monitor.get_system_info()

        self.assertEqual(result["cpu_percent"], 20.5)
        self.assertEqual(result["host"], "mediamtx-02")
        self.assertEqual(result["server_ips"], snapshot["server_ips"])
        self.assertEqual(result["memory_total_bytes"], 1000)
        self.assertEqual(result["net_mbit_tx"], 2.5)

    def test_missing_system_snapshot_keeps_empty_fallback(self):
        system_monitor.snapshot_store = RedisStore(FakeRedis())

        self.assertEqual(system_monitor.get_system_info(), {})


if __name__ == "__main__":
    unittest.main()
