"""
MediaMTX Monitor - cumulative counter processing.

Converts MediaMTX connection-, path-, and muxer-local cumulative counters into
reset-safe interval values. Counter identities and TTLs are supplied by the
caller so sessions and metric scopes remain separate.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping


logger = logging.getLogger(__name__)


def counter_delta(
    redis_client: Any,
    *,
    key: str,
    value: Any,
    ttl: int,
) -> int | None:
    """Store one cumulative value and return its non-negative interval delta."""
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
        logger.debug("Invalid cumulative counter %s=%r: %s", key, value, exc)
    except Exception as exc:
        logger.debug("Counter state failed for %s: %s", key, exc)
    return None


def counter_deltas(
    redis_client: Any,
    *,
    base_key: str,
    details: Mapping[str, Any],
    fields: Mapping[str, str],
    ttl: int,
) -> dict[str, int]:
    """Return available interval deltas keyed by normalized metric name."""
    deltas: dict[str, int] = {}
    for metric_name, native_name in fields.items():
        delta = counter_delta(
            redis_client,
            key=f"{base_key}:{native_name}",
            value=details.get(native_name),
            ttl=ttl,
        )
        if delta is not None:
            deltas[metric_name] = delta
    return deltas
