"""
MediaMTX Monitor - protocol-specific metric mapping.

Maps only fields supplied by MediaMTX v1.20 into the normalized connection
contract. It does not calculate rates, persist state, or assess health.
"""

from __future__ import annotations

from typing import Any, Mapping


RTSP_SESSION_TYPES = frozenset({"rtspSession", "rtspsSession"})
RTMP_CONNECTION_TYPES = frozenset({"rtmpConn", "rtmpsConn"})

COUNTER_FIELDS: dict[tuple[str, str], dict[str, str]] = {
    ("rtsp", "publisher"): {
        "loss": "inboundRTPPacketsLost",
        "rtp_error": "inboundRTPPacketsInError",
        "rtcp_error": "inboundRTCPPacketsInError",
    },
    ("rtsp", "reader"): {
        "reported_loss": "outboundRTPPacketsReportedLost",
        "discard": "outboundRTPPacketsDiscarded",
    },
    ("webrtc", "publisher"): {
        "rtp_loss": "inboundRTPPacketsLost",
    },
    ("webrtc", "reader"): {
        "frame_discard": "outboundFramesDiscarded",
    },
    ("rtmp", "reader"): {
        "frame_discard": "outboundFramesDiscarded",
    },
}


def protocol_family(connection_type: str | None) -> str | None:
    if connection_type in RTSP_SESSION_TYPES:
        return "rtsp"
    if connection_type in RTMP_CONNECTION_TYPES:
        return "rtmp"
    if connection_type == "webRTCSession":
        return "webrtc"
    if connection_type == "hlsSession":
        return "hls"
    if connection_type == "moqSession":
        return "moq"
    return None


def counter_fields(
    connection_type: str | None, direction: str
) -> Mapping[str, str]:
    family = protocol_family(connection_type)
    return COUNTER_FIELDS.get((family or "", direction), {})


def build_protocol_metrics(
    connection_type: str | None,
    details: Mapping[str, Any],
    direction: str,
    deltas: Mapping[str, int],
) -> dict[str, Any]:
    """Build available protocol gauges, metadata, and interval counters."""
    family = protocol_family(connection_type)
    if family is None:
        return {}
    metrics: dict[str, Any] = {"family": family}
    if deltas:
        metrics["counter_deltas"] = dict(deltas)

    gauges: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    if family in {"rtsp", "webrtc"} and direction == "publisher":
        if details.get("inboundRTPPacketsJitter") is not None:
            gauges["jitter_ms"] = details["inboundRTPPacketsJitter"]
    if family == "rtsp" and details.get("transport") is not None:
        metadata["transport"] = details["transport"]
    if family == "webrtc":
        for source, target in (
            ("peerConnectionEstablished", "peer_connection_established"),
            ("state", "state"),
            ("localCandidate", "local_candidate"),
            ("remoteCandidate", "remote_candidate"),
        ):
            if details.get(source) is not None:
                metadata[target] = details[source]
    if family in {"rtmp", "moq"} and details.get("state") is not None:
        metadata["state"] = details["state"]
    if family == "moq":
        for field in ("transport", "version"):
            if details.get(field) is not None:
                metadata[field] = details[field]
    if gauges:
        metrics["gauges"] = gauges
    if metadata:
        metrics["metadata"] = metadata
    return metrics if len(metrics) > 1 else {}


def build_common_metrics(
    connection_type: str | None,
    details: Mapping[str, Any],
    direction: str,
    bitrate_mbps: Any,
) -> dict[str, Any]:
    """Build the common directional connection contract from available data."""
    common: dict[str, Any] = {
        "protocol": protocol_family(connection_type) or connection_type,
        "direction": "IN" if direction == "publisher" else "OUT",
    }
    for field in ("remoteAddr", "created", "state", "inboundBytes", "outboundBytes"):
        if details.get(field) is not None:
            common[field] = details[field]
    if bitrate_mbps is not None:
        common["rx_mbit_s" if direction == "publisher" else "tx_mbit_s"] = bitrate_mbps
    byte_field = "inboundBytes" if direction == "publisher" else "outboundBytes"
    if details.get(byte_field) is not None:
        common["total_bytes"] = details[byte_field]
    return common
