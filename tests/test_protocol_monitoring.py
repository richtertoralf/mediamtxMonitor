import json
import unittest
from pathlib import Path
from unittest import mock

from bin import mediamtx_collector
from bin.redis_store import RedisStore
from tests.test_bitrate import FakePipeline
from tests.test_srt_health import FakeRedis


class ProtocolRedis(FakeRedis):
    def pipeline(self):
        return FakePipeline(self)


class ProtocolClient:
    def __init__(self):
        self.path_errors = {"rtsp": 20, "webrtc": 4, "rtmp-hls": 1}
        self.details = {
            "/v3/rtspsessions/list": [
                {
                    "id": "rtsp-pub", "remoteAddr": "192.0.2.1:5000",
                    "transport": "udp", "inboundBytes": 0,
                    "inboundRTPPacketsLost": 10,
                    "inboundRTPPacketsInError": 2,
                    "inboundRTCPPacketsInError": 1,
                    "inboundRTPPacketsJitter": 2.5,
                },
                {
                    "id": "rtsp-reader", "remoteAddr": "192.0.2.2:5001",
                    "transport": "tcp", "outboundBytes": 0,
                    "outboundRTPPacketsReportedLost": 4,
                    "outboundRTPPacketsDiscarded": 1,
                },
            ],
            "/v3/webrtcsessions/list": [
                {
                    "id": "webrtc-pub", "remoteAddr": "192.0.2.3:5002",
                    "inboundBytes": 0, "inboundRTPPacketsLost": 3,
                    "inboundRTPPacketsJitter": 1.5,
                    "peerConnectionEstablished": True, "state": "publish",
                    "localCandidate": {"type": "host", "address": "10.0.0.1"},
                    "remoteCandidate": {"type": "srflx", "address": "192.0.2.3"},
                },
                {
                    "id": "webrtc-reader", "remoteAddr": "192.0.2.4:5003",
                    "outboundBytes": 0, "outboundFramesDiscarded": 2,
                    "peerConnectionEstablished": True, "state": "read",
                },
            ],
            "/v3/rtmpconns/list": [
                {
                    "id": "rtmp-pub", "remoteAddr": "192.0.2.5:1935",
                    "inboundBytes": 0, "state": "publish",
                },
                {
                    "id": "rtmp-reader", "remoteAddr": "192.0.2.6:1935",
                    "outboundBytes": 0, "outboundFramesDiscarded": 5,
                    "state": "read",
                },
            ],
            "/v3/hlssessions/list": [
                {
                    "id": "hls-reader", "remoteAddr": "192.0.2.7:5004",
                    "outboundBytes": 0, "created": "2026-08-16T00:00:00Z",
                    "userAgent": "Test Player", "isCDN": False,
                },
            ],
            "/v3/moqsessions/list": [
                {
                    "id": "moq-reader", "remoteAddr": "192.0.2.8:5005",
                    "outboundBytes": 0, "state": "read",
                    "transport": "quic", "version": "draft-01",
                },
            ],
        }
        self.muxer = {
            "path": "rtmp-hls", "created": "2026-08-16T00:00:00Z",
            "lastRequest": "2026-08-16T00:00:02Z", "outboundBytes": 1000,
            "outboundFramesDiscarded": 7,
        }

    def build_url(self, endpoint):
        return f"http://localhost:9997{endpoint}"

    def get_json(self, endpoint, params=None):
        if endpoint == "/v3/info":
            return {"version": "1.20.0"}
        if endpoint == "/v3/paths/list":
            return {"items": [
                {
                    "name": "rtsp", "inboundFramesInError": self.path_errors["rtsp"],
                    "source": {"type": "rtspSession", "id": "rtsp-pub"},
                    "readers": [{"type": "rtspSession", "id": "rtsp-reader"}],
                },
                {
                    "name": "webrtc", "inboundFramesInError": self.path_errors["webrtc"],
                    "source": {"type": "webRTCSession", "id": "webrtc-pub"},
                    "readers": [{"type": "webRTCSession", "id": "webrtc-reader"}],
                },
                {
                    "name": "rtmp-hls", "inboundFramesInError": self.path_errors["rtmp-hls"],
                    "source": {"type": "rtmpConn", "id": "rtmp-pub"},
                    "readers": [
                        {"type": "rtmpConn", "id": "rtmp-reader"},
                        {
                            "type": "hlsSession",
                            "id": self.details["/v3/hlssessions/list"][0]["id"],
                        },
                        {"type": "moqSession", "id": "moq-reader"},
                    ],
                },
            ]}
        if endpoint == "/v3/hlsmuxers/list":
            return {"items": [self.muxer]}
        return {"items": self.details.get(endpoint, [])}


