import copy
import json
import unittest

from bin.redis_store import (
    NamespacedRedis,
    RedisStore,
    SnapshotDecodeError,
    redis_key_prefix,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.set_calls = []
        self.sorted_sets = {}
        self.expirations = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.set_calls.append((key, value))
        self.values[key] = value

    def zadd(self, key, members):
        values = self.sorted_sets.setdefault(key, {})
        values.update(members)

    def zremrangebyscore(self, key, minimum, maximum):
        values = self.sorted_sets.setdefault(key, {})
        for member, score in list(values.items()):
            if score <= float(maximum):
                del values[member]

    def expire(self, key, seconds):
        self.expirations[key] = seconds

    def zrangebyscore(self, key, minimum, maximum):
        values = self.sorted_sets.get(key, {})
        return [
            member
            for member, score in sorted(values.items(), key=lambda item: item[1])
            if float(minimum) <= score <= float(maximum)
        ]


class FailingRedis:
    def get(self, key):
        raise ConnectionError(f"get failed: {key}")

    def set(self, key, value):
        raise ConnectionError(f"set failed: {key}")


class RedisStoreTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.store = RedisStore(self.redis)

    def test_application_and_node_namespace_is_applied_at_io_boundary(self):
        raw = FakeRedis()
        store = RedisStore(NamespacedRedis(raw, "mediamtx-monitor:", "local"))

        store.write_snapshot("streams:latest", {"ok": True})

        self.assertIn("mediamtx-monitor:node:local:streams:latest", raw.values)
        self.assertEqual(
            redis_key_prefix("mediamtx-monitor:", "node-a"),
            "mediamtx-monitor:node:node-a:",
        )

    def test_write_serializes_snapshot_to_supplied_key_without_ttl(self):
        snapshot = {"streams": [{"name": "camera/main"}]}

        self.store.write_snapshot("streams:latest", snapshot)

        self.assertEqual(self.redis.set_calls, [(
            "streams:latest",
            json.dumps(snapshot),
        )])

    def test_read_decodes_snapshot(self):
        self.redis.values["system:latest"] = json.dumps({
            "cpu_percent": 12.5,
        })

        self.assertEqual(
            self.store.read_snapshot("system:latest"),
            {"cpu_percent": 12.5},
        )

    def test_missing_key_returns_none(self):
        self.assertIsNone(self.store.read_snapshot("missing:snapshot"))

    def test_invalid_json_raises_snapshot_decode_error(self):
        self.redis.values["broken:snapshot"] = "not-json"

        with self.assertRaises(SnapshotDecodeError) as context:
            self.store.read_snapshot("broken:snapshot")

        self.assertEqual(context.exception.key, "broken:snapshot")

    def test_redis_read_error_propagates(self):
        with self.assertRaises(ConnectionError):
            RedisStore(FailingRedis()).read_snapshot("snapshot")

    def test_redis_write_error_propagates(self):
        with self.assertRaises(ConnectionError):
            RedisStore(FailingRedis()).write_snapshot("snapshot", {})

    def test_unserializable_snapshot_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.store.write_snapshot("snapshot", {"value": object()})

    def test_write_does_not_mutate_snapshot(self):
        snapshot = {"streams": [{"name": "camera/main"}]}
        before = copy.deepcopy(snapshot)

        self.store.write_snapshot("snapshot", snapshot)

        self.assertEqual(snapshot, before)

    def test_history_is_ordered_time_trimmed_and_expires(self):
        for timestamp in (100.0, 130.0, 166.0):
            self.store.append_history_sample(
                "history:pub:stream:srtConn:id",
                {"timestamp": timestamp, "transport_rtt_ms": timestamp},
                timestamp=timestamp,
                retention_seconds=65,
                ttl_seconds=120,
            )

        self.assertEqual(
            self.store.read_history(
                "history:pub:stream:srtConn:id",
                from_timestamp=100,
                to_timestamp=200,
            ),
            [
                {"timestamp": 130.0, "transport_rtt_ms": 130.0},
                {"timestamp": 166.0, "transport_rtt_ms": 166.0},
            ],
        )
        self.assertEqual(
            self.redis.expirations["history:pub:stream:srtConn:id"], 120
        )

    def test_separate_history_keys_do_not_mix_samples(self):
        self.store.append_history_sample(
            "history:pub:stream:srtConn:first",
            {"timestamp": 10.0, "transport_rtt_ms": 20},
            timestamp=10.0,
            retention_seconds=65,
            ttl_seconds=120,
        )
        self.store.append_history_sample(
            "history:pub:stream:srtConn:second",
            {"timestamp": 10.0, "transport_rtt_ms": 30},
            timestamp=10.0,
            retention_seconds=65,
            ttl_seconds=120,
        )

        self.assertEqual(len(self.redis.sorted_sets), 2)


if __name__ == "__main__":
    unittest.main()
