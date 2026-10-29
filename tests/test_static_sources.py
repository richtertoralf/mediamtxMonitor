import json
import unittest
from pathlib import Path
from unittest import mock

from bin import mediamtx_collector
from bin.mediamtx_client import MediaMTXHTTPError
from bin.mediamtx_model import redact_error_text, sanitize_static_source
from bin.redis_store import RedisStore
from tests.test_protocol_monitoring import ProtocolRedis


SECRET = "kamera-passwort"


class StaticSourceClient:
    def __init__(self):
        self.static_requests = []
        self.path_bytes = 0
        self.fail = set()
        self.sources = {
            "pull-rtsp": {
                "type": "rtspSource", "state": "running", "lastError": "",
                "created": "2026-10-29T10:00:00+01:00",
                "typeSpecific": {
                    "remoteAddr": "192.0.2.20:554", "transport": "TCP",
                    "inboundBytes": 0, "inboundRTPPacketsLost": 1,
                    "inboundRTPPacketsInError": 0, "inboundRTCPPacketsInError": 0,
                    "inboundRTPPacketsJitter": 5.5,
                },
            },
            "pull-srt": {
                "type": "srtSource", "state": "running", "lastError": "",
                "created": "2026-10-29T10:00:00+01:00",
                "typeSpecific": {
                    "remoteAddr": "192.0.2.21:9000", "msRTT": 12.5,
                    "msReceiveTsbPdDelay": 200, "mbpsReceiveRate": 3.2,
                    "packetsReceivedLoss": 4, "packetsReceivedRetrans": 2,
                    "packetsReceivedDrop": 0, "packetsReceivedBelated": 0,
                    "packetsReceivedUnique": 100, "packetsReceivedUndecrypt": 0,
                },
            },
            "pull-dead": {
                "type": "rtspSource", "state": "error",
                "created": "2026-10-29T10:00:00+01:00",
                "lastError": (
                    f"dial rtsp://admin:{SECRET}@192.0.2.22:554/stream?token={SECRET}: "
                    "connection refused"
                ),
                "typeSpecific": None,
            },
            "pull-hls": {
                "type": "hlsSource", "state": "idle", "lastError": "",
                "created": "2026-10-29T10:00:00+01:00",
            },
        }

    def build_url(self, endpoint):
        return f"http://localhost:9997{endpoint}"

    def get_json(self, endpoint, params=None):
        if endpoint == "/v3/info":
            return {"version": "1.21.3"}
        if endpoint == "/v3/paths/list":
            items = [
                {"name": name, "available": True, "online": True,
                 "inboundBytes": self.path_bytes,
                 "source": {"type": source["type"], "id": ""}, "readers": []}
                for name, source in self.sources.items()
            ]
            items.append({"name": "push", "available": True, "online": True,
                          "source": {"type": "rtmpConn", "id": "p"}, "readers": []})
            return {"pageCount": 1, "items": items}
        prefix = "/v3/paths/static-sources/get/"
        if endpoint.startswith(prefix):
            name = endpoint[len(prefix):]
            self.static_requests.append(name)
            if name in self.fail:
                raise MediaMTXHTTPError(self.build_url(endpoint), 500)
            return self.sources[name]
        return {"items": []}


class StaticSourceCollectorTests(unittest.TestCase):
    def setUp(self):
        self.redis = ProtocolRedis()
        self.client = StaticSourceClient()
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
        return {item["name"]: item for item in snapshot}

    def test_only_static_sources_are_queried_within_the_refresh_interval(self):
        self.collect(100.0)
        self.assertEqual(
            sorted(self.client.static_requests),
            ["pull-dead", "pull-hls", "pull-rtsp", "pull-srt"],
        )
        self.collect(101.0)
        self.assertEqual(len(self.client.static_requests), 4)
        self.collect(105.0)
        self.assertEqual(len(self.client.static_requests), 8)

    def test_static_sources_reuse_connection_metrics(self):
        first = self.collect(100.0)
        self.client.sources["pull-rtsp"]["typeSpecific"]["inboundRTPPacketsLost"] = 4
        self.client.sources["pull-srt"]["typeSpecific"]["packetsReceivedLoss"] = 9
        self.client.path_bytes = 1_000_000
        streams = self.collect(105.0)

        rtsp = streams["pull-rtsp"]["source"]
        self.assertEqual(rtsp["connection_type"], "rtspSession")
        self.assertEqual(rtsp["details"]["state"], "running")
        self.assertEqual(rtsp["protocol_metrics"]["gauges"]["jitter_ms"], 5.5)
        self.assertEqual(
            rtsp["window_metrics"]["protocol_counters"]["10s"]["loss"], 3,
        )
        # The rate comes from the current path counter, not cached details.
        self.assertEqual(rtsp["bitrate_mbps"], 1.6)

        srt = streams["pull-srt"]["source"]
        self.assertEqual(srt["connection_type"], "srtConn")
        self.assertEqual(srt["transport_rtt_ms"], 12.5)
        self.assertEqual(srt["srt_latency_ms"], 200)
        self.assertEqual(srt["bitrate_mbps"], 3.2)
        self.assertEqual(srt["srt_health"]["loss_packets"], 5)

        hls = streams["pull-hls"]["source"]
        self.assertNotIn("connection_type", hls)
        self.assertEqual(hls["details"]["state"], "idle")
        self.assertNotIn("connection_type", first["push"]["source"])

    def test_error_texts_are_redacted_and_api_errors_leave_no_stale_data(self):
        streams = self.collect(100.0)
        dead = streams["pull-dead"]["source"]["details"]
        self.assertEqual(dead["state"], "error")
        self.assertIn("connection refused", dead["last_error"])
        stored = json.dumps(self.redis.values[mediamtx_collector.REDIS_KEY])
        self.assertNotIn(SECRET, stored)
        self.assertNotIn("admin", stored)

        self.client.fail = {"pull-rtsp"}
        streams = self.collect(105.0)
        self.assertEqual(streams["pull-rtsp"]["source"]["details"], {})
        self.assertEqual(streams["pull-srt"]["source"]["details"]["state"], "running")


class RedactionTests(unittest.TestCase):
    def test_urls_userinfo_and_query_values_are_removed(self):
        text = redact_error_text(
            f"dial rtsp://u:{SECRET}@host:554/x?jwt={SECRET} failed; "
            f"user:{SECRET}@10.0.0.1 refused &pass={SECRET}"
        )
        self.assertNotIn(SECRET, text)
        self.assertIn("failed", text)
        self.assertIn("refused", text)

    def test_plain_reason_stays_readable_and_bounded(self):
        reason = "dial tcp 127.0.0.1:18999: connect: connection refused"
        self.assertEqual(redact_error_text(reason), reason)
        self.assertEqual(len(redact_error_text("x" * 500)), 200)
        self.assertIsNone(redact_error_text(""))

    def test_missing_state_means_no_static_data(self):
        self.assertEqual(sanitize_static_source({"items": []}), {})


if __name__ == "__main__":
    unittest.main()
