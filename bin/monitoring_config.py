"""
MediaMTX Monitor - shared runtime configuration.

Defines compatible defaults and normalizes configuration consumed by the
collector, API, and system monitor without initializing services or connections.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, Mapping, Optional

import yaml

try:
    from .redis_keys import DEFAULT_STREAM_SNAPSHOT_KEY, DEFAULT_SYSTEM_SNAPSHOT_KEY
except ImportError:
    from redis_keys import DEFAULT_STREAM_SNAPSHOT_KEY, DEFAULT_SYSTEM_SNAPSHOT_KEY


DEFAULT_CONFIG_PATH = Path(
    "/opt/mediamtx-monitoring-backend/config/collector.yaml"
)

MONITORING_DEFAULTS: Dict[str, Any] = {
    "api_base_url": "http://localhost:9997",
}

REDIS_DEFAULTS: Dict[str, Any] = {
    "host": "localhost",
    "port": 6379,
    "namespace": "mediamtx-monitor:",
    "key": DEFAULT_STREAM_SNAPSHOT_KEY,
}

NODE_DEFAULTS: Dict[str, Any] = {
    "id": "local",
}

LEGACY_STREAM_SNAPSHOT_KEY = "mediamtx:streams:latest"
LEGACY_SYSTEM_SNAPSHOT_KEY = "mediamtx:system:latest"
NODE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

COLLECTOR_DEFAULTS: Dict[str, Any] = {
    "output_json_path": "/tmp/mediamtx_streams.json",
    "interval_seconds": 1,
    "version_refresh_seconds": 60,
    "forward_refresh_seconds": 5,
    "output_refresh_seconds": 5,
    "ignore_path_prefixes": ["__preview__/"],
}

BITRATE_DEFAULTS: Dict[str, Any] = {
    "min_dt": 0.5,
    "smooth_alpha": 0.5,
    "smooth_reference_seconds": 5.0,
    "ttl": 300,
    "ignore_loopback": True,
}

SYSTEM_MONITOR_DEFAULTS: Dict[str, Any] = {
    "redis_key": DEFAULT_SYSTEM_SNAPSHOT_KEY,
    "output_json_path": "/tmp/mediamtx_system.json",
    "interval_seconds": 10,
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
    "snapshot_refresh_ms": 1000,
    "streamlist_refresh_ms": 1000,
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
    namespace = resolved["namespace"]
    if not isinstance(namespace, str):
        raise ValueError("redis.namespace muss eine nicht leere Zeichenkette sein.")
    namespace = namespace.strip().rstrip(":")
    if not namespace:
        raise ValueError("redis.namespace darf nicht leer sein.")
    resolved["namespace"] = f"{namespace}:"
    if resolved["key"] == LEGACY_STREAM_SNAPSHOT_KEY:
        resolved["key"] = DEFAULT_STREAM_SNAPSHOT_KEY
    return resolved


def resolve_node_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve the monitored node identity with a single-node default."""
    node_block = config.get("node")
    if node_block is None:
        return dict(NODE_DEFAULTS)
    if not isinstance(node_block, Mapping):
        raise ValueError("node muss ein YAML-Mapping mit einer gültigen id sein.")
    if "id" not in node_block:
        return dict(NODE_DEFAULTS)
    node_id = node_block["id"]
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValueError("node.id darf nicht leer sein.")
    node_id = node_id.strip()
    if NODE_ID_PATTERN.fullmatch(node_id) is None:
        raise ValueError(
            "node.id darf nur Buchstaben, Ziffern, Punkt, Unterstrich und "
            "Bindestrich enthalten."
        )
    return {"id": node_id}


def resolve_collector_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve collector scheduling, output, and filtering settings."""
    resolved = _component_config(config, "collector", COLLECTOR_DEFAULTS)
    resolved["interval_seconds"] = int(resolved["interval_seconds"])
    resolved["version_refresh_seconds"] = int(resolved["version_refresh_seconds"])
    resolved["forward_refresh_seconds"] = int(resolved["forward_refresh_seconds"])
    resolved["output_refresh_seconds"] = int(resolved["output_refresh_seconds"])
    resolved["ignore_path_prefixes"] = list(resolved["ignore_path_prefixes"])
    return resolved


def resolve_bitrate_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve bitrate calculation settings with compatible defaults."""
    resolved = _component_config(config, "bitrate", BITRATE_DEFAULTS)
    resolved["min_dt"] = float(resolved["min_dt"])
    if resolved["smooth_alpha"] is not None:
        resolved["smooth_alpha"] = float(resolved["smooth_alpha"])
    resolved["smooth_reference_seconds"] = float(
        resolved["smooth_reference_seconds"]
    )
    resolved["ttl"] = int(resolved["ttl"])
    resolved["ignore_loopback"] = bool(resolved["ignore_loopback"])
    return resolved


def resolve_system_monitor_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Resolve system-monitor settings with compatible defaults."""
    resolved = _component_config(config, "system_monitor", SYSTEM_MONITOR_DEFAULTS)
    resolved["interval_seconds"] = int(resolved["interval_seconds"])
    if resolved["redis_key"] == LEGACY_SYSTEM_SNAPSHOT_KEY:
        resolved["redis_key"] = DEFAULT_SYSTEM_SNAPSHOT_KEY
    return resolved


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
        "node": resolve_node_config(config),
        "collector": resolve_collector_config(config),
        "bitrate": resolve_bitrate_config(config),
        "system_monitor": resolve_system_monitor_config(config),
        "api_server": resolve_api_config(config),
        "logging": resolve_logging_config(config),
        "frontend": resolve_frontend_config(config),
    }
