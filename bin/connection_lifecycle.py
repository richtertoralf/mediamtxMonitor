"""MediaMTX Monitor - short observed connection lifecycle state.

Tracks only unambiguous MediaMTX connection-ID changes over one minute. It
does not infer disconnects that happened between collector polls.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional


LIFECYCLE_WINDOW_SECONDS = 60
LIFECYCLE_TTL_SECONDS = 120

_BRACKETED_HOST = re.compile(r"^\[(.+)](?::\d+)?$")
_HOST_PORT = re.compile(r"^([^:]+):\d+$")


def remote_host(remote_addr: Any) -> Optional[str]:
    """Return a host without the ephemeral port used by a connection."""
    value = str(remote_addr or "").strip()
    if not value:
        return None
    bracketed = _BRACKETED_HOST.fullmatch(value)
    if bracketed:
        return bracketed.group(1)
    host_port = _HOST_PORT.fullmatch(value)
    if host_port:
        return host_port.group(1)
    return value


def observe_connection_groups(
    redis_client: Any,
    *,
    key: str,
    current_groups: Mapping[str, list[str]],
    timestamp: float,
    ttl: int = LIFECYCLE_TTL_SECONDS,
    reset_baseline: bool = False,
) -> dict[str, dict[str, Any]]:
    """Observe singleton ID changes and return stability for current groups.

    A group becomes ambiguous as soon as more than one connection is active;
    no change is attributed across such a sample.
    """
    previous = {} if reset_baseline else _read_state(redis_client.get(key))
    previous_groups = previous.get("groups", {})
    next_groups: dict[str, dict[str, Any]] = {}
    results: dict[str, dict[str, Any]] = {}

    for group_name in set(previous_groups) | set(current_groups):
        group = previous_groups.get(group_name, {})
        events = [
            float(event)
            for event in group.get("events", [])
            if _valid_timestamp(event) and float(event) > timestamp - LIFECYCLE_WINDOW_SECONDS
        ]
        previous_single = group.get("last_single_id")
        current_ids = sorted({str(item) for item in current_groups.get(group_name, []) if item})

        if len(current_ids) > 1:
            previous_single = None
        elif len(current_ids) == 1:
            current_id = current_ids[0]
            if previous_single is not None and previous_single != current_id:
                events.append(timestamp)
            previous_single = current_id

            results[group_name] = {
                "changes_60s": len(events),
                "last_change_at": events[-1] if events else None,
                "seconds_since_last_change": int(timestamp - events[-1]) if events else None,
            }

        next_groups[group_name] = {
            "last_single_id": previous_single,
            "events": events,
        }

    redis_client.set(
        key,
        json.dumps({"groups": next_groups}, separators=(",", ":"), sort_keys=True),
        ex=ttl,
    )
    return results


def _read_state(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    try:
        value = json.loads(payload)
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _valid_timestamp(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
