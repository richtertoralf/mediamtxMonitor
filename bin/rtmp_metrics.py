"""MediaMTX Monitor - RTMP reader metrics.

Derives interval values from native connection-local RTMP counters without
classifying connection health.
"""

from __future__ import annotations

import logging
from typing import Any, Optional


def frame_discard_delta(
    redis_client: Any,
    *,
    key: str,
    value: Any,
    ttl: int,
) -> Optional[int]:
    """Return a reset-safe delta of a cumulative reader discard counter."""
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
        logging.debug("Invalid RTMP frame-discard counter %s=%r: %s", key, value, exc)
        return None
    except Exception as exc:
        logging.debug("RTMP frame-discard state failed for %s: %s", key, exc)
        return None
