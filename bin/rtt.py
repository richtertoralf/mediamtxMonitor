# /opt/mediamtx-monitoring-backend/bin/rtt.py
# -*- coding: utf-8 -*-
"""
rtt.py – Externe ICMP-Ping-Messung für geeignete MediaMTX-Verbindungen.

Warum nur ICMP?
- Beim Publisher ist die remoteAddr meist ein Encoder-Client mit *ephemeral* Port.
  TCP-Connect-RTT zu diesem Port schlägt i. d. R. fehl. Ein Host-Ping ist hier die
  robusteste Näherung. Fällt ICMP weg (Firewall), lassen wir RTT einfach leer.

Caching/Glättung:
- EWMA-Glättung per Redis in rollenbezogenen Zustands-Keys.
- Rate-Limit (min_period_s): z. B. nur alle 30 s neu messen.
"""

from __future__ import annotations
import subprocess
import time
import re
from typing import Optional, Tuple

try:
    from .redis_keys import (
        DEFAULT_RTT_PUBLISHER_PREFIX,
        DEFAULT_RTT_READER_PREFIX,
        publisher_rtt_keys,
        reader_rtt_keys,
    )
except ImportError:
    from redis_keys import (
        DEFAULT_RTT_PUBLISHER_PREFIX,
        DEFAULT_RTT_READER_PREFIX,
        publisher_rtt_keys,
        reader_rtt_keys,
    )

_IPV6_BRACKET_RE = re.compile(r'^\[(.+)\]:(\d+)$')  # "[2001:db8::1]:443"
_IPV4_PORT_RE = re.compile(r'^([^:]+):(\d+)$')      # "192.168.0.10:5555"

def _parse_host(remote: str) -> Optional[str]:
    """Extrahiert den Host aus 'host:port' oder '[v6]:port' oder nur Host."""
    if not remote:
        return None
    remote = remote.strip()
    m6 = _IPV6_BRACKET_RE.match(remote)
    if m6:
        return m6.group(1)
    m4 = _IPV4_PORT_RE.match(remote)
    if m4:
        return m4.group(1)
    return remote  # nur Host ohne Port

def _icmp_ping_once(host: str, timeout_s: float = 0.9) -> Optional[float]:
    """Gibt RTT in ms zurück oder None (nutzt System-`ping`)."""
    if not host:
        return None
    cmd = ["ping", "-n", "-c", "1", "-w", str(max(1, int(round(timeout_s)))), host]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 0.5)
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    m = re.search(r'time[=<]\s*([\d\.]+)\s*ms', proc.stdout)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None

def _rgetf(r, key: str) -> Optional[float]:
    try:
        v = r.get(key)
        return float(v) if v is not None else None
    except Exception:
        return None

def _rset(r, key: str, value, ttl: int) -> None:
    try:
        r.set(key, value, ex=ttl)
    except Exception:
        pass

def _measure_icmp_rtt_ms(
    r,
    remote_addr: str,
    keys: Tuple[str, str, str],
    *,
    ewma_alpha: float = 0.5,
    min_period_s: int = 30,
    ttl_s: int = 300,
    timeout_s: float = 0.9,
) -> Optional[float]:
    """Measure ICMP RTT using the supplied isolated Redis state keys.

    - Rate-Limit: höchstens alle `min_period_s` neu messen.
    - Fällt ICMP weg, liefern wir den Cache (ewma/last), sonst None.
    """
    host = _parse_host(remote_addr)
    if not host:
        return None

    k_ewma, k_last, k_ts = keys

    now = time.time()
    last_ts = _rgetf(r, k_ts)
    if last_ts is not None and (now - last_ts) < float(min_period_s):
        ew = _rgetf(r, k_ewma)
        return ew if ew is not None else _rgetf(r, k_last)

    rtt = _icmp_ping_once(host, timeout_s=timeout_s)
    if rtt is None:
        # Kein Ping möglich → besten Cache zurückgeben, aber Timestamp updaten,
        # damit wir nicht in jeder Iteration erneut versuchen.
        ew = _rgetf(r, k_ewma)
        if ew is not None:
            _rset(r, k_ts, now, ttl_s)
            return ew
        last = _rgetf(r, k_last)
        if last is not None:
            _rset(r, k_ts, now, ttl_s)
            return last
        return None

    # Glätten
    prev_ew = _rgetf(r, k_ewma)
    if prev_ew is not None:
        rtt = ewma_alpha * rtt + (1.0 - ewma_alpha) * prev_ew

    # Cache aktualisieren
    _rset(r, k_ewma, rtt, ttl_s)
    _rset(r, k_last, rtt, ttl_s)
    _rset(r, k_ts, now, ttl_s)
    return rtt


def measure_publisher_rtt_ms(
    r,
    remote_addr: str,
    *,
    ewma_alpha: float = 0.5,
    min_period_s: int = 30,
    ttl_s: int = 300,
    key_prefix: str = DEFAULT_RTT_PUBLISHER_PREFIX,
    timeout_s: float = 0.9,
) -> Optional[float]:
    """Measure external ICMP ping for a non-SRT publisher."""
    host = _parse_host(remote_addr)
    if not host:
        return None
    return _measure_icmp_rtt_ms(
        r,
        remote_addr,
        publisher_rtt_keys(host, key_prefix),
        ewma_alpha=ewma_alpha,
        min_period_s=min_period_s,
        ttl_s=ttl_s,
        timeout_s=timeout_s,
    )


def measure_reader_rtt_ms(
    r,
    remote_addr: str,
    *,
    path: str,
    connection_type: str,
    connection_id: str,
    ewma_alpha: float = 0.5,
    min_period_s: int = 30,
    ttl_s: int = 300,
    key_prefix: str = DEFAULT_RTT_READER_PREFIX,
    timeout_s: float = 0.9,
) -> Optional[float]:
    """Measure external ICMP ping with reader-connection-local cache state."""
    host = _parse_host(remote_addr)
    if not host:
        return None
    return _measure_icmp_rtt_ms(
        r,
        remote_addr,
        reader_rtt_keys(
            path,
            connection_type,
            connection_id,
            host,
            key_prefix,
        ),
        ewma_alpha=ewma_alpha,
        min_period_s=min_period_s,
        ttl_s=ttl_s,
        timeout_s=timeout_s,
    )
