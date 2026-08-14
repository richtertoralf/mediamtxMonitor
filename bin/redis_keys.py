"""Pure builders for the existing MediaMTX Monitor Redis key schema."""

from __future__ import annotations


DEFAULT_STREAM_SNAPSHOT_KEY = "mediamtx:streams:latest"
DEFAULT_SYSTEM_SNAPSHOT_KEY = "mediamtx:system:latest"
DEFAULT_RTT_PUBLISHER_PREFIX = "rtt:pub"

_PUBLISHER_PREFIX = "pub"
_READER_PREFIX = "rd"
_SRT_HEALTH_PREFIX = "srt-health"
_CONNECTION_HISTORY_PREFIX = "history"
_BITRATE_PREV_BYTES = "prev_bytes"
_BITRATE_PREV_TS = "prev_ts"
_BITRATE_EWMA_MBPS = "ewma_mbps"
_RTT_EWMA_MS = "ewma_ms"
_RTT_LAST_MS = "last_ms"
_RTT_LAST_TS = "last_ts"


def publisher_connection_key(
    path: str, connection_type: str, connection_id: str
) -> str:
    """Build the existing publisher measurement identity."""
    return f"{_PUBLISHER_PREFIX}:{path}:{connection_type}:{connection_id}"


def reader_connection_key(
    path: str, connection_type: str, connection_id: str
) -> str:
    """Build the existing reader measurement identity."""
    return f"{_READER_PREFIX}:{path}:{connection_type}:{connection_id}"


def connection_history_key(connection_key: str) -> str:
    """Build the short-history key for an existing connection identity."""
    return f"{_CONNECTION_HISTORY_PREFIX}:{connection_key}"


def stream_snapshot_freshness_key(snapshot_key: str) -> str:
    """Build the collection-timestamp sidecar for a stream snapshot."""
    return f"{snapshot_key}:collected_at"


def bitrate_state_keys(base_key: str) -> tuple[str, str, str]:
    """Return previous-byte, timestamp, and EWMA keys for a connection."""
    return (
        f"{base_key}:{_BITRATE_PREV_BYTES}",
        f"{base_key}:{_BITRATE_PREV_TS}",
        f"{base_key}:{_BITRATE_EWMA_MBPS}",
    )


def publisher_rtt_keys(
    host: str, key_prefix: str = DEFAULT_RTT_PUBLISHER_PREFIX
) -> tuple[str, str, str]:
    """Return EWMA, last-value, and timestamp keys for publisher RTT."""
    base_key = f"{key_prefix}:{host}"
    return (
        f"{base_key}:{_RTT_EWMA_MS}",
        f"{base_key}:{_RTT_LAST_MS}",
        f"{base_key}:{_RTT_LAST_TS}",
    )


def publisher_srt_health_key(
    path: str, connection_type: str, connection_id: str
) -> str:
    """Build the SRT health-state base key for a publisher."""
    connection_key = publisher_connection_key(path, connection_type, connection_id)
    return f"{_SRT_HEALTH_PREFIX}:{connection_key}"


def reader_srt_health_key(
    path: str, connection_type: str, connection_id: str
) -> str:
    """Build the SRT health-state base key for a reader."""
    connection_key = reader_connection_key(path, connection_type, connection_id)
    return f"{_SRT_HEALTH_PREFIX}:{connection_key}"


def srt_counter_key(srt_health_key: str, counter: str) -> str:
    """Append a native MediaMTX SRT counter name to a health-state key."""
    return f"{srt_health_key}:{counter}"
