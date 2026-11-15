import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

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

    def test_redis_outage_skips_one_snapshot_and_the_next_write_recovers(self):
        class OutageRedis(FakeRedis):
            down = False

            def set(self, key, value):
                if self.down:
                    raise ConnectionError("Connection refused")
                self.values[key] = value

        redis_client = OutageRedis()
        system_monitor.snapshot_store = RedisStore(redis_client)
        usage = SimpleNamespace(_asdict=lambda: {"total": 1, "used": 0})
        fake_psutil = SimpleNamespace(
            cpu_percent=lambda interval: 5.0,
            virtual_memory=lambda: usage,
            swap_memory=lambda: usage,
            disk_usage=lambda path: usage,
            getloadavg=lambda: (0.0, 0.0, 0.0),
        )
        with (
            mock.patch.multiple(
                system_monitor,
                psutil=fake_psutil,
                get_filtered_net_io=lambda: {"bytes_recv": 0, "bytes_sent": 0},
                get_server_ips=lambda: [],
                get_cpu_breakdown=lambda: {},
                get_temperatures=lambda: {},
                calculate_network_bitrate=lambda net_io, now: {
                    "net_mbit_rx": None, "net_mbit_tx": None,
                },
            ),
            mock.patch.object(Path, "write_text"),
        ):
            redis_client.down = True
            with self.assertLogs(level="ERROR") as logs:
                system_monitor.collect_and_store()
            self.assertIn("Connection refused", logs.output[0])
            self.assertNotIn(system_monitor.REDIS_KEY, redis_client.values)

            redis_client.down = False
            system_monitor.collect_and_store()

        stored = json.loads(redis_client.values[system_monitor.REDIS_KEY])
        self.assertEqual(stored["cpu_percent"], 5.0)


if __name__ == "__main__":
    unittest.main()
