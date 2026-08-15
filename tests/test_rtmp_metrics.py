import unittest

from bin.rtmp_metrics import frame_discard_delta
from tests.test_srt_health import FakeRedis


class FrameDiscardDeltaTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()

    def delta(self, key, value):
        return frame_discard_delta(
            self.redis, key=key, value=value, ttl=300
        )

    def test_baseline_growth_unchanged_and_reset(self):
        self.assertIsNone(self.delta("reader:a", 0))
        self.assertEqual(self.delta("reader:a", 3), 3)
        self.assertEqual(self.delta("reader:a", 3), 0)
        self.assertEqual(self.delta("reader:a", 8), 5)
        self.assertIsNone(self.delta("reader:a", 0))
        self.assertEqual(self.delta("reader:a", 2), 2)

    def test_connection_ids_are_isolated(self):
        self.assertIsNone(self.delta("reader:a", 8))
        self.assertEqual(self.delta("reader:a", 10), 2)
        self.assertIsNone(self.delta("reader:b", 0))
        self.assertEqual(self.delta("reader:b", 1), 1)
        self.assertEqual(self.delta("reader:a", 11), 1)

    def test_missing_counter_does_not_create_state(self):
        self.assertIsNone(self.delta("reader:a", None))
        self.assertNotIn("reader:a", self.redis.values)


if __name__ == "__main__":
    unittest.main()
