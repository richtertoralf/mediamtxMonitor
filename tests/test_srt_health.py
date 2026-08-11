import json
import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from srt_health import build_srt_health, counter_delta  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = str(value)
        self.expirations[key] = ex

    def ping(self):
        return True


class CounterDeltaTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()

    def test_first_cycle_has_no_delta_and_uses_ttl(self):
        self.assertIsNone(counter_delta(self.redis, "conn:counter", 10, 123))
        self.assertEqual(self.redis.expirations["conn:counter"], 123)

    def test_normal_delta_including_zero(self):
        counter_delta(self.redis, "conn:counter", 10, 123)
        self.assertEqual(counter_delta(self.redis, "conn:counter", 13, 123), 3)
        self.assertEqual(counter_delta(self.redis, "conn:counter", 13, 123), 0)

    def test_counter_reset_does_not_return_negative_value(self):
        counter_delta(self.redis, "conn:counter", 10, 123)
        self.assertIsNone(counter_delta(self.redis, "conn:counter", 2, 123))
        self.assertEqual(counter_delta(self.redis, "conn:counter", 5, 123), 3)

    def test_new_connection_id_has_independent_first_cycle(self):
        counter_delta(self.redis, "conn:a:counter", 10, 123)
        self.assertEqual(counter_delta(self.redis, "conn:a:counter", 12, 123), 2)
        self.assertIsNone(counter_delta(self.redis, "conn:b:counter", 50, 123))


class SrtHealthModelTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()

    def health(self, details, direction="publisher", key="conn"):
        return build_srt_health(
            self.redis, key=key, details=details, direction=direction, ttl=300
        )

    def test_publisher_reserve_is_link_divided_by_rx(self):
        health = self.health({"mbpsReceiveRate": 4.0, "mbpsLinkCapacity": 12.8})
        self.assertEqual(health["reserve_ratio"], 3.2)

    def test_reader_reserve_is_link_divided_by_tx(self):
        health = self.health(
            {"mbpsSendRate": 4.25, "mbpsLinkCapacity": 11.4}, "reader"
        )
        self.assertEqual(health["reserve_ratio"], 2.68)

    def test_retrans_drop_and_belated_are_interval_values(self):
        first = {
            "packetsReceivedRetrans": 100,
            "packetsReceivedDrop": 8,
            "packetsReceivedBelated": 2,
        }
        second = {
            "packetsReceivedRetrans": 103,
            "packetsReceivedDrop": 8,
            "packetsReceivedBelated": 4,
        }
        self.health(first)
        health = self.health(second)
        self.assertEqual(health["retrans_packets"], 3)
        self.assertEqual(health["drop_packets"], 0)
        self.assertEqual(health["belated_packets"], 2)

    def test_reader_retrans_and_drop_are_interval_values(self):
        self.health(
            {"packetsRetrans": 20, "packetsSendDrop": 5},
            direction="reader",
        )
        health = self.health(
            {"packetsRetrans": 22, "packetsSendDrop": 5},
            direction="reader",
        )
        self.assertEqual(health["retrans_packets"], 2)
        self.assertEqual(health["drop_packets"], 0)

    def test_missing_values_do_not_create_zero_placeholders(self):
        self.assertEqual(self.health({}), {})
        self.assertNotIn(
            "reserve_ratio",
            self.health({"mbpsReceiveRate": 4.0}),
        )


class CollectorSrtHealthIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import mediamtx_collector

        cls.collector = mediamtx_collector

    def setUp(self):
        self.redis = FakeRedis()
        self.collector.r = self.redis
        self.srt_details = [
            {
                "id": "srt-publisher",
                "remoteAddr": "192.0.2.10:9000",
                "mbpsReceiveRate": 4.0,
                "mbpsLinkCapacity": 12.0,
                "msRTT": 20,
                "packetsReceivedRetrans": 10,
            },
            {
                "id": "srt-reader",
                "remoteAddr": "192.0.2.11:9000",
                "mbpsSendRate": 3.5,
                "mbpsLinkCapacity": 10.5,
                "packetsRetrans": 4,
            },
        ]
        self.rtmp_details = [
            {"id": "rtmp-publisher", "remoteAddr": "192.0.2.20:1935"},
            {"id": "rtmp-reader", "remoteAddr": "192.0.2.21:1935"},
        ]

    def fetch(self, endpoint, params=None):
        if endpoint == "/v3/info":
            return {"version": "1.20.0"}
        if endpoint == "/v3/paths/list":
            return {
                "items": [
                    {
                        "name": "srt-path",
                        "source": {"type": "srtConn", "id": "srt-publisher"},
                        "readers": [{"type": "srtConn", "id": "srt-reader"}],
                    },
                    {
                        "name": "rtmp-path",
                        "source": {"type": "rtmpConn", "id": "rtmp-publisher"},
                        "readers": [{"type": "rtmpConn", "id": "rtmp-reader"}],
                    },
                ]
            }
        if endpoint == "/v3/srtconns/list":
            return {"items": self.srt_details}
        if endpoint == "/v3/rtmpconns/list":
            return {"items": self.rtmp_details}
        return {"items": []}

    def collect(self):
        with (
            mock.patch.object(self.collector, "fetch", side_effect=self.fetch),
            mock.patch.object(Path, "write_text"),
        ):
            self.collector.collect_and_store()
        return json.loads(self.redis.values[self.collector.REDIS_KEY])

    def test_collector_adds_srt_health_with_stable_separate_keys(self):
        first = self.collect()
        srt_path = first[0]
        rtmp_path = first[1]

        self.assertEqual(srt_path["source"]["srt_health"]["rx_mbps"], 4.0)
        self.assertEqual(srt_path["readers"][0]["srt_health"]["tx_mbps"], 3.5)
        self.assertNotIn("srt_health", rtmp_path["source"])
        self.assertNotIn("srt_health", rtmp_path["readers"][0])

        health_keys = {
            key for key in self.redis.values if key.startswith("srt-health:")
        }
        publisher_key = (
            "srt-health:pub:srt-path:srtConn:srt-publisher:"
            "packetsReceivedRetrans"
        )
        reader_key = (
            "srt-health:rd:srt-path:srtConn:srt-reader:packetsRetrans"
        )
        self.assertIn(publisher_key, health_keys)
        self.assertIn(reader_key, health_keys)
        self.assertNotEqual(publisher_key, reader_key)

        self.srt_details[0]["packetsReceivedRetrans"] = 13
        self.srt_details[1]["packetsRetrans"] = 6
        second = self.collect()
        self.assertEqual(second[0]["source"]["srt_health"]["retrans_packets"], 3)
        self.assertEqual(
            second[0]["readers"][0]["srt_health"]["retrans_packets"], 2
        )
        self.assertEqual(
            health_keys,
            {key for key in self.redis.values if key.startswith("srt-health:")},
        )


if __name__ == "__main__":
    unittest.main()
