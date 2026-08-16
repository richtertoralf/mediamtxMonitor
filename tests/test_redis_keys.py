import unittest

from bin.redis_keys import (
    DEFAULT_STREAM_SNAPSHOT_KEY,
    DEFAULT_SYSTEM_SNAPSHOT_KEY,
    bitrate_state_keys,
    connection_counter_key,
    connection_lifecycle_key,
    connection_history_key,
    hls_muxer_metric_key,
    path_metric_key,
    publisher_connection_key,
    publisher_srt_health_key,
    reader_connection_key,
    reader_srt_health_key,
    rtmp_frame_discard_key,
    srt_counter_key,
    stream_snapshot_freshness_key,
)


class SnapshotKeyTests(unittest.TestCase):
    def test_existing_snapshot_defaults_are_unchanged(self):
        self.assertEqual(DEFAULT_STREAM_SNAPSHOT_KEY, "mediamtx:streams:latest")
        self.assertEqual(DEFAULT_SYSTEM_SNAPSHOT_KEY, "mediamtx:system:latest")

    def test_stream_freshness_is_a_snapshot_sidecar(self):
        self.assertEqual(
            stream_snapshot_freshness_key("mediamtx:streams:latest"),
            "mediamtx:streams:latest:collected_at",
        )


class ConnectionStateKeyTests(unittest.TestCase):
    def test_history_wraps_existing_publisher_and_reader_identity(self):
        publisher = publisher_connection_key("stream", "srtConn", "pub-id")
        reader = reader_connection_key("stream", "srtConn", "reader-id")

        self.assertEqual(
            connection_history_key(publisher),
            "history:pub:stream:srtConn:pub-id",
        )
        self.assertEqual(
            connection_history_key(reader),
            "history:rd:stream:srtConn:reader-id",
        )

    def test_publisher_bitrate_keys_match_existing_schema(self):
        base_key = publisher_connection_key("stream", "srtConn", "123")
        self.assertEqual(base_key, "pub:stream:srtConn:123")
        self.assertEqual(bitrate_state_keys(base_key), (
            "pub:stream:srtConn:123:prev_bytes",
            "pub:stream:srtConn:123:prev_ts",
            "pub:stream:srtConn:123:ewma_mbps",
        ))

    def test_reader_bitrate_keys_match_existing_schema(self):
        base_key = reader_connection_key("stream", "srtConn", "123")
        self.assertEqual(base_key, "rd:stream:srtConn:123")
        self.assertEqual(bitrate_state_keys(base_key), (
            "rd:stream:srtConn:123:prev_bytes",
            "rd:stream:srtConn:123:prev_ts",
            "rd:stream:srtConn:123:ewma_mbps",
        ))

    def test_stream_paths_and_connection_ids_remain_unescaped(self):
        self.assertEqual(
            publisher_connection_key("camera/main room", "srtConn", "id:part:1"),
            "pub:camera/main room:srtConn:id:part:1",
        )

    def test_rtmp_discard_and_lifecycle_keys_use_central_roles(self):
        reader = reader_connection_key("camera/main", "rtmpConn", "reader:1")
        self.assertEqual(
            rtmp_frame_discard_key(reader),
            "rd:camera/main:rtmpConn:reader:1:rtmp_frame_discard",
        )
        self.assertEqual(
            connection_lifecycle_key("camera/main", "reader", "rtmpConn"),
            "lifecycle:reader:camera/main:rtmpConn",
        )

    def test_shared_counter_path_and_muxer_identities_are_central(self):
        reader = reader_connection_key("camera/main", "rtspSession", "reader:1")
        self.assertEqual(
            connection_counter_key(reader),
            "rd:camera/main:rtspSession:reader:1:counters",
        )
        self.assertEqual(path_metric_key("camera/main"), "path:camera/main")
        self.assertEqual(hls_muxer_metric_key("camera/main"), "hls-muxer:camera/main")
        self.assertEqual(
            path_metric_key("camera/main", "rtspSession:source:1"),
            "path:camera/main:rtspSession:source:1",
        )
        self.assertEqual(
            hls_muxer_metric_key("camera/main", "2026-08-16T00:00:00Z"),
            "hls-muxer:camera/main:2026-08-16T00:00:00Z",
        )


class SrtHealthKeyTests(unittest.TestCase):
    def test_publisher_counter_key_matches_existing_schema(self):
        health_key = publisher_srt_health_key("stream", "srtConn", "123")
        self.assertEqual(
            srt_counter_key(health_key, "packetsReceivedRetrans"),
            "srt-health:pub:stream:srtConn:123:packetsReceivedRetrans",
        )

    def test_reader_counter_key_matches_existing_schema(self):
        health_key = reader_srt_health_key("camera/main", "srtConn", "reader:1")
        self.assertEqual(
            srt_counter_key(health_key, "packetsRetrans"),
            "srt-health:rd:camera/main:srtConn:reader:1:packetsRetrans",
        )


if __name__ == "__main__":
    unittest.main()
