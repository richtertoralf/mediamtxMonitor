import json
import unittest
from pathlib import Path
from unittest import mock

from bin import mediamtx_collector
from bin.mediamtx_client import MediaMTXRequestError
from bin.redis_keys import stream_snapshot_freshness_key
from bin.redis_store import RedisStore
from tests.test_srt_health import FakeRedis


class LifecycleMediaMTXClient:
    def __init__(self, readers):
        self.readers = readers
        self.calls = []

    def build_url(self, endpoint):
        return f"http://localhost:9997{endpoint}"

    def get_json(self, endpoint, params=None):
        self.calls.append((endpoint, params))
        if endpoint == "/v3/info":
            return {"version": "1.20.0"}
        if endpoint == "/v3/paths/list":
            return {
                "items": [
                    {
                        "name": "path-x",
                        "source": {"type": "srtConn", "id": "publisher"},
                        "readers": [
                            {"type": "srtConn", "id": reader["id"]}
                            for reader in self.readers
                        ],
                    }
                ]
            }
        if endpoint == "/v3/srtconns/list":
            return {
                "items": [
                    {
                        "id": "publisher",
                        "remoteAddr": "192.0.2.1:9000",
                        "msRTT": 20,
                    },
                    *self.readers,
                ]
            }
        if endpoint == "/v3/paths/forward/list":
            return {"items": []}
        return {"items": []}


class FailingPathsClient(LifecycleMediaMTXClient):
    def get_json(self, endpoint, params=None):
        if endpoint == "/v3/paths/list":
            raise MediaMTXRequestError("paths unavailable")
        return super().get_json(endpoint, params=params)


class ConnectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        mediamtx_collector.r = self.redis
        mediamtx_collector.snapshot_store = RedisStore(self.redis)
        mediamtx_collector.reset_poll_cache()

    def collect(self, client, timestamp):
        mediamtx_collector.mediamtx_client = client
        with (
            mock.patch.object(Path, "write_text"),
            mock.patch.object(mediamtx_collector.time, "time", return_value=timestamp),
        ):
            metrics = mediamtx_collector.collect_and_store()
        snapshot = json.loads(self.redis.values[mediamtx_collector.REDIS_KEY])
        return snapshot, metrics

    @staticmethod
    def reader(reader_id, port):
        return {
            "id": reader_id,
            "remoteAddr": f"192.168.1.50:{port}",
            "msRTT": 30,
        }

    def test_reconnect_sequence_current_snapshot_follows_each_poll(self):
        client = LifecycleMediaMTXClient([])
        sequences = [
            [self.reader("UUID-A", 51001)],
            [],
            [self.reader("UUID-B", 51017)],
            [],
            [self.reader("UUID-C", 51023)],
        ]

        snapshots = []
        for offset, readers in enumerate(sequences):
            client.readers = readers
            snapshot, _metrics = self.collect(client, 1000.0 + offset)
            snapshots.append(snapshot)

        self.assertEqual(
            [[reader["id"] for reader in item[0]["readers"]] for item in snapshots],
            [["UUID-A"], [], ["UUID-B"], [], ["UUID-C"]],
        )
        self.assertTrue(all(len(snapshot) == 1 for snapshot in snapshots))
        self.assertIn("history:rd:path-x:srtConn:UUID-A", self.redis.sorted_sets)
        self.assertIn("history:rd:path-x:srtConn:UUID-B", self.redis.sorted_sets)
        self.assertIn("history:rd:path-x:srtConn:UUID-C", self.redis.sorted_sets)
        self.assertEqual(
            len(self.redis.sorted_sets["history:rd:path-x:srtConn:UUID-A"]), 1
        )
        self.assertEqual(
            len(self.redis.sorted_sets["history:rd:path-x:srtConn:UUID-B"]), 1
        )

    def test_overlapping_connections_are_never_deduplicated(self):
        client = LifecycleMediaMTXClient([])
        reader_a = self.reader("UUID-A", 51001)
        reader_b = self.reader("UUID-B", 51017)
        reader_c = self.reader("UUID-C", 51023)
        sequences = [[reader_a], [reader_a, reader_b], [reader_b, reader_c], [reader_c]]

        observed = []
        for offset, readers in enumerate(sequences):
            client.readers = readers
            snapshot, _metrics = self.collect(client, 2000.0 + offset)
            observed.append([reader["id"] for reader in snapshot[0]["readers"]])

        self.assertEqual(
            observed,
            [["UUID-A"], ["UUID-A", "UUID-B"], ["UUID-B", "UUID-C"], ["UUID-C"]],
        )

    def test_same_host_different_ids_and_ports_remain_distinct(self):
        client = LifecycleMediaMTXClient(
            [self.reader("UUID-A", 51001), self.reader("UUID-B", 51017)]
        )

        snapshot, _metrics = self.collect(client, 3000.0)

        self.assertEqual(len(snapshot[0]["readers"]), 2)
        self.assertEqual(
            [reader["details"]["remoteAddr"] for reader in snapshot[0]["readers"]],
            ["192.168.1.50:51001", "192.168.1.50:51017"],
        )

    def test_fast_poll_fetches_only_active_details_and_exposes_freshness(self):
        client = LifecycleMediaMTXClient([self.reader("UUID-A", 51001)])

        _first, first_metrics = self.collect(client, 4000.0)
        first_endpoints = [endpoint for endpoint, _params in client.calls]
        client.calls.clear()
        _second, second_metrics = self.collect(client, 4001.0)
        second_endpoints = [endpoint for endpoint, _params in client.calls]

        self.assertEqual(
            first_endpoints,
            [
                "/v3/info",
                "/v3/paths/list",
                "/v3/srtconns/list",
                "/v3/paths/forward/list",
            ],
        )
        self.assertEqual(
            second_endpoints,
            ["/v3/paths/list", "/v3/srtconns/list"],
        )
        self.assertEqual(first_metrics["api_request_count"], 4)
        self.assertEqual(second_metrics["api_request_count"], 2)
        freshness_key = stream_snapshot_freshness_key(mediamtx_collector.REDIS_KEY)
        self.assertEqual(json.loads(self.redis.values[freshness_key]), 4001.0)

    def test_failed_paths_poll_preserves_last_successful_snapshot_and_freshness(self):
        active = LifecycleMediaMTXClient([self.reader("UUID-A", 51001)])
        snapshot, _metrics = self.collect(active, 5000.0)
        freshness_key = stream_snapshot_freshness_key(mediamtx_collector.REDIS_KEY)

        failing = FailingPathsClient([])
        mediamtx_collector.mediamtx_client = failing
        with mock.patch.object(
            mediamtx_collector.time, "time", return_value=5001.0
        ):
            mediamtx_collector.collect_and_store()

        self.assertEqual(
            json.loads(self.redis.values[mediamtx_collector.REDIS_KEY]), snapshot
        )
        self.assertEqual(json.loads(self.redis.values[freshness_key]), 5000.0)


if __name__ == "__main__":
    unittest.main()
