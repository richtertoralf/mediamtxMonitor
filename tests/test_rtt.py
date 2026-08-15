import subprocess
import unittest
from unittest import mock

from bin import rtt
from tests.test_srt_health import FakeRedis


class RemoteHostTests(unittest.TestCase):
    def test_ipv4_ipv6_and_hostname_are_extracted(self):
        self.assertEqual(rtt._parse_host("192.0.2.10:1935"), "192.0.2.10")
        self.assertEqual(rtt._parse_host("[2001:db8::10]:8554"), "2001:db8::10")
        self.assertEqual(rtt._parse_host("reader.example:443"), "reader.example")
        self.assertEqual(rtt._parse_host("reader.example"), "reader.example")
        self.assertIsNone(rtt._parse_host(""))

    def test_ping_timeout_is_unavailable(self):
        with mock.patch.object(
            rtt.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["ping"], 1.4),
        ):
            self.assertIsNone(rtt._icmp_ping_once("192.0.2.10"))


class ReaderPingTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.kwargs = {
            "path": "camera/main",
            "connection_type": "rtmpConn",
            "connection_id": "reader-a",
            "min_period_s": 30,
            "ttl_s": 300,
        }

    def measure(self, remote="192.0.2.20:1935"):
        return rtt.measure_reader_rtt_ms(self.redis, remote, **self.kwargs)

    def test_success_is_cached_smoothed_and_rate_limited(self):
        with (
            mock.patch.object(
                rtt.time, "time", side_effect=[100.0, 101.0, 131.0]
            ),
            mock.patch.object(
                rtt, "_icmp_ping_once", side_effect=[10.0, 20.0]
            ) as ping,
        ):
            self.assertEqual(self.measure(), 10.0)
            self.assertEqual(self.measure(), 10.0)
            self.assertEqual(self.measure(), 15.0)

        self.assertEqual(ping.call_count, 2)
        self.assertTrue(
            all(value == 300 for value in self.redis.expirations.values())
        )

    def test_failed_ping_is_unavailable_and_never_zero(self):
        with (
            mock.patch.object(rtt.time, "time", return_value=100.0),
            mock.patch.object(rtt, "_icmp_ping_once", return_value=None),
        ):
            self.assertIsNone(self.measure())
        self.assertEqual(self.redis.values, {})

    def test_failed_refresh_returns_existing_cache(self):
        with (
            mock.patch.object(rtt.time, "time", side_effect=[100.0, 131.0]),
            mock.patch.object(rtt, "_icmp_ping_once", side_effect=[12.0, None]),
        ):
            self.assertEqual(self.measure(), 12.0)
            self.assertEqual(self.measure(), 12.0)

    def test_new_connection_does_not_reuse_previous_connection_cache(self):
        with (
            mock.patch.object(rtt.time, "time", side_effect=[100.0, 101.0]),
            mock.patch.object(rtt, "_icmp_ping_once", side_effect=[12.0, None]),
        ):
            self.assertEqual(self.measure(), 12.0)
            self.kwargs["connection_id"] = "reader-reconnected"
            self.assertIsNone(self.measure())


if __name__ == "__main__":
    unittest.main()
