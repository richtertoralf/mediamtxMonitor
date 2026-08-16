"""Pure builders for the existing MediaMTX Monitor Redis key schema."""

from __future__ import annotations


DEFAULT_STREAM_SNAPSHOT_KEY = "mediamtx:streams:latest"
DEFAULT_SYSTEM_SNAPSHOT_KEY = "mediamtx:system:latest"

_PUBLISHER_PREFIX = "pub"
_READER_PREFIX = "rd"
_SRT_HEALTH_PREFIX = "srt-health"
_CONNECTION_HISTORY_PREFIX = "history"
_BITRATE_PREV_BYTES = "prev_bytes"
_BITRATE_PREV_TS = "prev_ts"
_BITRATE_EWMA_MBPS = "ewma_mbps"
_RTMP_FRAME_DISCARD = "rtmp_frame_discard"
_CONNECTION_LIFECYCLE_PREFIX = "lifecycle"
_COUNTER_STATE_SUFFIX = "counters"
_PATH_PREFIX = "path"
_HLS_MUXER_PREFIX = "hls-muxer"


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


def rtmp_frame_discard_key(reader_key: str) -> str:
    """Build the cumulative RTMP reader frame-discard state key."""
    return f"{reader_key}:{_RTMP_FRAME_DISCARD}"


def connection_counter_key(connection_key: str) -> str:
    """Build the shared non-SRT cumulative-counter state base key."""
    return f"{connection_key}:{_COUNTER_STATE_SUFFIX}"


def path_metric_key(path: str, source_identity: str | None = None) -> str:
    """Build Path metric state, optionally scoped to its current source."""
    base = f"{_PATH_PREFIX}:{path}"
    return f"{base}:{source_identity}" if source_identity else base


def hls_muxer_metric_key(path: str, created: str | None = None) -> str:
    """Build one path-scoped HLS muxer generation identity."""
    base = f"{_HLS_MUXER_PREFIX}:{path}"
    return f"{base}:{created}" if created else base


def connection_lifecycle_key(path: str, role: str, connection_type: str) -> str:
    """Build short-lived lifecycle state shared across connection IDs."""
    return f"{_CONNECTION_LIFECYCLE_PREFIX}:{role}:{path}:{connection_type}"
