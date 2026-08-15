import json
import unittest
from pathlib import Path
from unittest import mock

from bin import mediamtx_collector
from bin.redis_store import RedisStore
from tests.test_srt_health import FakeMediaMTXClient, FakeRedis


class ReaderIcmpIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        mediamtx_collector.r = self.redis
        mediamtx_collector.snapshot_store = RedisStore(self.redis)
        mediamtx_collector.reset_poll_cache()
        self.reader_specs = [
            ("rtmpConn", "rtmp-reader", "192.0.2.10:1935"),
            ("rtmpsConn", "rtmps-reader", "192.0.2.11:1936"),
            ("rtspSession", "rtsp-session", "192.0.2.12:8554"),
            ("rtspConn", "rtsp-conn", "192.0.2.13:8554"),
            ("rtspsSession", "rtsps-session", "192.0.2.14:8322"),
            ("rtspsConn", "rtsps-conn", "192.0.2.15:8322"),
            ("webRTCSession", "webrtc-reader", "[2001:db8::20]:8189"),
            ("moqSession", "moq-reader", "reader.example:443"),
            ("hlsSession", "hls-reader", "192.0.2.21:49152"),
            ("srtConn", "srt-reader", "192.0.2.22:9000"),
            ("rtmpConn", "missing-remote", None),
        ]
        mediamtx_collector.mediamtx_client = FakeMediaMTXClient(self.fetch)

    def fetch(self, endpoint, params=None):
        if endpoint == "/v3/info":
            return {"version": "1.20.0"}
        if endpoint == "/v3/paths/list":
            return {"items": [{
                "name": "reader-path",
                "source": {},
                "readers": [
                    {"type": reader_type, "id": reader_id}
                    for reader_type, reader_id, _remote in self.reader_specs
                ],
            }]}
        if endpoint == "/v3/paths/forward/list":
            return {"items": []}
        endpoint_by_type = {
            value: key for key, value in mediamtx_collector.DETAIL_ENDPOINTS.items()
        }
        reader_type = endpoint_by_type.get(endpoint)
        return {"items": [
            {
                "id": reader_id,
                **({"remoteAddr": remote} if remote is not None else {}),
                **({"msRTT": 44} if reader_type == "srtConn" else {}),
            }
            for item_type, reader_id, remote in self.reader_specs
            if item_type == reader_type
        ]}

    def collect(self, timestamp, measure=None):
        if measure is None:
            measure = lambda *_args, **_kwargs: 12.5
        with (
            mock.patch.object(Path, "write_text"),
            mock.patch.object(
                mediamtx_collector.time, "time", return_value=timestamp
            ),
            mock.patch.object(
                mediamtx_collector,
                "measure_configured_rtt",
                side_effect=measure,
            ) as configured_measure,
        ):
            mediamtx_collector.collect_and_store()
        snapshot = json.loads(self.redis.values[mediamtx_collector.REDIS_KEY])
        return snapshot[0], configured_measure

    def test_supported_readers_receive_only_external_icmp(self):
        stream, configured_measure = self.collect(100.0)
        readers = {reader["id"]: reader for reader in stream["readers"]}

        eligible_ids = {
            reader_id
            for reader_type, reader_id, remote in self.reader_specs
            if reader_type in mediamtx_collector.ICMP_READER_TYPES and remote
        }
        self.assertEqual(configured_measure.call_count, len(eligible_ids))
        for reader_id in eligible_ids:
            self.assertEqual(readers[reader_id]["icmp_rtt_ms"], 12.5)
        for reader_id in {"hls-reader", "srt-reader", "missing-remote"}:
            self.assertNotIn("icmp_rtt_ms", readers[reader_id])
        self.assertEqual(readers["srt-reader"]["transport_rtt_ms"], 44.0)
        self.assertNotIn("transport_rtt_ms", readers["webrtc-reader"])

        rtsp_calls = [
            call.kwargs["measurement_kwargs"]["connection_type"]
            for call in configured_measure.call_args_list
            if call.kwargs["measurement_kwargs"]["connection_type"]
            in {"rtspSession", "rtspConn"}
        ]
        self.assertCountEqual(rtsp_calls, ["rtspSession", "rtspConn"])

    def test_failed_measurement_stays_unavailable(self):
        stream, _configured_measure = self.collect(
            200.0, measure=lambda *_a, **_k: None
        )
        self.assertTrue(
            all("icmp_rtt_ms" not in reader for reader in stream["readers"])
        )

    def test_icmp_history_uses_shared_cadence_and_reconnect_identity(self):
        self.reader_specs = [("rtmpConn", "reader-a", "192.0.2.30:1935")]
        self.collect(300.0)
        self.collect(301.0)
        old_key = "history:rd:reader-path:rtmpConn:reader-a"
        old_samples = [json.loads(value) for value in self.redis.sorted_sets[old_key]]
        self.assertEqual(
            len([sample for sample in old_samples if "icmp_rtt_ms" in sample]),
            1,
        )

        self.reader_specs = [("rtmpConn", "reader-b", "192.0.2.30:1940")]
        self.collect(330.0)
        new_key = "history:rd:reader-path:rtmpConn:reader-b"
        self.assertIn(old_key, self.redis.sorted_sets)
        self.assertIn(new_key, self.redis.sorted_sets)
        new_samples = [json.loads(value) for value in self.redis.sorted_sets[new_key]]
        self.assertEqual(len(new_samples), 1)
        self.assertEqual(new_samples[0]["icmp_rtt_ms"], 12.5)


if __name__ == "__main__":
    unittest.main()
