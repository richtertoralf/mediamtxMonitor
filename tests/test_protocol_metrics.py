import unittest

from bin.protocol_metrics import (
    build_common_metrics,
    build_protocol_metrics,
    counter_fields,
)


class ProtocolMetricMappingTests(unittest.TestCase):
    def test_common_directional_model_uses_available_bytes_and_rate(self):
        publisher = build_common_metrics(
            "rtspSession",
            {"remoteAddr": "192.0.2.1:5000", "inboundBytes": 2_000},
            "publisher",
            1.25,
        )
        reader = build_common_metrics(
            "webRTCSession",
            {"outboundBytes": 3_000, "state": "read"},
            "reader",
            2.5,
        )
        self.assertEqual(publisher["direction"], "IN")
        self.assertEqual(publisher["rx_mbit_s"], 1.25)
        self.assertEqual(publisher["total_bytes"], 2_000)
        self.assertEqual(reader["direction"], "OUT")
        self.assertEqual(reader["tx_mbit_s"], 2.5)
        self.assertEqual(reader["total_bytes"], 3_000)

    def test_rtsp_directions_have_distinct_native_counters(self):
        self.assertEqual(counter_fields("rtspSession", "publisher"), {
            "loss": "inboundRTPPacketsLost",
            "rtp_error": "inboundRTPPacketsInError",
            "rtcp_error": "inboundRTCPPacketsInError",
        })
        self.assertEqual(counter_fields("rtspsSession", "reader"), {
            "reported_loss": "outboundRTPPacketsReportedLost",
            "discard": "outboundRTPPacketsDiscarded",
        })

    def test_webrtc_publisher_maps_jitter_peer_and_ice_without_reader_rtt(self):
        details = {
            "inboundRTPPacketsJitter": 2.5,
            "peerConnectionEstablished": True,
            "state": "read",
            "localCandidate": {"type": "host"},
            "remoteCandidate": {"type": "srflx"},
        }
        metrics = build_protocol_metrics(
            "webRTCSession", details, "publisher", {"rtp_loss": 2}
        )
        self.assertEqual(metrics["gauges"], {"jitter_ms": 2.5})
        self.assertTrue(metrics["metadata"]["peer_connection_established"])
        self.assertEqual(metrics["counter_deltas"], {"rtp_loss": 2})
        self.assertNotIn("rtt", metrics)

    def test_rtmp_and_moq_do_not_invent_packet_health(self):
        rtmp = build_protocol_metrics(
            "rtmpConn", {"state": "publish"}, "publisher", {}
        )
        moq = build_protocol_metrics(
            "moqSession",
            {"state": "read", "transport": "quic", "version": "draft-01"},
            "reader",
            {},
        )
        self.assertEqual(rtmp["metadata"], {"state": "publish"})
        self.assertEqual(moq["metadata"]["transport"], "quic")
        self.assertNotIn("gauges", rtmp)
        self.assertNotIn("counter_deltas", moq)


if __name__ == "__main__":
    unittest.main()