class ProtocolCollectorTests(unittest.TestCase):
    def setUp(self):
        self.redis = ProtocolRedis()
        self.client = ProtocolClient()
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

    def test_protocol_metrics_share_reset_safe_windows_and_scopes(self):
        self.collect(100.0)
        rtsp_pub, rtsp_reader = self.client.details["/v3/rtspsessions/list"]
        rtsp_pub.update({
            "inboundRTPPacketsLost": 12,
            "inboundRTPPacketsInError": 3,
            "inboundRTCPPacketsInError": 1,
            "inboundRTPPacketsJitter": 4.5,
        })
        rtsp_reader.update({
            "outboundRTPPacketsReportedLost": 7,
            "outboundRTPPacketsDiscarded": 2,
        })
        webrtc_pub, webrtc_reader = self.client.details["/v3/webrtcsessions/list"]
        webrtc_pub["inboundRTPPacketsLost"] = 5
        webrtc_reader["outboundFramesDiscarded"] = 6
        self.client.details["/v3/rtmpconns/list"][1]["outboundFramesDiscarded"] = 8
        self.client.muxer["outboundFramesDiscarded"] = 10
        self.client.path_errors["rtsp"] = 22

        snapshot = self.collect(101.0)
        rtsp, webrtc, rtmp_hls = snapshot
        self.assertEqual(
            rtsp["source"]["window_metrics"]["protocol_counters"]["10s"],
            {"loss": 2, "rtcp_error": 0, "rtp_error": 1},
        )
        self.assertEqual(rtsp["source"]["protocol_metrics"]["gauges"], {
            "jitter_ms": 4.5,
        })
        self.assertEqual(rtsp["source"]["jitter_history"][-1]["ms"], 4.5)
        self.assertEqual(
            rtsp["readers"][0]["window_metrics"]["protocol_counters"]["10s"],
            {"discard": 1, "reported_loss": 3},
        )
        self.assertEqual(
            rtsp["path_metrics"]["window_metrics"]["protocol_counters"]["10s"],
            {"frame_error": 2},
        )
        self.assertEqual(
            webrtc["source"]["window_metrics"]["protocol_counters"]["10s"],
            {"rtp_loss": 2},
        )
        self.assertEqual(
            webrtc["readers"][0]["window_metrics"]["protocol_counters"]["10s"],
            {"frame_discard": 4},
        )
        self.assertEqual(
            rtmp_hls["readers"][0]["window_metrics"]["frame_discard"]["10s"],
            3,
        )
        self.assertEqual(
            rtmp_hls["hls_muxer"]["window_metrics"]["protocol_counters"]["10s"],
            {"mux_discard": 3},
        )
        self.assertEqual(rtmp_hls["hls_muxer"]["scope"], "hls_muxer")
        self.assertEqual(rtmp_hls["hls_muxer"]["path"], "rtmp-hls")
        self.assertEqual(
            rtmp_hls["readers"][2]["protocol_metrics"]["metadata"],
            {"state": "read", "transport": "quic", "version": "draft-01"},
        )

    def test_counter_reset_does_not_create_negative_window_value(self):
        self.collect(200.0)
        rtsp_pub = self.client.details["/v3/rtspsessions/list"][0]
        rtsp_pub["inboundRTPPacketsLost"] = 1
        source = self.collect(201.0)[0]["source"]
        counters = source.get("window_metrics", {}).get("protocol_counters", {})
        self.assertNotIn("loss", counters.get("10s", {}))

    def test_rtsp_reported_loss_large_native_jump_is_not_filtered(self):
        reader = self.client.details["/v3/rtspsessions/list"][1]
        reader["outboundRTPPacketsReportedLost"] = 0
        self.collect(250.0)
        reader["outboundRTPPacketsReportedLost"] = 33_554_430
        jumped = self.collect(251.0)[0]["readers"][0]
        self.assertEqual(
            jumped["window_metrics"]["protocol_counters"]["10s"][
                "reported_loss"
            ],
            33_554_430,
        )
        unchanged = self.collect(252.0)[0]["readers"][0]
        self.assertEqual(unchanged["protocol_metrics"]["counter_deltas"], {
            "discard": 0,
            "reported_loss": 0,
        })
        self.assertEqual(
            unchanged["window_metrics"]["protocol_counters"]["60s"][
                "reported_loss"
            ],
            33_554_430,
        )

    def test_new_hls_muxer_generation_does_not_inherit_old_history(self):
        self.collect(300.0)
        self.client.muxer["outboundFramesDiscarded"] = 9
        self.collect(301.0)
        self.client.muxer.update({
            "created": "2026-08-16T00:01:00Z",
            "outboundFramesDiscarded": 20,
        })
        muxer = self.collect(302.0)[2]["hls_muxer"]
        self.assertNotIn("protocol_counters", muxer.get("window_metrics", {}))
        self.assertIn(
            "history:hls-muxer:rtmp-hls:2026-08-16T00:00:00Z",
            self.redis.sorted_sets,
        )
        self.assertIn(
            "history:hls-muxer:rtmp-hls:2026-08-16T00:01:00Z",
            self.redis.sorted_sets,
        )

    def test_hls_rate_average_reuses_session_history_and_new_id_starts_fresh(self):
        hls = self.client.details["/v3/hlssessions/list"][0]
        self.collect(400.0)
        hls["outboundBytes"] = 600_000
        second = self.collect(401.0)[2]["readers"][1]
        self.assertNotIn("rate_metrics", second)
        hls["outboundBytes"] = 625_000
        third = self.collect(402.0)[2]["readers"][1]
        self.assertIn("10s", third["rate_metrics"])
        self.assertEqual(third["bitrate_mbps"], third["common"]["tx_mbit_s"])

        hls.update({"id": "hls-reader-new", "outboundBytes": 0})
        replacement = self.collect(403.0)[2]["readers"][1]
        self.assertEqual(replacement["id"], "hls-reader-new")
        self.assertNotIn("rate_metrics", replacement)
        self.assertIn(
            "history:rd:rtmp-hls:hlsSession:hls-reader",
            self.redis.sorted_sets,
        )
        self.assertIn(
            "history:rd:rtmp-hls:hlsSession:hls-reader-new",
            self.redis.sorted_sets,
        )


if __name__ == "__main__":
    unittest.main()
