"""Nebenwirkungsfreie Auflösung gemeinsam verwendeter Monitoring-Konfiguration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import yaml

try:
    from .redis_keys import (
        DEFAULT_RTT_PUBLISHER_PREFIX,
        DEFAULT_STREAM_SNAPSHOT_KEY,
        DEFAULT_SYSTEM_SNAPSHOT_KEY,
    )
except ImportError:
    from redis_keys import (
        DEFAULT_RTT_PUBLISHER_PREFIX,
        DEFAULT_STREAM_SNAPSHOT_KEY,
        DEFAULT_SYSTEM_SNAPSHOT_KEY,
    )


DEFAULT_CONFIG_PATH = Path(
    "/opt/mediamtx-monitoring-backend/config/collector.yaml"
)

MONITORING_DEFAULTS: Dict[str, Any] = {
    "api_base_url": "http://localhost:9997",
}

REDIS_DEFAULTS: Dict[str, Any] = {
    "host": "localhost",
    "port": 6379,
    "key": DEFAULT_STREAM_SNAPSHOT_KEY,
}

COLLECTOR_DEFAULTS: Dict[str, Any] = {
    "output_json_path": "/tmp/mediamtx_streams.json",
    "interval_seconds": 10,
    "ignore_path_prefixes": ["__preview__/"],
}

BITRATE_DEFAULTS: Dict[str, Any] = {
    "min_dt": 0.5,
    "smooth_alpha": 0.5,
    "ttl": 300,
    "ignore_loopback": True,
}

SYSTEM_MONITOR_DEFAULTS: Dict[str, Any] = {
    "redis_key": DEFAULT_SYSTEM_SNAPSHOT_KEY,
    "output_json_path": "/tmp/mediamtx_system.json",
    "interval_seconds": 10,
}

RTT_DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "ewma_alpha": 0.5,
    "min_period_s": 30,
    "ttl_s": 300,
    "timeout_s": 0.9,
    "key_prefix": DEFAULT_RTT_PUBLISHER_PREFIX,
}

API_DEFAULTS: Dict[str, Any] = {
    "listen_host": "127.0.0.1",
    "listen_port": 8080,
    "static_dir": "/opt/mediamtx-monitoring-backend/static",
    "index_file": "index.html",
}

LOGGING_DEFAULTS: Dict[str, Any] = {
    "level": "INFO",
}

FRONTEND_DEFAULTS: Dict[str, Any] = {
    "snapshot_refresh_ms": 2000,
    "streamlist_refresh_ms": 5000,
}


def _component_config(
    config: Mapping[str, Any], block_name: str, defaults: Mapping[str, Any]
) -> Dict[str, Any]:
    block = config.get(block_name, {}) or {}
    if not isinstance(block, Mapping):
        block = {}
    return {key: block.get(key, default) for key, default in defaults.items()}


def load_monitoring_config(
    path: Path | str = DEFAULT_CONFIG_PATH,
) -> Dict[str, Any]:
    """Load the raw YAML configuration without applying runtime defaults."""
    with Path(path).open("r", encoding="utf-8") as config_file:
        loaded = yaml.safe_load(config_file) or {}
    if not isinstance(loaded, Mapping):
        raise ValueError("Die Monitoring-Konfiguration muss ein YAML-Mapping sein.")
    return dict(loaded)


def resolve_redis_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve the shared Redis connection and stream snapshot settings."""
    resolved = _component_config(config, "redis", REDIS_DEFAULTS)
    resolved["port"] = int(resolved["port"])
    return resolved


def resolve_collector_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve collector scheduling, output, and filtering settings."""
    resolved = _component_config(config, "collector", COLLECTOR_DEFAULTS)
    resolved["interval_seconds"] = int(resolved["interval_seconds"])
    resolved["ignore_path_prefixes"] = list(resolved["ignore_path_prefixes"])
    return resolved


def resolve_bitrate_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve bitrate calculation settings with compatible defaults."""
    resolved = _component_config(config, "bitrate", BITRATE_DEFAULTS)
    resolved["min_dt"] = float(resolved["min_dt"])
    if resolved["smooth_alpha"] is not None:
        resolved["smooth_alpha"] = float(resolved["smooth_alpha"])
    resolved["ttl"] = int(resolved["ttl"])
    resolved["ignore_loopback"] = bool(resolved["ignore_loopback"])
    return resolved


def resolve_system_monitor_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Löst den ``system_monitor``-Block mit kompatiblen Defaults auf."""
    resolved = _component_config(config, "system_monitor", SYSTEM_MONITOR_DEFAULTS)
    resolved["interval_seconds"] = int(resolved["interval_seconds"])
    return resolved


def resolve_rtt_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Löst den ``rtt``-Block mit den bisher wirksamen Defaults auf."""
    return _component_config(config, "rtt", RTT_DEFAULTS)


def resolve_api_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve direct API server settings and documented static-file values."""
    resolved = _component_config(config, "api_server", API_DEFAULTS)
    resolved["listen_port"] = int(resolved["listen_port"])
    return resolved


def resolve_logging_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve the logging block currently consumed by the API service."""
    return _component_config(config, "logging", LOGGING_DEFAULTS)


def resolve_frontend_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve refresh values exposed by the monitoring API."""
    resolved = _component_config(config, "frontend", FRONTEND_DEFAULTS)
    resolved["snapshot_refresh_ms"] = int(resolved["snapshot_refresh_ms"])
    resolved["streamlist_refresh_ms"] = int(resolved["streamlist_refresh_ms"])
    return resolved


def resolve_monitoring_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the normalized runtime configuration without mutating raw input."""
    return {
        "api_base_url": config.get(
            "api_base_url", MONITORING_DEFAULTS["api_base_url"]
        ),
        "redis": resolve_redis_config(config),
        "collector": resolve_collector_config(config),
        "bitrate": resolve_bitrate_config(config),
        "rtt": resolve_rtt_config(config),
        "system_monitor": resolve_system_monitor_config(config),
        "api_server": resolve_api_config(config),
        "logging": resolve_logging_config(config),
        "frontend": resolve_frontend_config(config),
    }


def measure_configured_rtt(
    redis_client: Any,
    remote_addr: str,
    rtt_config: Mapping[str, Any],
    measure_func: Callable[..., Optional[float]],
) -> Optional[float]:
    """Führt eine RTT-Messung nur aus, wenn sie konfiguriert aktiviert ist."""
    if not rtt_config["enabled"]:
        return None

    return measure_func(
        redis_client,
        remote_addr=remote_addr,
        ewma_alpha=float(rtt_config["ewma_alpha"]),
        min_period_s=int(rtt_config["min_period_s"]),
        ttl_s=int(rtt_config["ttl_s"]),
        key_prefix=str(rtt_config["key_prefix"]),
        timeout_s=float(rtt_config["timeout_s"]),
    )
