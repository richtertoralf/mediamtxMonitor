import unittest

from bin.redis_keys import (
    DEFAULT_RTT_PUBLISHER_PREFIX,
    DEFAULT_STREAM_SNAPSHOT_KEY,
    DEFAULT_SYSTEM_SNAPSHOT_KEY,
    bitrate_state_keys,
    publisher_connection_key,
    publisher_rtt_keys,
    publisher_srt_health_key,
    reader_connection_key,
    reader_srt_health_key,
    srt_counter_key,
)


class SnapshotKeyTests(unittest.TestCase):
    def test_existing_snapshot_defaults_are_unchanged(self):
        self.assertEqual(DEFAULT_STREAM_SNAPSHOT_KEY, "mediamtx:streams:latest")
        self.assertEqual(DEFAULT_SYSTEM_SNAPSHOT_KEY, "mediamtx:system:latest")


class ConnectionStateKeyTests(unittest.TestCase):
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


class RttKeyTests(unittest.TestCase):
    def test_all_publisher_rtt_keys_match_existing_schema(self):
        self.assertEqual(DEFAULT_RTT_PUBLISHER_PREFIX, "rtt:pub")
        self.assertEqual(publisher_rtt_keys("192.0.2.10"), (
            "rtt:pub:192.0.2.10:ewma_ms",
            "rtt:pub:192.0.2.10:last_ms",
            "rtt:pub:192.0.2.10:last_ts",
        ))

    def test_ipv6_and_custom_prefix_remain_unescaped(self):
        self.assertEqual(
            publisher_rtt_keys("2001:db8::1", "custom:rtt"),
            (
                "custom:rtt:2001:db8::1:ewma_ms",
                "custom:rtt:2001:db8::1:last_ms",
                "custom:rtt:2001:db8::1:last_ts",
            ),
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
