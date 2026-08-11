"""JSON snapshot persistence over an existing Redis-compatible client."""

from __future__ import annotations

import json
from typing import Any


class SnapshotDecodeError(ValueError):
    """Raised when a stored snapshot is not valid JSON."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Redis-Snapshot enthält ungültiges JSON: {key}")
        self.key = key


class RedisStore:
    """Read and write current monitoring snapshots as JSON without TTL."""

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
