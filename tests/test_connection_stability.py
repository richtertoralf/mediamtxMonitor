import unittest

from bin.connection_lifecycle import (
    LIFECYCLE_TTL_SECONDS,
    observe_connection_groups,
    remote_host,
)
from tests.test_srt_health import FakeRedis


class ConnectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.key = "lifecycle:reader:path:rtmpConn"

    def observe(self, groups, timestamp, reset=False):
        return observe_connection_groups(
            self.redis,
            key=self.key,
            current_groups=groups,
            timestamp=timestamp,
            reset_baseline=reset,
        )

    def test_unchanged_id_is_stable_and_uses_short_ttl(self):
        first = self.observe({"192.0.2.1": ["a"]}, 100, reset=True)
        second = self.observe({"192.0.2.1": ["a"]}, 101)
        self.assertEqual(first["192.0.2.1"]["changes_60s"], 0)
        self.assertEqual(second["192.0.2.1"]["changes_60s"], 0)
        self.assertEqual(self.redis.expirations[self.key], LIFECYCLE_TTL_SECONDS)

    def test_change_persists_expires_and_multiple_changes_are_counted(self):
        self.observe({"host": ["a"]}, 100, reset=True)
        changed = self.observe({"host": ["b"]}, 110)
        held = self.observe({"host": ["b"]}, 140)
        twice = self.observe({"host": ["c"]}, 150)
        expired = self.observe({"host": ["c"]}, 211)
        self.assertEqual(changed["host"]["changes_60s"], 1)
        self.assertEqual(changed["host"]["seconds_since_last_change"], 0)
        self.assertEqual(held["host"]["seconds_since_last_change"], 30)
        self.assertEqual(twice["host"]["changes_60s"], 2)
        self.assertEqual(expired["host"]["changes_60s"], 0)

    def test_disconnect_gap_then_new_id_is_an_observed_change(self):
        self.observe({"host": ["a"]}, 100, reset=True)
        self.observe({}, 101)
        changed = self.observe({"host": ["b"]}, 102)
        self.assertEqual(changed["host"]["changes_60s"], 1)

    def test_parallel_connections_make_attribution_ambiguous(self):
        self.observe({"host": ["a"]}, 100, reset=True)
        ambiguous = self.observe({"host": ["a", "b"]}, 101)
        later = self.observe({"host": ["b"]}, 102)
        self.assertNotIn("host", ambiguous)
        self.assertEqual(later["host"]["changes_60s"], 0)

    def test_restart_baseline_does_not_create_change(self):
        self.observe({"host": ["a"]}, 100, reset=True)
        restarted = self.observe({"host": ["b"]}, 101, reset=True)
        self.assertEqual(restarted["host"]["changes_60s"], 0)

    def test_remote_host_ignores_ephemeral_ports(self):
        self.assertEqual(remote_host("192.0.2.1:50000"), "192.0.2.1")
        self.assertEqual(remote_host("192.0.2.1:50001"), "192.0.2.1")
        self.assertEqual(remote_host("[2001:db8::1]:1935"), "2001:db8::1")
        self.assertIsNone(remote_host(None))


if __name__ == "__main__":
    unittest.main()
