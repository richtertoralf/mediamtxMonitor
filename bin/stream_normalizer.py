"""
MediaMTX Monitor - Stream normalization.

Transforms raw MediaMTX path and connection data into the stable monitoring
snapshot structure.

Responsibilities:
- Join paths, publishers, and readers with indexed connection details.
- Build the existing base stream, track, and media representation.
- Provide the stable connection identity fallback used by metric enrichment.

Does not:
- Perform HTTP requests or persist snapshots.
- Calculate bitrate, RTT, SRT counters, or health.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

try:
    from .mediamtx_model import (
        build_media_model,
        get_details_by_type,
        track_codecs,
    )
except ImportError:
    from mediamtx_model import build_media_model, get_details_by_type, track_codecs


def normalize_publisher(
    source: Mapping[str, Any], details: Mapping[str, Any]
) -> dict[str, Any]:
    """Join a raw Path source reference with its connection details."""
    source_type: Optional[str] = source.get("type")
    source_id: Optional[str] = source.get("id")
    return {
        "type": source_type,
        "id": source_id,
        "details": get_details_by_type(source_type, source_id, details),
    }


def normalize_reader(
    reader: Mapping[str, Any], details: Mapping[str, Any]
) -> dict[str, Any]:
    """Join a raw Path reader reference with its connection details."""
    reader_type: Optional[str] = reader.get("type")
    reader_id: Optional[str] = reader.get("id")
    return {
        "type": reader_type,
        "id": reader_id,
        "details": get_details_by_type(reader_type, reader_id, details),
    }


def connection_identity(connection: Mapping[str, Any]) -> Any:
    """Return the existing ID, remote-address, then ``n/a`` identity fallback."""
    return connection.get("id") or connection.get("details", {}).get(
        "remoteAddr"
    ) or "n/a"


def sanitize_forward_destinations(destinations: Any) -> list[dict[str, Any]]:
    """Expose only non-sensitive v1.21 forward-destination observations."""
    if not isinstance(destinations, list):
        return []
    safe: list[dict[str, Any]] = []
    for destination in destinations:
        if not isinstance(destination, Mapping):
            continue
        item: dict[str, Any] = {}
        for field in ("id", "pos", "type", "state", "outboundBytes", "created"):
            if field in destination:
                item[field] = destination[field]
        if item:
            safe.append(item)
    return safe


def normalize_stream(
    path: Mapping[str, Any],
    details: Mapping[str, Any],
    mediamtx_version: Any,
    forward_destinations: Any,
) -> dict[str, Any]:
    """Build the existing base snapshot object for one raw MediaMTX path."""
    source = path.get("source", {}) or {}
    readers = path.get("readers", []) or []
    tracks2 = path.get("tracks2", []) or []

    normalized = {
        "name": path.get("name", ""),
        "mediamtxVersion": mediamtx_version,
        "source": normalize_publisher(source, details),
        "tracks2": tracks2,
        "tracks": track_codecs(tracks2),
        "media": build_media_model(tracks2),
        "inboundBytes": int(path.get("inboundBytes") or 0),
        "outboundBytes": int(path.get("outboundBytes") or 0),
        "inboundFramesInError": int(path.get("inboundFramesInError") or 0),
        "forwardDestinations": sanitize_forward_destinations(forward_destinations),
        "readers": [normalize_reader(reader, details) for reader in readers],
    }
    # MediaMTX v1.21 exposes the current path state as available/online.
    # Both fields are optional in fixtures because a missing observation must
    # remain distinguishable from an explicit false value.
    for field in ("available", "online"):
        if field in path:
            normalized[field] = bool(path.get(field))
    return normalized
