import copy
import json
import unittest

from bin.redis_store import RedisStore, SnapshotDecodeError


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.set_calls = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.set_calls.append((key, value))
        self.values[key] = value


class FailingRedis:
    def get(self, key):
        raise ConnectionError(f"get failed: {key}")

    def set(self, key, value):
        raise ConnectionError(f"set failed: {key}")


class RedisStoreTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.store = RedisStore(self.redis)

    def test_write_serializes_snapshot_to_supplied_key_without_ttl(self):
        snapshot = {"streams": [{"name": "camera/main"}]}

        self.store.write_snapshot("mediamtx:streams:latest", snapshot)

        self.assertEqual(self.redis.set_calls, [(
            "mediamtx:streams:latest",
            json.dumps(snapshot),
        )])

    def test_read_decodes_snapshot(self):
        self.redis.values["mediamtx:system:latest"] = json.dumps({
            "cpu_percent": 12.5,
        })

        self.assertEqual(
            self.store.read_snapshot("mediamtx:system:latest"),
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


if __name__ == "__main__":
    unittest.main()
