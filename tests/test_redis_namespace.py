"""Tests for the central application/node Redis I/O namespace."""

from pathlib import Path
import unittest

from bin.redis_keys import (
    connection_history_key,
    connection_lifecycle_key,
    hls_muxer_metric_key,
    path_metric_key,
    publisher_connection_key,
    publisher_srt_health_key,
    reader_connection_key,
)
from bin.redis_store import NamespacedRedis


class RecordingRedis:
    def __init__(self):
        self.calls = []
        self.pipeline_instance = RecordingPipeline(self.calls)

    def get(self, key, **kwargs):
        self.calls.append(("get", (key,), kwargs))
        return "get-result"

    def set(self, key, value, **kwargs):
        self.calls.append(("set", (key, value), kwargs))
        return "set-result"

    def delete(self, *keys):
        self.calls.append(("delete", keys, {}))
        return 2

    def expire(self, key, ttl, **kwargs):
        self.calls.append(("expire", (key, ttl), kwargs))
        return True

    def zadd(self, key, mapping, **kwargs):
        self.calls.append(("zadd", (key, mapping), kwargs))
        return 1

    def zrangebyscore(self, key, minimum, maximum, **kwargs):
        self.calls.append(("zrangebyscore", (key, minimum, maximum), kwargs))
        return ["sample"]

    def zremrangebyscore(self, key, minimum, maximum, **kwargs):
        self.calls.append(("zremrangebyscore", (key, minimum, maximum), kwargs))
        return 1

    def pipeline(self):
        self.calls.append(("pipeline", (), {}))
        return self.pipeline_instance


class RecordingPipeline:
    def __init__(self, calls):
        self.calls = calls

    def set(self, key, value, **kwargs):
        self.calls.append(("pipeline.set", (key, value), kwargs))
        return self

    def execute(self):
        self.calls.append(("pipeline.execute", (), {}))
        return [True]


class RedisNamespaceTests(unittest.TestCase):
    def test_all_functional_key_families_receive_one_central_prefix(self):
        raw = RecordingRedis()
        client = NamespacedRedis(raw, "mediamtx-monitor:", "local")
        publisher = publisher_connection_key("camera", "srtConn", "pub-1")
        reader = reader_connection_key("camera", "srtConn", "rd-1")
        functional_keys = [
            "streams:latest",
            "system:latest",
            publisher,
            reader,
            publisher_srt_health_key("camera", "srtConn", "pub-1"),
            connection_history_key(publisher),
            path_metric_key("camera", "srtConn:pub-1"),
            hls_muxer_metric_key("camera", "created"),
            connection_lifecycle_key("camera", "publisher", "rtmpConn"),
        ]

        for key in functional_keys:
            client.get(key)

        self.assertEqual(
            [call[1][0] for call in raw.calls],
            [f"mediamtx-monitor:node:local:{key}" for key in functional_keys],
        )

    def test_configured_node_id_changes_the_complete_redis_prefix(self):
        raw = RecordingRedis()
        client = NamespacedRedis(raw, "mediamtx-monitor:", "node-a")

        client.set("streams:latest", "[]")

        self.assertEqual(raw.calls, [(
            "set",
            ("mediamtx-monitor:node:node-a:streams:latest", "[]"),
            {},
        )])

    def test_complete_key_bearing_method_contract(self):
        raw = RecordingRedis()
        client = NamespacedRedis(raw, "mediamtx-monitor:", "local")
        prefix = "mediamtx-monitor:node:local:"
        mapping = {"payload": 12.5}

        self.assertEqual(client.get("get-key"), "get-result")
        self.assertEqual(client.set("set-key", "value", ex=30, nx=True), "set-result")
        self.assertEqual(client.delete("first", "second"), 2)
        self.assertTrue(client.expire("expiry", 120, nx=True))
        self.assertEqual(client.zadd("sorted", mapping, nx=True, ch=True), 1)
        self.assertEqual(
            client.zrangebyscore("sorted", 1.5, 9.5, start=2, num=4),
            ["sample"],
        )
        self.assertEqual(
            client.zremrangebyscore("sorted", "-inf", 7.25),
            1,
        )
        pipeline = client.pipeline()
        self.assertIs(pipeline.set("pipeline-key", 5, ex=45), pipeline)
        self.assertEqual(pipeline.execute(), [True])

        self.assertEqual(raw.calls, [
            ("get", (f"{prefix}get-key",), {}),
            ("set", (f"{prefix}set-key", "value"), {"ex": 30, "nx": True}),
            ("delete", (f"{prefix}first", f"{prefix}second"), {}),
            ("expire", (f"{prefix}expiry", 120), {"nx": True}),
            ("zadd", (f"{prefix}sorted", mapping), {"nx": True, "ch": True}),
            (
                "zrangebyscore",
                (f"{prefix}sorted", 1.5, 9.5),
                {"start": 2, "num": 4},
            ),
            (
                "zremrangebyscore",
                (f"{prefix}sorted", "-inf", 7.25),
                {},
            ),
            ("pipeline", (), {}),
            ("pipeline.set", (f"{prefix}pipeline-key", 5), {"ex": 45}),
            ("pipeline.execute", (), {}),
        ])
        self.assertEqual(raw.calls[-2][1][0].count(prefix), 1)

    def test_productive_redis_connections_are_immediately_namespaced(self):
        repository = Path(__file__).resolve().parents[1]
        for relative_path in (
            "bin/mediamtx_collector.py",
            "bin/monitoring_api.py",
            "bin/system_monitor.py",
        ):
            source = (repository / relative_path).read_text(encoding="utf-8")
            self.assertEqual(source.count("redis.Redis("), 1)
            self.assertEqual(source.count("NamespacedRedis(raw_redis,"), 1)


if __name__ == "__main__":
    unittest.main()
