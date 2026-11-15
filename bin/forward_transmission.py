"""
MediaMTX Monitor - transmission evidence for forward destinations.

Evaluates from two consecutive successful MediaMTX observations of one forward
destination whether it carries data: native ``state`` plus growth of the
native ``outboundBytes`` counter within a bounded window. The caller keeps the
returned state in process memory, so a new collector generation starts
without evidence instead of inheriting it.

Does not query MediaMTX or Redis and makes no statement about whether a remote
platform publishes the stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


SENDING = "sending"
NOT_SENDING = "not_sending"
UNKNOWN = "unknown"

# MediaMTX v1.21 defines exactly these forward states.
_STOPPED_STATES = {"idle": "state_idle", "error": "state_error"}


@dataclass(frozen=True)
class TransmissionState:
    """Evaluation of one forward destination at one observation."""

    observed_at: float
    outbound_bytes: Optional[int]
    status: str
    reason: str
    since: Optional[float] = None
    since_observed: bool = False
    last_growth_at: Optional[float] = None
    ended_at: Optional[float] = None

    def as_snapshot(self) -> dict[str, Any]:
        """Return the public snapshot form of this evaluation."""
        return {
            "status": self.status,
            "reason": self.reason,
            "since": self.since,
            "since_observed": self.since_observed,
            "last_growth_at": self.last_growth_at,
            "ended_at": self.ended_at,
        }


def _outbound_bytes(destination: Mapping[str, Any]) -> Optional[int]:
    value = destination.get("outboundBytes")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _classify(
    previous: Optional[TransmissionState],
    state: Any,
    outbound_bytes: Optional[int],
    now: float,
    window_seconds: float,
) -> tuple[str, str]:
    if state in _STOPPED_STATES:
        return NOT_SENDING, _STOPPED_STATES[state]
    if state != "forwarding":
        return UNKNOWN, "state_unknown"
    if outbound_bytes is None:
        return UNKNOWN, "no_byte_counter"
    if previous is None or previous.outbound_bytes is None:
        return UNKNOWN, "first_sample"
    if now - previous.observed_at > window_seconds:
        return UNKNOWN, "sample_gap"
    if outbound_bytes < previous.outbound_bytes:
        return UNKNOWN, "counter_reset"
    if outbound_bytes > previous.outbound_bytes:
        return SENDING, "bytes_growing"
    return NOT_SENDING, "no_byte_growth"


def evaluate_transmission(
    previous: Optional[TransmissionState],
    destination: Mapping[str, Any],
    now: float,
    window_seconds: float,
) -> TransmissionState:
    """Evaluate one forward destination against its previous observation.

    ``since`` is the first observation of the current sending period.
    ``since_observed`` tells whether the monitor saw the period begin: the
    observation before showed no transmission or an unused byte counter.
    Otherwise the transmission was already running at the first observation
    and its real start is earlier and unknown. ``ended_at`` is the first
    observation without transmission after the last byte growth.
    """
    outbound_bytes = _outbound_bytes(destination)
    status, reason = _classify(
        previous, destination.get("state"), outbound_bytes, now, window_seconds
    )

    if status == SENDING:
        # _classify returns SENDING only with a previous byte sample.
        if previous is None:
            since, since_observed = now, False
        elif previous.status == SENDING:
            since, since_observed = previous.since, previous.since_observed
        else:
            since_observed = (
                previous.status == NOT_SENDING or previous.outbound_bytes == 0
            )
            since = now if since_observed else previous.observed_at
        return TransmissionState(
            observed_at=now,
            outbound_bytes=outbound_bytes,
            status=status,
            reason=reason,
            since=since,
            since_observed=since_observed,
            last_growth_at=now,
            ended_at=None,
        )

    last_growth_at = previous.last_growth_at if previous else None
    ended_at = previous.ended_at if previous else None
    if status == NOT_SENDING and ended_at is None and last_growth_at is not None:
        ended_at = now
    return TransmissionState(
        observed_at=now,
        outbound_bytes=outbound_bytes,
        status=status,
        reason=reason,
        last_growth_at=last_growth_at,
        ended_at=ended_at,
    )
