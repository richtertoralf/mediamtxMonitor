"""Nebenwirkungsfreie Auflösung gemeinsam verwendeter Monitoring-Konfiguration."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional


SYSTEM_MONITOR_DEFAULTS: Dict[str, Any] = {
    "redis_key": "mediamtx:system:latest",
    "output_json_path": "/tmp/mediamtx_system.json",
    "interval_seconds": 10,
}

RTT_DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "ewma_alpha": 0.5,
    "min_period_s": 30,
    "ttl_s": 300,
    "timeout_s": 0.9,
    "key_prefix": "rtt:pub",
}


def _component_config(
    config: Mapping[str, Any], block_name: str, defaults: Mapping[str, Any]
) -> Dict[str, Any]:
    block = config.get(block_name, {}) or {}
    return {key: block.get(key, default) for key, default in defaults.items()}


def resolve_system_monitor_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Löst den ``system_monitor``-Block mit kompatiblen Defaults auf."""
    return _component_config(config, "system_monitor", SYSTEM_MONITOR_DEFAULTS)


def resolve_rtt_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Löst den ``rtt``-Block mit den bisher wirksamen Defaults auf."""
    return _component_config(config, "rtt", RTT_DEFAULTS)


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
