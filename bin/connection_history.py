"""
MediaMTX Monitor - short connection history.

Builds compact samples from normalized publisher and reader connections.
History is live-only and intentionally limited to about one minute; it neither
defines the current snapshot nor infers reconnects or connection lifecycle.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


HISTORY_RETENTION_SECONDS = 65
HISTORY_TTL_SECONDS = 120

_SRT_EVENT_FIELDS = (
    "retrans_packets",
    "loss_packets",
    "drop_packets",
    "belated_packets",
    "undecrypt_packets",
)

_FRAME_DISCARD_FIELD = "frame_discard_delta"

_PROTOCOL_COUNTERS_FIELD = "protocol_counter_deltas"
_JITTER_FIELD = "jitter_ms"

_WINDOW_SECONDS = (10, 60)


def build_history_sample(
    connection: Mapping[str, Any],
    direction: str,
    timestamp: float,
) -> dict[str, Any]:
    """Return a compact sample containing only available normalized metrics."""
    sample: dict[str, Any] = {"timestamp": timestamp}
    rate_name = "rx_mbps" if direction == "publisher" else "tx_mbps"
    bitrate = connection.get("bitrate_mbps")
    if bitrate is not None:
        sample[rate_name] = bitrate

    if connection.get("transport_rtt_ms") is not None:
        sample["transport_rtt_ms"] = connection["transport_rtt_ms"]

    if connection.get("srt_latency_ms") is not None:
        sample["srt_latency_ms"] = connection["srt_latency_ms"]

    srt_metrics = connection.get("srt_health", {}) or {}
    if srt_metrics.get("link_capacity_mbps") is not None:
        sample["link_capacity_mbps"] = srt_metrics["link_capacity_mbps"]
    for field in _SRT_EVENT_FIELDS:
        if srt_metrics.get(field) is not None:
            sample[field] = srt_metrics[field]

    if connection.get(_FRAME_DISCARD_FIELD) is not None:
        sample[_FRAME_DISCARD_FIELD] = connection[_FRAME_DISCARD_FIELD]

    protocol_metrics = connection.get("protocol_metrics", {}) or {}
    gauges = protocol_metrics.get("gauges", {}) or {}
    if gauges.get(_JITTER_FIELD) is not None:
        sample[_JITTER_FIELD] = gauges[_JITTER_FIELD]
    deltas = dict(protocol_metrics.get("counter_deltas", {}) or {})
    if connection.get(_FRAME_DISCARD_FIELD) is not None:
        deltas.pop("frame_discard", None)
    if deltas:
        sample[_PROTOCOL_COUNTERS_FIELD] = dict(deltas)

    return sample


def _numeric_values(
    samples: list[Mapping[str, Any]], field: str
) -> list[float]:
    values = []
    for sample in samples:
        value = sample.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
            if math.isfinite(number):
                values.append(number)
    return values


def _percentile(values: list[float], percentile: float) -> float:
    """Return a linearly interpolated percentile for one or more values."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_history(
    samples: list[Mapping[str, Any]], timestamp: float
) -> dict[str, Any]:
    """Calculate optional 10- and 60-second timing and event summaries."""
    timing_field = None
    if any(sample.get("transport_rtt_ms") is not None for sample in samples):
        timing_field = "transport_rtt_ms"

    timing = {}
    events = {}
    for seconds in _WINDOW_SECONDS:
        window_name = f"{seconds}s"
        window = [
            sample
            for sample in samples
            if isinstance(sample.get("timestamp"), (int, float))
            and sample["timestamp"] > timestamp - seconds
            and sample["timestamp"] <= timestamp
        ]

        if timing_field is not None:
            values = _numeric_values(window, timing_field)
            if values:
                p50 = round(_percentile(values, 0.50), 2)
                p95 = round(_percentile(values, 0.95), 2)
                timing[window_name] = {
                    "sample_count": len(values),
                    "p50_ms": p50,
                    "p95_ms": p95,
                    "variation_ms": round(p95 - p50, 2),
                }

        event_window = {}
        for field in _SRT_EVENT_FIELDS:
            values = _numeric_values(window, field)
            if values:
                event_window[field] = round(sum(values), 2)
        if event_window:
            events[window_name] = event_window

    summary: dict[str, Any] = {}
    if timing:
        summary["timing_source"] = timing_field
        summary["timing"] = timing
        if "10s" in timing and "60s" in timing:
            summary["p50_delta_ms"] = round(
                timing["10s"]["p50_ms"] - timing["60s"]["p50_ms"], 2
            )
    if events:
        summary["events"] = events

    frame_discard = {}
    for seconds in _WINDOW_SECONDS:
        values = _numeric_values(
            [
                sample
                for sample in samples
                if isinstance(sample.get("timestamp"), (int, float))
                and sample["timestamp"] > timestamp - seconds
                and sample["timestamp"] <= timestamp
            ],
            _FRAME_DISCARD_FIELD,
        )
        if values:
            frame_discard[f"{seconds}s"] = int(sum(values))
    if frame_discard:
        summary["frame_discard"] = frame_discard

    jitter = {}
    protocol_counters = {}
    for seconds in _WINDOW_SECONDS:
        window_name = f"{seconds}s"
        window = [
            sample for sample in samples
            if isinstance(sample.get("timestamp"), (int, float))
            and sample["timestamp"] > timestamp - seconds
            and sample["timestamp"] <= timestamp
        ]
        jitter_values = _numeric_values(window, _JITTER_FIELD)
        if jitter_values:
            p50 = round(_percentile(jitter_values, 0.50), 2)
            p95 = round(_percentile(jitter_values, 0.95), 2)
            jitter[window_name] = {
                "sample_count": len(jitter_values),
                "current_ms": round(jitter_values[-1], 2),
                "p50_ms": p50,
                "p95_ms": p95,
                "variation_ms": round(p95 - p50, 2),
            }
        names = {
            name
            for sample in window
            for name in (sample.get(_PROTOCOL_COUNTERS_FIELD, {}) or {})
        }
        values_by_name = {}
        for name in names:
            values = _numeric_values(
                [sample.get(_PROTOCOL_COUNTERS_FIELD, {}) or {} for sample in window],
                name,
            )
            if values:
                values_by_name[name] = int(sum(values))
        if values_by_name:
            protocol_counters[window_name] = values_by_name
    if jitter:
        summary["jitter"] = jitter
    if protocol_counters:
        summary["protocol_counters"] = protocol_counters
    return summary


