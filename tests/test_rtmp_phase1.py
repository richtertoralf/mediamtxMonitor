import json
import unittest
from pathlib import Path
from unittest import mock

from bin import mediamtx_collector
from bin.redis_store import RedisStore
from tests.test_srt_health import FakeRedis
from tests.test_bitrate import FakePipeline


class RTMPRedis(FakeRedis):
    def pipeline(self):
        return FakePipeline(self)


class RTMPPhaseClient:
    def __init__(self):
        self.connections = {
            "rtmpConn": [
                self.connection("rtmp-pub", "192.0.2.10:50000", inbound=0),
                self.connection("rtmp-reader-a", "192.0.2.20:51000", outbound=0),
                self.connection("rtmp-reader-b", "192.0.2.21:51001", outbound=0),
            ],
            "rtmpsConn": [
                self.connection("rtmps-pub", "192.0.2.11:50001", inbound=0),
                self.connection("rtmps-reader", "192.0.2.22:51002", outbound=0),
            ],
        }

    @staticmethod
    def connection(connection_id, remote, *, inbound=0, outbound=0, discard=0):
        return {
            "id": connection_id,
            "remoteAddr": remote,
            "inboundBytes": inbound,
            "outboundBytes": outbound,
            "outboundFramesDiscarded": discard,
        }

    def build_url(self, endpoint):
        return f"http://localhost:9997{endpoint}"

    def get_json(self, endpoint, params=None):
        if endpoint == "/v3/info":
            return {"version": "1.20.0"}
        if endpoint == "/v3/paths/list":
            plain_publisher = next(
                item["id"] for item in self.connections["rtmpConn"]
                if "pub" in item["id"]
            )
            secure_publisher = next(
                item["id"] for item in self.connections["rtmpsConn"]
                if "pub" in item["id"]
            )
            return {"items": [
                {
                    "name": "plain",
                    "source": {"type": "rtmpConn", "id": plain_publisher},
                    "readers": [
                        {"type": "rtmpConn", "id": item["id"]}
                        for item in self.connections["rtmpConn"]
                        if item["id"].startswith("rtmp-reader")
                    ],
                },
                {
                    "name": "secure",
                    "source": {"type": "rtmpsConn", "id": secure_publisher},
                    "readers": [{"type": "rtmpsConn", "id": "rtmps-reader"}],
                },
            ]}
        if endpoint == "/v3/rtmpconns/list":
            return {"items": self.connections["rtmpConn"]}
        if endpoint == "/v3/rtmpsconns/list":
            return {"items": self.connections["rtmpsConn"]}
        return {"items": []}


class CollectorRTMPPhaseTests(unittest.TestCase):
    def setUp(self):
        self.redis = RTMPRedis()
        self.client = RTMPPhaseClient()
        mediamtx_collector.r = self.redis
        mediamtx_collector.snapshot_store = RedisStore(self.redis)
        mediamtx_collector.mediamtx_client = self.client
        mediamtx_collector.reset_poll_cache()

    def collect(self, timestamp):
        with (
            mock.patch.object(Path, "write_text"),
            mock.patch.object(mediamtx_collector.time, "time", return_value=timestamp),
        ):
            mediamtx_collector.collect_and_store()
        return json.loads(self.redis.values[mediamtx_collector.REDIS_KEY])

    def test_rtmp_and_rtmps_reuse_directional_rate_history(self):
        self.collect(100.0)
        for connection in self.client.connections["rtmpConn"]:
            if connection["id"] == "rtmp-pub":
                connection["inboundBytes"] = 1_000_000
            else:
                connection["outboundBytes"] = 500_000
        self.client.connections["rtmpsConn"][0]["inboundBytes"] = 2_000_000
        self.client.connections["rtmpsConn"][1]["outboundBytes"] = 250_000

        snapshot = self.collect(101.0)
        plain, secure = snapshot
        self.assertEqual(plain["source"]["rate_history"], [
            {"timestamp": 100.0, "mbps": None},
            {"timestamp": 101.0, "mbps": 8.0},
        ])
        self.assertEqual(plain["readers"][0]["rate_history"][-1]["mbps"], 4.0)
        self.assertEqual(secure["source"]["rate_history"][-1]["mbps"], 16.0)
        self.assertEqual(secure["readers"][0]["rate_history"][-1]["mbps"], 2.0)

    def test_discard_deltas_are_reader_local_and_publisher_is_excluded(self):
        self.collect(200.0)
        self.client.connections["rtmpConn"][0]["outboundFramesDiscarded"] = 99
        self.client.connections["rtmpConn"][1]["outboundFramesDiscarded"] = 3
        self.client.connections["rtmpConn"][2]["outboundFramesDiscarded"] = 8
        second = self.collect(201.0)[0]

        self.assertNotIn("frame_discard_delta", second["source"])
        self.assertNotIn("frame_discard", second["source"].get("window_metrics", {}))
        self.assertEqual(
            second["readers"][0]["window_metrics"]["frame_discard"],
            {"10s": 3, "60s": 3},
        )
        self.assertEqual(
            second["readers"][1]["window_metrics"]["frame_discard"],
            {"10s": 8, "60s": 8},
        )

        self.client.connections["rtmpConn"][1]["outboundFramesDiscarded"] = 3
        self.client.connections["rtmpConn"][2]["outboundFramesDiscarded"] = 10
        third = self.collect(202.0)[0]
        self.assertEqual(third["readers"][0]["frame_discard_delta"], 0)
        self.assertEqual(third["readers"][1]["frame_discard_delta"], 2)
        self.assertEqual(
            third["readers"][1]["window_metrics"]["frame_discard"]["10s"], 10
        )

    def test_new_reader_id_gets_new_history_and_observed_change(self):
        self.collect(300.0)
        old = self.client.connections["rtmpConn"][1]
        old["outboundBytes"] = 500_000
        self.collect(301.0)
        replacement = self.client.connection(
            "rtmp-reader-new", "192.0.2.20:51999", outbound=0, discard=0
        )
        self.client.connections["rtmpConn"][1] = replacement

        reader = self.collect(302.0)[0]["readers"][0]
        self.assertEqual(reader["id"], "rtmp-reader-new")
        self.assertEqual(reader["rate_history"], [{"timestamp": 302.0, "mbps": None}])
        self.assertEqual(reader["connection_stability"]["changes_60s"], 1)
        self.assertEqual(reader["connection_stability"]["seconds_since_last_change"], 0)
        self.assertIn("history:rd:plain:rtmpConn:rtmp-reader-a", self.redis.sorted_sets)
        self.assertIn("history:rd:plain:rtmpConn:rtmp-reader-new", self.redis.sorted_sets)

    def test_publisher_change_is_observed_without_reader_fingerprinting(self):
        self.collect(400.0)
        self.client.connections["rtmpConn"][0] = self.client.connection(
            "rtmp-pub-new", "192.0.2.10:50999", inbound=0
        )
        source = self.collect(401.0)[0]["source"]
        self.assertEqual(source["connection_stability"]["changes_60s"], 1)

    def test_parallel_readers_on_same_host_get_no_attributed_stability(self):
        self.client.connections["rtmpConn"][2]["remoteAddr"] = "192.0.2.20:51001"
        readers = self.collect(500.0)[0]["readers"]
        self.assertEqual(len(readers), 2)
        self.assertTrue(all("connection_stability" not in reader for reader in readers))


if __name__ == "__main__":
    unittest.main()
