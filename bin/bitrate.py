"""
MediaMTX Monitor - stateful bitrate calculation.

Converts cumulative byte counters into reset-safe Mbit/s values using previous
counter state. Optional EWMA smoothing preserves a stable time response across
different sampling intervals.

Does not select between native protocol rates and calculated fallback rates.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Optional

try:
    from .redis_keys import bitrate_state_keys
except ImportError:
    from redis_keys import bitrate_state_keys


def calc_bitrate(
    r,
    key: str,
    bytes_now: int,
    now: Optional[float] = None,
    min_dt: float = 0.5,
    smooth_alpha: Optional[float] = None,
    smooth_reference_seconds: Optional[float] = None,
    ttl: int = 300,
) -> Optional[float]:
    """Return a rounded Mbit/s delta from a cumulative byte counter.

    ``None`` is returned until previous state exists, when the interval is too
    short, after a counter reset, or when state processing fails. When supplied,
    ``smooth_reference_seconds`` keeps EWMA behavior stable across poll cadences.
    """
    if key is None or key == "":
        logging.debug("calc_bitrate: leerer Schlüssel")
        return None
    if bytes_now is None:
        logging.debug("calc_bitrate: bytes_now ist None")
        return None

    now = time.time() if now is None else float(now)

    try:
        prev_bytes_key, prev_ts_key, ewma_key = bitrate_state_keys(key)

        prev_bytes_str = r.get(prev_bytes_key)
        prev_ts_str = r.get(prev_ts_key)

        # The first observation establishes a baseline and cannot yield a rate.
        if prev_bytes_str is None or prev_ts_str is None:
            _store_state(r, key, int(bytes_now), now, ttl)
            return None

        prev_bytes = int(prev_bytes_str)
        prev_ts = float(prev_ts_str)
        dt = now - prev_ts

        if dt < min_dt:
            return None

        delta = int(bytes_now) - prev_bytes
        # A counter reset or connection replacement must not produce a negative rate.
        if delta < 0:
            _store_state(r, key, int(bytes_now), now, ttl)
            return None

        mbps = (delta * 8) / (dt * 1_000_000)

        if smooth_alpha is not None:
            try:
                prev_mbps_str = r.get(ewma_key)
                if prev_mbps_str is not None:
                    prev_mbps = float(prev_mbps_str)
                    alpha = float(smooth_alpha)
                    if smooth_reference_seconds is not None:
                        reference = float(smooth_reference_seconds)
                        if reference > 0:
                            alpha = 1.0 - math.pow(1.0 - alpha, dt / reference)
                    mbps = alpha * mbps + (1.0 - alpha) * prev_mbps
                r.set(ewma_key, mbps, ex=ttl)
            except Exception as e:
                # Optional smoothing failures must not discard the raw rate.
                logging.debug(f"calc_bitrate: EWMA-Fehler für {key}: {e}")

        _store_state(r, key, int(bytes_now), now, ttl)

        return round(mbps, 2)

    except Exception as e:
        logging.debug(f"calc_bitrate: Fehler bei {key}: {e}")
        # Refresh the baseline so a transient state error does not persist.
        try:
            _store_state(r, key, int(bytes_now), now, ttl)
        except Exception:
            # Preserve the original fallback while still exposing the secondary error.
            logging.debug("calc_bitrate: zusätzlicher Fehler beim Speichern des Zustands", exc_info=True)
        return None


def reset_state(r, key: str) -> None:
    """Delete the previous counter, timestamp, and EWMA state for one key."""
    try:
        prev_bytes_key, prev_ts_key, ewma_key = bitrate_state_keys(key)
        r.delete(prev_bytes_key)
        r.delete(prev_ts_key)
        r.delete(ewma_key)
    except Exception as e:
        logging.debug(f"reset_state: Fehler beim Löschen des Zustands für {key}: {e}")


def _store_state(r, key: str, bytes_now: int, ts: float, ttl: int) -> None:
    """Store the counter baseline atomically with its expiration."""
    try:
        prev_bytes_key, prev_ts_key, _ = bitrate_state_keys(key)
        pipe = r.pipeline()
        pipe.set(prev_bytes_key, bytes_now, ex=ttl)
        pipe.set(prev_ts_key, ts, ex=ttl)
        pipe.execute()
    except Exception as e:
        logging.debug(f"_store_state: Fehler beim Speichern des Zustands für {key}: {e}")
