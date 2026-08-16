import unittest

from bin.counter_metrics import counter_delta, counter_deltas
from tests.test_srt_health import FakeRedis


class CounterMetricsTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()

    def test_normal_unchanged_reset_and_new_session_are_safe(self):
        self.assertIsNone(counter_delta(
            self.redis, key="conn:a:loss", value=10, ttl=120,
        ))
        self.assertEqual(counter_delta(
            self.redis, key="conn:a:loss", value=13, ttl=120,
        ), 3)
        self.assertEqual(counter_delta(
            self.redis, key="conn:a:loss", value=13, ttl=120,
        ), 0)
        self.assertIsNone(counter_delta(
            self.redis, key="conn:a:loss", value=2, ttl=120,
        ))
        self.assertIsNone(counter_delta(
            self.redis, key="conn:b:loss", value=30, ttl=120,
        ))
        self.assertEqual(self.redis.expirations["conn:a:loss"], 120)

    def test_multiple_native_fields_receive_normalized_names(self):
        fields = {"loss": "nativeLoss", "error": "nativeError"}
        counter_deltas(
            self.redis,
            base_key="rd:path:type:id:counters",
            details={"nativeLoss": 5, "nativeError": 2},
            fields=fields,
            ttl=300,
        )
        result = counter_deltas(
            self.redis,
            base_key="rd:path:type:id:counters",
            details={"nativeLoss": 8, "nativeError": 2},
            fields=fields,
            ttl=300,
        )
        self.assertEqual(result, {"loss": 3, "error": 0})


if __name__ == "__main__":
    unittest.main()
