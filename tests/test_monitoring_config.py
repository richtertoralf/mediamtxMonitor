import copy
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from monitoring_config import (  # noqa: E402
    API_DEFAULTS,
    BITRATE_DEFAULTS,
    COLLECTOR_DEFAULTS,
    FRONTEND_DEFAULTS,
    LOGGING_DEFAULTS,
    MONITORING_DEFAULTS,
    REDIS_DEFAULTS,
    SYSTEM_MONITOR_DEFAULTS,
    load_monitoring_config,
    resolve_api_config,
    resolve_bitrate_config,
    resolve_collector_config,
    resolve_frontend_config,
    resolve_logging_config,
    resolve_monitoring_config,
    resolve_redis_config,
    resolve_system_monitor_config,
)


class MonitoringConfigTests(unittest.TestCase):
    def test_complete_default_resolution(self):
        self.assertEqual(resolve_monitoring_config({}), {
            "api_base_url": MONITORING_DEFAULTS["api_base_url"],
            "redis": REDIS_DEFAULTS,
            "collector": COLLECTOR_DEFAULTS,
            "bitrate": BITRATE_DEFAULTS,
            "system_monitor": SYSTEM_MONITOR_DEFAULTS,
            "api_server": API_DEFAULTS,
            "logging": LOGGING_DEFAULTS,
            "frontend": FRONTEND_DEFAULTS,
        })

    def test_partial_configuration_keeps_component_defaults(self):
        resolved = resolve_monitoring_config({
            "api_base_url": "http://media.example:9997",
            "redis": {"host": "redis.example"},
            "collector": {"interval_seconds": 7},
            "api_server": {"listen_port": 9090},
        })

        self.assertEqual(resolved["api_base_url"], "http://media.example:9997")
        self.assertEqual(resolved["redis"], {
            "host": "redis.example",
            "port": 6379,
            "key": "mediamtx:streams:latest",
        })
        self.assertEqual(resolved["collector"]["interval_seconds"], 7)
        self.assertEqual(
            resolved["collector"]["output_json_path"],
            "/tmp/mediamtx_streams.json",
        )
        self.assertEqual(resolved["api_server"]["listen_port"], 9090)
        self.assertEqual(resolved["api_server"]["listen_host"], "127.0.0.1")

    def test_component_resolvers_normalize_values(self):
        config = {
            "redis": {"host": "cache", "port": "6380", "key": "streams"},
            "collector": {
                "interval_seconds": "12",
                "ignore_path_prefixes": ["internal/"],
            },
            "bitrate": {
                "min_dt": "1.25",
                "smooth_alpha": None,
                "ttl": "90",
                "ignore_loopback": False,
            },
            "system_monitor": {"interval_seconds": "15"},
            "api_server": {"listen_port": "8081"},
            "frontend": {
                "snapshot_refresh_ms": "1000",
                "streamlist_refresh_ms": "3000",
            },
            "logging": {"level": "DEBUG"},
        }

        self.assertEqual(resolve_redis_config(config)["port"], 6380)
        self.assertEqual(resolve_collector_config(config)["interval_seconds"], 12)
        self.assertEqual(resolve_bitrate_config(config), {
            "min_dt": 1.25,
            "smooth_alpha": None,
            "smooth_reference_seconds": 5.0,
            "ttl": 90,
            "ignore_loopback": False,
        })
        self.assertEqual(
            resolve_system_monitor_config(config)["interval_seconds"], 15
        )
        self.assertEqual(resolve_api_config(config)["listen_port"], 8081)
        self.assertEqual(resolve_frontend_config(config), {
            "snapshot_refresh_ms": 1000,
            "streamlist_refresh_ms": 3000,
        })
        self.assertEqual(resolve_logging_config(config)["level"], "DEBUG")

    def test_invalid_optional_blocks_fall_back_to_defaults(self):
        config = {
            "redis": [],
            "collector": "invalid",
            "bitrate": 42,
            "system_monitor": None,
            "api_server": [],
            "logging": "invalid",
            "frontend": 3.14,
        }
        resolved = resolve_monitoring_config(config)

        self.assertEqual(resolved["redis"], REDIS_DEFAULTS)
        self.assertEqual(resolved["collector"], COLLECTOR_DEFAULTS)
        self.assertEqual(resolved["bitrate"], BITRATE_DEFAULTS)
        self.assertEqual(resolved["system_monitor"], SYSTEM_MONITOR_DEFAULTS)
        self.assertEqual(resolved["api_server"], API_DEFAULTS)
        self.assertEqual(resolved["logging"], LOGGING_DEFAULTS)
        self.assertEqual(resolved["frontend"], FRONTEND_DEFAULTS)

    def test_resolution_does_not_mutate_raw_configuration(self):
        raw = {
            "redis": {"port": "6380"},
            "collector": {"ignore_path_prefixes": ["private/"]},
            "bitrate": {"smooth_alpha": "0.25"},
        }
        before = copy.deepcopy(raw)

        resolved = resolve_monitoring_config(raw)
        resolved["collector"]["ignore_path_prefixes"].append("changed/")

        self.assertEqual(raw, before)

    def test_yaml_loader_returns_raw_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "collector.yaml"
            path.write_text("redis:\n  host: test-cache\n", encoding="utf-8")

            self.assertEqual(
                load_monitoring_config(path),
                {"redis": {"host": "test-cache"}},
            )

    def test_all_services_share_the_same_redis_contract(self):
        config = {
            "redis": {
                "host": "shared-cache",
                "port": 6390,
                "key": "shared:streams",
            }
        }
        normalized = resolve_monitoring_config(config)

        self.assertEqual(normalized["redis"], resolve_redis_config(config))
        self.assertEqual(normalized["redis"]["host"], "shared-cache")
        self.assertEqual(normalized["redis"]["port"], 6390)
        self.assertEqual(normalized["redis"]["key"], "shared:streams")


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


if __name__ == "__main__":
    unittest.main()
