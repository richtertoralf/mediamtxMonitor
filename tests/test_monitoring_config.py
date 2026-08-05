import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from monitoring_config import (  # noqa: E402
    RTT_DEFAULTS,
    SYSTEM_MONITOR_DEFAULTS,
    measure_configured_rtt,
    resolve_rtt_config,
    resolve_system_monitor_config,
)


class SystemMonitorConfigTests(unittest.TestCase):
    def test_defaults_without_block(self):
        self.assertEqual(resolve_system_monitor_config({}), SYSTEM_MONITOR_DEFAULTS)

    def test_all_values_come_from_system_monitor_block(self):
        config = {"system_monitor": {
            "redis_key": "test:system:snapshot",
            "output_json_path": "/tmp/test-system.json",
            "interval_seconds": 47,
        }}
        resolved = resolve_system_monitor_config(config)
        self.assertEqual(resolved["redis_key"], "test:system:snapshot")
        self.assertEqual(resolved["output_json_path"], "/tmp/test-system.json")
        self.assertEqual(resolved["interval_seconds"], 47)

    def test_system_monitor_and_api_share_resolved_redis_key(self):
        config = {"system_monitor": {"redis_key": "test:shared:system"}}
        system_monitor_key = resolve_system_monitor_config(config)["redis_key"]
        api_key = resolve_system_monitor_config(config)["redis_key"]
        self.assertEqual(system_monitor_key, api_key)


class RttConfigTests(unittest.TestCase):
    def test_defaults_match_previous_runtime_behavior(self):
        expected = {
            "enabled": True,
            "ewma_alpha": 0.5,
            "min_period_s": 30,
            "ttl_s": 300,
            "timeout_s": 0.9,
            "key_prefix": "rtt:pub",
        }
        self.assertEqual(resolve_rtt_config({}), expected)
        self.assertEqual(resolve_rtt_config({}), RTT_DEFAULTS)

    def test_disabled_does_not_call_measurement(self):
        calls = []
        result = measure_configured_rtt(
            object(), "192.0.2.10:1234",
            resolve_rtt_config({"rtt": {"enabled": False}}),
            lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        self.assertIsNone(result)
        self.assertEqual(calls, [])

    def test_enabled_passes_all_six_values(self):
        calls = []

        def fake_measure(redis_client, **kwargs):
            calls.append((redis_client, kwargs))
            return 12.5

        redis_client = object()
        config = resolve_rtt_config({"rtt": {
            "enabled": True,
            "ewma_alpha": 0.25,
            "min_period_s": 17,
            "ttl_s": 91,
            "timeout_s": 1.75,
            "key_prefix": "test:rtt",
        }})
        result = measure_configured_rtt(
            redis_client, "192.0.2.10:1234", config, fake_measure
        )
        self.assertEqual(result, 12.5)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], redis_client)
        self.assertEqual(calls[0][1], {
            "remote_addr": "192.0.2.10:1234",
            "ewma_alpha": 0.25,
            "min_period_s": 17,
            "ttl_s": 91,
            "timeout_s": 1.75,
            "key_prefix": "test:rtt",
        })

    def test_zero_ewma_alpha_is_preserved(self):
        calls = []

        def fake_measure(redis_client, **kwargs):
            calls.append(kwargs)
            return None

        config = resolve_rtt_config({"rtt": {"ewma_alpha": 0.0}})
        measure_configured_rtt(object(), "192.0.2.10", config, fake_measure)
        self.assertEqual(config["ewma_alpha"], 0.0)
        self.assertEqual(calls[0]["ewma_alpha"], 0.0)


if __name__ == "__main__":
    unittest.main()
