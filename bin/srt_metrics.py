"""
MediaMTX Monitor - native SRT metrics.

Builds the existing directional SRT metric contract from MediaMTX-provided
rates, link capacity, transport RTT, and reset-safe counter deltas. Publisher
and reader counters use separate native field mappings and persisted state.

Does not classify connection health as OK, WARN, or CRIT.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

try:
    from .redis_keys import srt_counter_key
except ImportError:
    from redis_keys import srt_counter_key


PUBLISHER_COUNTERS = {
    "retrans_packets": "packetsReceivedRetrans",
    "drop_packets": "packetsReceivedDrop",
    "belated_packets": "packetsReceivedBelated",
    "loss_packets": "packetsReceivedLoss",
    "unique_packets": "packetsReceivedUnique",
    "undecrypt_packets": "packetsReceivedUndecrypt",
}

READER_COUNTERS = {
    "retrans_packets": "packetsRetrans",
    "drop_packets": "packetsSendDrop",
    "loss_packets": "packetsSendLoss",
    "sent_packets": "packetsSent",
    "unique_packets": "packetsSentUnique",
}


def counter_delta(redis_client, key: str, value: Any, ttl: int) -> Optional[int]:
    """Store a cumulative SRT counter and return its non-negative delta."""
    if value is None:
        return None

    try:
        current = int(value)
        previous = redis_client.get(key)
        redis_client.set(key, current, ex=ttl)
        if previous is None:
            return None
        delta = current - int(previous)
        return delta if delta >= 0 else None
    except (TypeError, ValueError) as exc:
        logging.debug("Ungültiger SRT-Zähler %s=%r: %s", key, value, exc)
        return None
    except Exception as exc:
        logging.debug("SRT-Zählerzustand konnte nicht verarbeitet werden (%s): %s", key, exc)
        return None


def build_srt_health(
    redis_client,
    *,
    key: str,
    details: Dict[str, Any],
    direction: str,
    ttl: int,
    transport_rtt_ms: Any = None,
) -> Dict[str, Any]:
    """Build the existing SRT metric contract for a publisher or reader."""
    if direction == "publisher":
        rate_name = "rx_mbps"
        rate_field = "mbpsReceiveRate"
        counters = PUBLISHER_COUNTERS
    elif direction == "reader":
        rate_name = "tx_mbps"
        rate_field = "mbpsSendRate"
        counters = READER_COUNTERS
    else:
        raise ValueError(f"Unbekannte SRT-Richtung: {direction}")

    health: Dict[str, Any] = {}
    rate = _positive_number(details.get(rate_field))
    link = _positive_number(details.get("mbpsLinkCapacity"))
    rtt = _positive_number(
        transport_rtt_ms if transport_rtt_ms is not None else details.get("msRTT")
    )

    if rate is not None:
        health[rate_name] = rate
    if link is not None:
        health["link_capacity_mbps"] = link
    if rtt is not None:
        health["rtt_ms"] = rtt

    for model_name, native_name in counters.items():
        delta = counter_delta(
            redis_client,
            srt_counter_key(key, native_name),
            details.get(native_name),
            ttl,
        )
        if delta is not None:
            health[model_name] = delta

    return health


def _positive_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None
