"""MediaMTX Monitor - RTMP reader metrics.

Derives interval values from native connection-local RTMP counters without
classifying connection health.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from .counter_metrics import counter_delta
except ImportError:
    from counter_metrics import counter_delta


def frame_discard_delta(
    redis_client: Any,
    *,
    key: str,
    value: Any,
    ttl: int,
) -> Optional[int]:
    """Return a reset-safe delta of a cumulative reader discard counter."""
    return counter_delta(
        redis_client,
        key=key,
        value=value,
        ttl=ttl,
    )