def rate_history(
    samples: list[Mapping[str, Any]], direction: str
) -> list[dict[str, Any]]:
    """Return compact rate points, retaining missing samples as graph gaps."""
    field = "rx_mbps" if direction == "publisher" else "tx_mbps"
    points = []
    for sample in samples:
        timestamp = sample.get("timestamp")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            continue
        values = _numeric_values([sample], field)
        points.append({
            "timestamp": float(timestamp),
            "mbps": round(values[0], 2) if values else None,
        })
    return points


def average_rate(
    samples: list[Mapping[str, Any]],
    direction: str,
    timestamp: float,
    seconds: int,
    *,
    minimum_samples: int = 2,
) -> dict[str, Any] | None:
    """Return an arithmetic rate mean from one existing time window."""
    field = "rx_mbps" if direction == "publisher" else "tx_mbps"
    window = [
        sample
        for sample in samples
        if isinstance(sample.get("timestamp"), (int, float))
        and not isinstance(sample.get("timestamp"), bool)
        and sample["timestamp"] > timestamp - seconds
        and sample["timestamp"] <= timestamp
    ]
    values = _numeric_values(window, field)
    if len(values) < minimum_samples:
        return None
    return {
        "average_mbps": round(sum(values) / len(values), 2),
        "sample_count": len(values),
    }


def jitter_history(samples: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return available native jitter gauges for a compact 60-second trend."""
    points = []
    for sample in samples:
        timestamp = sample.get("timestamp")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            continue
        values = _numeric_values([sample], _JITTER_FIELD)
        points.append({
            "timestamp": float(timestamp),
            "ms": round(values[0], 2) if values else None,
        })
    return points
