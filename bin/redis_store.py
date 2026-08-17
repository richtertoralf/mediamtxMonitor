"""
MediaMTX Monitor - Redis snapshot and short-history persistence.

Stores current JSON snapshots without expiration and compact connection-history
samples with time-based retention and TTL. Key construction, metric calculation,
and MediaMTX interpretation remain outside this module.
"""

from __future__ import annotations

import json
from typing import Any


class SnapshotDecodeError(ValueError):
    """Raised when a stored snapshot is not valid JSON."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Redis-Snapshot enthält ungültiges JSON: {key}")
        self.key = key


class RedisStore:
    """Persist current snapshots and short-lived history as JSON in Redis."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    def write_snapshot(self, key: str, snapshot: Any) -> None:
        """Serialize and store a snapshot under the supplied configured key."""
        payload = json.dumps(snapshot)
        self._redis.set(key, payload)

    def read_snapshot(self, key: str) -> Any:
        """Return a decoded snapshot, or ``None`` when the key does not exist."""
        payload = self._redis.get(key)
        if payload is None:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SnapshotDecodeError(key) from exc

    def append_history_sample(
        self,
        key: str,
        sample: dict[str, Any],
        *,
        timestamp: float,
        retention_seconds: float,
        ttl_seconds: int,
    ) -> None:
        """Append, time-trim, and expire a compact connection sample."""
        payload = json.dumps(sample, separators=(",", ":"), sort_keys=True)
        self._redis.zadd(key, {payload: timestamp})
        self._redis.zremrangebyscore(key, "-inf", timestamp - retention_seconds)
        self._redis.expire(key, ttl_seconds)

    def read_history(
        self, key: str, *, from_timestamp: float, to_timestamp: float
    ) -> list[dict[str, Any]]:
        """Read decoded history samples ordered by their timestamp score."""
        payloads = self._redis.zrangebyscore(key, from_timestamp, to_timestamp)
        samples = []
        for payload in payloads:
            try:
                samples.append(json.loads(payload))
            except json.JSONDecodeError as exc:
                raise SnapshotDecodeError(key) from exc
        return samples
