import unittest

from bin.bitrate import calc_bitrate
from bin.redis_keys import bitrate_state_keys


class FakePipeline:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.operations = []

    def set(self, key, value, ex=None):
        self.operations.append((key, value, ex))
        return self

    def execute(self):
        for key, value, _ttl in self.operations:
            self.redis.values[key] = str(value)


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = str(value)

    def pipeline(self):
        return FakePipeline(self)


class BitrateCadenceTests(unittest.TestCase):
    def seed(self, redis_client, key):
        previous_bytes, previous_timestamp, ewma = bitrate_state_keys(key)
        redis_client.values[previous_bytes] = "0"
        redis_client.values[previous_timestamp] = "0"
        redis_client.values[ewma] = "0"

    def test_one_second_samples_preserve_five_second_ewma_time_effect(self):
        fast = FakeRedis()
        slow = FakeRedis()
        self.seed(fast, "fast")
        self.seed(slow, "slow")

        fast_result = None
        for second in range(1, 6):
            fast_result = calc_bitrate(
                fast,
                key="fast",
                bytes_now=1_250_000 * second,
                now=second,
                min_dt=0.5,
                smooth_alpha=0.5,
                smooth_reference_seconds=5,
                ttl=300,
            )
        slow_result = calc_bitrate(
            slow,
            key="slow",
            bytes_now=6_250_000,
            now=5,
            min_dt=0.5,
            smooth_alpha=0.5,
            smooth_reference_seconds=5,
            ttl=300,
        )

        self.assertEqual(fast_result, 5.0)
        self.assertEqual(slow_result, 5.0)


if __name__ == "__main__":
    unittest.main()
