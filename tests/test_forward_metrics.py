import json
import unittest
from pathlib import Path
from unittest import mock

from bin import mediamtx_collector
from bin.redis_store import RedisStore
from bin.stream_normalizer import sanitize_forward_destinations
from tests.test_protocol_monitoring import ProtocolRedis


SECRET = "streamkey-geheim"


def srt_forward(forward_id, pos, sent, loss=0, retrans=0):
    return {
        "id": forward_id, "pos": pos, "type": "srt", "state": "forwarding",
        "created": "2026-10-29T10:00:00Z", "outboundBytes": sent,
        "lastError": f"dial srt://relay.example:9000?streamid={SECRET}",
        "conf": {"dest": f"srt://relay.example:9000?passphrase={SECRET}"},
        "typeSpecific": {
            "remoteAddr": "203.0.113.5:9000",
            "msRTT": 42.5, "msSendTsbPdDelay": 300, "msSendBuf": 120,
            "packetsSendLoss": loss, "packetsRetrans": retrans,
            "packetsSendDrop": 0, "packetsSent": 1000, "packetsSentUnique": 990,
            "bytesSent": sent,
        },
    }


def rtmp_forward(forward_id, pos, sent):
    return {
        "id": forward_id, "pos": pos, "type": "rtmp", "state": "forwarding",
        "created": "2026-10-29T10:00:00Z", "outboundBytes": sent,
        "typeSpecific": {"remoteAddr": "203.0.113.6:1935", "outboundBytes": sent},
    }


class ForwardClient:
    def __init__(self):
        self.forwards = []
        self.forward_requests = 0

    def build_url(self, endpoint):
        return f"http://localhost:9997{endpoint}"

    def get_json(self, endpoint, params=None):
        if endpoint == "/v3/info":
            return {"version": "1.21.3"}
        if endpoint == "/v3/paths/list":
            return {"pageCount": 1, "items": [{
                "name": "cam", "available": True, "online": True,
                "source": None, "readers": [],
            }]}
        if endpoint == "/v3/paths/forward-dests/list":
            self.forward_requests += 1
            return {"pageCount": 1, "items": self.forwards}
        return {"items": []}


class ForwardMetricTests(unittest.TestCase):
    def setUp(self):
        self.redis = ProtocolRedis()
        self.client = ForwardClient()
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
        snapshot = json.loads(self.redis.values[mediamtx_collector.REDIS_KEY])
        return {item["id"]: item for item in snapshot[0]["forwardDestinations"]}

    def test_rate_uses_the_refresh_interval_and_native_srt_metrics(self):
        self.client.forwards = [srt_forward("a", 0, 0), rtmp_forward("b", 1, 0)]
        first = self.collect(100.0)
        self.assertIsNone(first["b"]["bitrate_mbps"])

        self.client.forwards = [
            srt_forward("a", 0, 1_000_000, loss=2, retrans=5),
            rtmp_forward("b", 1, 1_250_000),
        ]
        # Between refreshes the cached rate stays; no request is repeated.
        self.collect(102.0)
        self.assertEqual(self.client.forward_requests, 1)
        second = self.collect(105.0)
        self.assertEqual(self.client.forward_requests, 2)

        self.assertEqual(second["b"]["bitrate_mbps"], 2.0)
        self.assertEqual(second["b"]["connection_type"], "rtmpConn")
        srt = second["a"]
        self.assertEqual(srt["connection_type"], "srtConn")
        self.assertEqual(srt["transport_rtt_ms"], 42.5)
        self.assertEqual(srt["srt_latency_ms"], 300)
        self.assertEqual(srt["details"]["msSendBuf"], 120)
        self.assertEqual(srt["srt_health"]["loss_packets"], 2)
        self.assertEqual(
            srt["window_metrics"]["events"]["10s"]["retrans_packets"], 5,
        )

    def test_reordering_keeps_identity_by_native_id(self):
        self.client.forwards = [rtmp_forward("a", 0, 0), rtmp_forward("b", 1, 0)]
        self.collect(100.0)
        # A destination before "b" was removed: "b" moves to position 0.
        self.client.forwards = [rtmp_forward("b", 0, 1_250_000)]
        after = self.collect(105.0)
        self.assertEqual(list(after), ["b"])
        self.assertEqual(after["b"]["pos"], 0)
        self.assertEqual(after["b"]["bitrate_mbps"], 2.0)

    def test_changed_configuration_starts_a_new_baseline(self):
        self.client.forwards = [rtmp_forward("a", 0, 5_000_000)]
        self.collect(100.0)
        self.client.forwards = [rtmp_forward("new", 0, 100)]
        after = self.collect(105.0)
        self.assertIsNone(after["new"]["bitrate_mbps"])

    def test_counter_reset_yields_no_negative_values(self):
        self.client.forwards = [srt_forward("a", 0, 5_000_000, loss=10, retrans=10)]
        self.collect(100.0)
        self.client.forwards = [srt_forward("a", 0, 1_000, loss=1, retrans=1)]
        after = self.collect(105.0)["a"]
        self.assertNotIn("loss_packets", after["srt_health"])
        self.assertNotIn("retrans_packets", after["srt_health"])
        self.client.forwards = [srt_forward("a", 0, 1_000, loss=1, retrans=1)]
        after = self.collect(110.0)["a"]
        self.assertEqual(after["srt_health"]["loss_packets"], 0)

    def test_targets_and_error_texts_never_reach_the_snapshot(self):
        self.client.forwards = [srt_forward("a", 0, 0)]
        self.collect(100.0)
        stored = json.dumps(self.redis.values[mediamtx_collector.REDIS_KEY])
        for secret in (SECRET, "relay.example", "203.0.113.5", "lastError"):
            self.assertNotIn(secret, stored)


class ForwardSanitizerTests(unittest.TestCase):
    def test_sanitizer_is_idempotent_for_enriched_output(self):
        once = sanitize_forward_destinations([srt_forward("a", 0, 10)])
        once[0]["bitrate_mbps"] = 1.5
        twice = sanitize_forward_destinations(once)
        self.assertEqual(twice, once)
        self.assertNotIn("remoteAddr", twice[0]["details"])


if __name__ == "__main__":
    unittest.main()
