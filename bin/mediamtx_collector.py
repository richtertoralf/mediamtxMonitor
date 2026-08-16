#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mediamtx_collector.py – Streamdaten-Monitoring für MediaMTX

Erfasst alle aktiven Pfade, Quellen (Publisher/Ingest), Leser (Reader/Clients) und
berechnet – soweit nicht von der MediaMTX-API bereitgestellt – Bitraten anhand
von Bytes-Deltas über die Zeit (ΔBytes / Δt). Ergebnisse werden in Redis und
optional als JSON-Datei abgelegt.

Konfiguration:
- /opt/mediamtx-monitoring-backend/config/collector.yaml
  Erwartete Keys (Beispiele; alle optional mit Defaults):
    api_base_url: "http://localhost:9997"
    interval_seconds: 1
    version_refresh_seconds: 60
    forward_refresh_seconds: 5
    output_refresh_seconds: 5
    output_json_path: "/tmp/mediamtx_streams.json"
    redis:
      host: "localhost"
      port: 6379
      key: "mediamtx:streams:latest"
    bitrate:
      min_dt: 0.5           # Mindest-Δt für Messung
      smooth_alpha: 0.5     # EWMA-Glättung (None zum Deaktivieren)
      ttl: 300              # TTL für prev_* und glättungs-Keys
      ignore_loopback: true # Reader von 127.0.0.0/8 bzw. ::1 ausblenden

Ablauf:
1) MediaMTX-Version und API abfragen (Paths und Protokoll-Sessions/-Verbindungen).
2) Pro Path:
   - Publisher-Details auflösen (je nach Typ).
   - Publisher-Bitrate: API (SRT) bevorzugen; sonst Delta aus inboundBytes.
   - Reader-Liste auflösen; pro Reader Bitrate: API (SRT) bevorzugen; sonst Delta aus outboundBytes.
3) Aggregiertes Objekt in Redis schreiben (Key aus config).
4) Optional JSON-Datei für Debug/Inspektion.

Voraussetzung:
- Modul bitrate.py im selben bin/-Verzeichnis:
  from bitrate import calc_bitrate
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from redis.exceptions import RedisError
except ImportError:  # Unit tests load product modules without runtime dependencies.
    class RedisError(Exception):
        pass

try:
    from .bitrate import calc_bitrate
    from .counter_metrics import counter_delta, counter_deltas
    from .connection_history import (
        HISTORY_RETENTION_SECONDS,
        HISTORY_TTL_SECONDS,
        average_rate,
        build_history_sample,
        jitter_history,
        rate_history,
        summarize_history,
    )
    from .connection_lifecycle import (
        observe_connection_groups,
        remote_host,
    )
    from .mediamtx_client import MediaMTXClient, MediaMTXError, MediaMTXHTTPError
    from .mediamtx_model import (
        DETAIL_ENDPOINTS,
        HLS_MUXER_ENDPOINT,
        MINIMUM_MEDIAMTX_VERSION,
        OPTIONAL_SECURE_ENDPOINTS,
        index_details,
        is_supported_version,
    )
    from .monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from .redis_keys import (
        connection_counter_key,
        connection_lifecycle_key,
        connection_history_key,
        hls_muxer_metric_key,
        path_metric_key,
        publisher_connection_key,
        publisher_srt_health_key,
        reader_connection_key,
        reader_srt_health_key,
        rtmp_frame_discard_key,
        stream_snapshot_freshness_key,
    )
    from .redis_store import RedisStore
    from .protocol_metrics import (
        RTMP_CONNECTION_TYPES,
        build_common_metrics,
        build_protocol_metrics,
        counter_fields,
    )
    from .srt_health import build_srt_health
    from .stream_normalizer import connection_identity, normalize_stream
except ImportError:
    from bitrate import calc_bitrate
    from counter_metrics import counter_delta, counter_deltas
    from connection_history import (
        HISTORY_RETENTION_SECONDS,
        HISTORY_TTL_SECONDS,
        average_rate,
        build_history_sample,
        jitter_history,
        rate_history,
        summarize_history,
    )
    from connection_lifecycle import observe_connection_groups, remote_host
    from mediamtx_client import MediaMTXClient, MediaMTXError, MediaMTXHTTPError
    from mediamtx_model import (
        DETAIL_ENDPOINTS,
        HLS_MUXER_ENDPOINT,
        MINIMUM_MEDIAMTX_VERSION,
        OPTIONAL_SECURE_ENDPOINTS,
        index_details,
        is_supported_version,
    )
    from monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from redis_keys import (
        connection_counter_key,
        connection_lifecycle_key,
        connection_history_key,
        hls_muxer_metric_key,
        path_metric_key,
        publisher_connection_key,
        publisher_srt_health_key,
        reader_connection_key,
        reader_srt_health_key,
        rtmp_frame_discard_key,
        stream_snapshot_freshness_key,
    )
    from redis_store import RedisStore
    from protocol_metrics import (
        RTMP_CONNECTION_TYPES,
        build_common_metrics,
        build_protocol_metrics,
        counter_fields,
    )
    from srt_health import build_srt_health
    from stream_normalizer import connection_identity, normalize_stream


# ---------------------------------------------------------------------------
# Konfiguration laden
# ---------------------------------------------------------------------------

config = resolve_monitoring_config({})
API_BASE = config["api_base_url"]
REDIS_CFG = config["redis"]
REDIS_HOST = REDIS_CFG["host"]
REDIS_PORT = REDIS_CFG["port"]
REDIS_KEY = REDIS_CFG["key"]
COLLECTOR_CFG = config["collector"]
JSON_OUTPUT_PATH = COLLECTOR_CFG["output_json_path"]
INTERVAL = COLLECTOR_CFG["interval_seconds"]
IGNORE_PATH_PREFIXES = COLLECTOR_CFG["ignore_path_prefixes"]
BITRATE_CFG = config["bitrate"]
BITRATE_MIN_DT = BITRATE_CFG["min_dt"]
BITRATE_SMOOTH_ALPHA: Optional[float] = BITRATE_CFG["smooth_alpha"]
BITRATE_SMOOTH_REFERENCE_SECONDS = BITRATE_CFG["smooth_reference_seconds"]
BITRATE_TTL = BITRATE_CFG["ttl"]
IGNORE_LOOPBACK = BITRATE_CFG["ignore_loopback"]
r = None
snapshot_store = None
mediamtx_client = None


@dataclass
class PollCache:
    """Small in-process cache for data that does not belong in the 1 Hz path."""

    mediamtx_version: Optional[str] = None
    next_version_refresh: float = 0.0
    next_forward_refresh: float = 0.0
    next_output_write: float = 0.0
    forward_destinations: Dict[str, Any] = field(default_factory=dict)
    lifecycle_roles_by_path: Dict[str, set[tuple[str, str]]] = field(
        default_factory=dict
    )
    lifecycle_keys_seen: set[str] = field(default_factory=set)


poll_cache = PollCache()

def reset_poll_cache() -> None:
    """Reset slow-path state, primarily for runtime reconfiguration and tests."""
    global poll_cache
    poll_cache = PollCache()


def configure_runtime(raw_config: Dict[str, Any]) -> None:
    global config, API_BASE, REDIS_CFG, REDIS_HOST, REDIS_PORT, REDIS_KEY
    global COLLECTOR_CFG, JSON_OUTPUT_PATH, INTERVAL, IGNORE_PATH_PREFIXES
    global BITRATE_CFG, BITRATE_MIN_DT, BITRATE_SMOOTH_ALPHA
    global BITRATE_SMOOTH_REFERENCE_SECONDS, BITRATE_TTL
    global IGNORE_LOOPBACK

    config = resolve_monitoring_config(raw_config)
    API_BASE = config["api_base_url"]
    REDIS_CFG = config["redis"]
    REDIS_HOST = REDIS_CFG["host"]
    REDIS_PORT = REDIS_CFG["port"]
    REDIS_KEY = REDIS_CFG["key"]
    COLLECTOR_CFG = config["collector"]
    JSON_OUTPUT_PATH = COLLECTOR_CFG["output_json_path"]
    INTERVAL = COLLECTOR_CFG["interval_seconds"]
    IGNORE_PATH_PREFIXES = COLLECTOR_CFG["ignore_path_prefixes"]
    BITRATE_CFG = config["bitrate"]
    BITRATE_MIN_DT = BITRATE_CFG["min_dt"]
    BITRATE_SMOOTH_ALPHA = BITRATE_CFG["smooth_alpha"]
    BITRATE_SMOOTH_REFERENCE_SECONDS = BITRATE_CFG[
        "smooth_reference_seconds"
    ]
    BITRATE_TTL = BITRATE_CFG["ttl"]
    IGNORE_LOOPBACK = BITRATE_CFG["ignore_loopback"]
    reset_poll_cache()


def initialize_runtime(config_path: Path | str = DEFAULT_CONFIG_PATH) -> None:
    global r, snapshot_store, mediamtx_client

    import redis

    try:
        configure_runtime(load_monitoring_config(config_path))
    except Exception as exc:
        print(f"❌ Fehler beim Laden der Konfigurationsdatei {config_path}: {exc}")
        sys.exit(1)
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        snapshot_store = RedisStore(r)
        logging.info("🔌 Verbindung zu Redis hergestellt.")
    except Exception as exc:
        logging.error(f"❌ Verbindung zu Redis fehlgeschlagen: {exc}")
        sys.exit(1)
    mediamtx_client = MediaMTXClient(API_BASE)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def fetch(
    endpoint: str,
    params: Optional[Dict[str, str]] = None,
    *,
    required: bool = False,
) -> Dict[str, Any]:
    """
    Holt JSON vom MediaMTX-API-Endpunkt. Optionale Abfragen liefern bei Fehlern
    eine leere Liste; Fehler verpflichtender Current-State-Abfragen werden
    weitergereicht, damit kein leerer oder teilweise veralteter Snapshot entsteht.
    """
    url = mediamtx_client.build_url(endpoint)
    try:
        data = mediamtx_client.get_json(endpoint, params=params)
        if isinstance(data, dict):
            return data
        return {"items": []}
    except MediaMTXError as e:
        if (
            endpoint in OPTIONAL_SECURE_ENDPOINTS
            and isinstance(e, MediaMTXHTTPError)
            and e.status_code == 404
        ):
            return {"items": []}
        if required:
            raise
        logging.warning(f"⚠️ API-Fehler {url}: {e}")
        return {"items": []}


def is_loopback(remote: str) -> bool:
    """
    Ermittelt, ob eine Remote-Adresse eine Loopback-Adresse ist.
    IPv4 127.0.0.0/8 oder IPv6 ::1 / [::1].
    """
    if not remote:
        return False
    remote = remote.strip()
    if remote.startswith("127."):
        return True
    if remote.startswith("::1") or remote.startswith("[::1]"):
        return True
    return False


def first_available(mapping: Dict[str, Any], *field_names: str) -> Any:
    """Return the first present, non-null field without treating zero as absent."""
    for field_name in field_names:
        value = mapping.get(field_name)
        if value is not None:
            return value
    return None


def _update_connection_history(
    connection: Dict[str, Any],
    *,
    history_key: str,
    direction: str,
    timestamp: float,
    include_rate_history: bool = False,
    include_jitter_history: bool = False,
    rate_average_seconds: Optional[int] = None,
) -> None:
    """Persist optional live history without breaking the current snapshot."""
    sample = build_history_sample(
        connection,
        direction,
        timestamp,
    )
    try:
        snapshot_store.append_history_sample(
            history_key,
            sample,
            timestamp=timestamp,
            retention_seconds=HISTORY_RETENTION_SECONDS,
            ttl_seconds=HISTORY_TTL_SECONDS,
        )
        samples = snapshot_store.read_history(
            history_key,
            from_timestamp=timestamp - 60,
            to_timestamp=timestamp,
        )
        summary = summarize_history(samples, timestamp)
        if summary:
            connection["window_metrics"] = summary
        if include_rate_history:
            connection["rate_history"] = rate_history(samples, direction)
        if include_jitter_history:
            connection["jitter_history"] = jitter_history(samples)
        if rate_average_seconds is not None:
            average = average_rate(
                samples,
                direction,
                timestamp,
                rate_average_seconds,
            )
            if average is not None:
                connection.setdefault("rate_metrics", {})[
                    f"{rate_average_seconds}s"
                ] = average
    except (RedisError, ConnectionError, TimeoutError, TypeError, ValueError) as exc:
        logging.warning("Kurzzeithistorie konnte nicht geschrieben werden: %s", exc)


def _enrich_protocol_metrics(
    connection: Dict[str, Any],
    *,
    connection_type: Optional[str],
    details: Dict[str, Any],
    direction: str,
    connection_key: str,
) -> None:
    """Attach normalized non-SRT metrics from connection-local API fields."""
    if connection_type == "srtConn":
        return
    fields = counter_fields(connection_type, direction)
    if connection_type in RTMP_CONNECTION_TYPES and direction == "reader":
        discard = counter_delta(
            r,
            key=rtmp_frame_discard_key(connection_key),
            value=details.get("outboundFramesDiscarded"),
            ttl=BITRATE_TTL,
        )
        deltas = {} if discard is None else {"frame_discard": discard}
        if discard is not None:
            connection["frame_discard_delta"] = discard
    else:
        deltas = counter_deltas(
            r,
            base_key=connection_counter_key(connection_key),
            details=details,
            fields=fields,
            ttl=BITRATE_TTL,
        )
    metrics = build_protocol_metrics(
        connection_type,
        details,
        direction,
        deltas,
    )
    if metrics:
        connection["protocol_metrics"] = metrics
    connection["common"] = build_common_metrics(
        connection_type,
        details,
        direction,
        connection.get("bitrate_mbps"),
    )


def _observe_lifecycle(
    *,
    path: str,
    role: str,
    connection_type: str,
    groups: Dict[str, list[str]],
    timestamp: float,
) -> Dict[str, Dict[str, Any]]:
    """Observe lifecycle state without carrying IDs across collector restarts."""
    key = connection_lifecycle_key(path, role, connection_type)
    reset_baseline = key not in poll_cache.lifecycle_keys_seen
    poll_cache.lifecycle_keys_seen.add(key)
    try:
        return observe_connection_groups(
            r,
            key=key,
            current_groups=groups,
            timestamp=timestamp,
            reset_baseline=reset_baseline,
        )
    except (RedisError, ConnectionError, TimeoutError, TypeError, ValueError) as exc:
        logging.warning("Connection-Lifecycle konnte nicht geschrieben werden: %s", exc)
        return {}


def _enrich_rtmp_lifecycle(
    entry: Dict[str, Any], path: str, timestamp: float
) -> None:
    """Attach observed changes only to unambiguous RTMP connections."""
    source = entry["source"]
    current_roles: set[tuple[str, str]] = set()
    if source.get("type") in RTMP_CONNECTION_TYPES:
        current_roles.add(("publisher", source["type"]))

    readers_by_type: Dict[str, list[Dict[str, Any]]] = {}
    for reader in entry["readers"]:
        if reader.get("type") in RTMP_CONNECTION_TYPES:
            current_roles.add(("reader", reader["type"]))
            readers_by_type.setdefault(reader["type"], []).append(reader)

    known_roles = poll_cache.lifecycle_roles_by_path.setdefault(path, set())
    for role, connection_type in known_roles | current_roles:
        if role == "publisher":
            groups = {}
            if source.get("type") == connection_type and source.get("id"):
                groups["publisher"] = [str(source["id"])]
            results = _observe_lifecycle(
                path=path,
                role=role,
                connection_type=connection_type,
                groups=groups,
                timestamp=timestamp,
            )
            if groups and "publisher" in results:
                source["connection_stability"] = results["publisher"]
            continue

        readers = readers_by_type.get(connection_type, [])
        groups: Dict[str, list[str]] = {}
        entries_by_group: Dict[str, list[Dict[str, Any]]] = {}
        for reader in readers:
            host = remote_host(reader.get("details", {}).get("remoteAddr"))
            if host is None or not reader.get("id"):
                continue
            groups.setdefault(host, []).append(str(reader["id"]))
            entries_by_group.setdefault(host, []).append(reader)

        results = _observe_lifecycle(
            path=path,
            role=role,
            connection_type=connection_type,
            groups=groups,
            timestamp=timestamp,
        )
        for group_name, grouped_entries in entries_by_group.items():
            if len(grouped_entries) == 1 and group_name in results:
                grouped_entries[0]["connection_stability"] = results[group_name]

    known_roles.update(current_roles)


# ---------------------------------------------------------------------------
# Kernfunktion: Sammeln und Speichern
# ---------------------------------------------------------------------------


def collect_and_store() -> Dict[str, float]:
    """
    Sammelt Pfad-, Publisher- und Reader-Infos aus der MediaMTX-API,
    reichert diese um berechnete Bitraten an und schreibt das Ergebnis
    nach Redis und optional als JSON-Datei.
    """
    cycle_started = time.perf_counter()
    metrics = {
        "api_duration_ms": 0.0,
        "api_request_count": 0.0,
        "history_duration_ms": 0.0,
        "redis_snapshot_duration_ms": 0.0,
    }

    def cycle_fetch(
        endpoint: str,
        params: Optional[Dict[str, str]] = None,
        *,
        required: bool = False,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        try:
            return fetch(endpoint, params=params, required=required)
        finally:
            metrics["api_duration_ms"] += (
                time.perf_counter() - started
            ) * 1000
            metrics["api_request_count"] += 1

    now = time.time()
    version_refresh = COLLECTOR_CFG["version_refresh_seconds"]
    if poll_cache.mediamtx_version is None or now >= poll_cache.next_version_refresh:
        try:
            info = cycle_fetch("/v3/info", required=True)
        except MediaMTXError as exc:
            logging.warning("MediaMTX-Version konnte nicht gelesen werden: %s", exc)
            metrics["cycle_duration_ms"] = (
                time.perf_counter() - cycle_started
            ) * 1000
            return metrics
        mediamtx_version = info.get("version")
        if not is_supported_version(mediamtx_version):
            required = ".".join(str(part) for part in MINIMUM_MEDIAMTX_VERSION)
            shown_version = mediamtx_version or "unbekannt"
            logging.error(
                "❌ MediaMTX %s wird nicht unterstützt; erforderlich ist v%s oder neuer.",
                shown_version,
                required,
            )
            metrics["cycle_duration_ms"] = (
                time.perf_counter() - cycle_started
            ) * 1000
            return metrics
        poll_cache.mediamtx_version = str(mediamtx_version)
        poll_cache.next_version_refresh = now + version_refresh
    mediamtx_version = poll_cache.mediamtx_version
    if not is_supported_version(mediamtx_version):
        required = ".".join(str(part) for part in MINIMUM_MEDIAMTX_VERSION)
        shown_version = mediamtx_version or "unbekannt"
        logging.error(
            "❌ MediaMTX %s wird nicht unterstützt; erforderlich ist v%s oder neuer.",
            shown_version,
            required,
        )
        metrics["cycle_duration_ms"] = (
            time.perf_counter() - cycle_started
        ) * 1000
        return metrics

    try:
        paths = cycle_fetch("/v3/paths/list", required=True).get("items", [])
    except MediaMTXError as exc:
        logging.warning("MediaMTX-Paths konnten nicht gelesen werden: %s", exc)
        metrics["cycle_duration_ms"] = (
            time.perf_counter() - cycle_started
        ) * 1000
        return metrics
    visible_paths = [
        path
        for path in paths
        if not any(
            str(path.get("name", "")).startswith(prefix)
            for prefix in IGNORE_PATH_PREFIXES
        )
    ]
    active_types = {
        connection.get("type")
        for path in visible_paths
        for connection in [
            path.get("source", {}) or {},
            *((path.get("readers", []) or [])),
        ]
        if connection.get("type") in DETAIL_ENDPOINTS
    }
    details = index_details({
        obj_type: cycle_fetch(DETAIL_ENDPOINTS[obj_type]).get("items", [])
        for obj_type in DETAIL_ENDPOINTS
        if obj_type in active_types
    })
    hls_muxers = {}
    if "hlsSession" in active_types:
        hls_muxers = {
            str(item.get("path")): item
            for item in cycle_fetch(HLS_MUXER_ENDPOINT).get("items", [])
            if isinstance(item, dict) and item.get("path") is not None
        }

    if now >= poll_cache.next_forward_refresh:
        poll_cache.forward_destinations = {
            str(path.get("name", "")): cycle_fetch(
                "/v3/paths/forward/list",
                params={"path": str(path.get("name", ""))},
            ).get("items", [])
            for path in visible_paths
        }
        poll_cache.next_forward_refresh = (
            now + COLLECTOR_CFG["forward_refresh_seconds"]
        )

    aggregated = []
    for path in visible_paths:
        name: str = path.get("name", "")
        forward_destinations = poll_cache.forward_destinations.get(name, [])
        entry = normalize_stream(
            path,
            details,
            mediamtx_version,
            forward_destinations,
        )
        source = entry["source"]
        src_type: Optional[str] = source["type"]
        src_details = source["details"]
        normalized_readers = entry["readers"]
        entry["readers"] = []

        path_state_key = path_metric_key(
            name,
            f"{source.get('type')}:{source.get('id')}"
            if source.get("type") and source.get("id") else None,
        )

        path_delta = counter_delta(
            r,
            key=f"{path_state_key}:inboundFramesInError",
            value=path.get("inboundFramesInError"),
            ttl=BITRATE_TTL,
        )
        path_metrics: Dict[str, Any] = {"scope": "path"}
        if path_delta is not None:
            path_metrics["protocol_metrics"] = {
                "family": "path",
                "counter_deltas": {"frame_error": path_delta},
            }
        _update_connection_history(
            path_metrics,
            history_key=connection_history_key(path_state_key),
            direction="publisher",
            timestamp=now,
        )
        if path_metrics.get("window_metrics"):
            entry["path_metrics"] = path_metrics

        hls_muxer = hls_muxers.get(name)
        if hls_muxer:
            muxer_state_key = hls_muxer_metric_key(name, hls_muxer.get("created"))
            mux_delta = counter_delta(
                r,
                key=f"{muxer_state_key}:outboundFramesDiscarded",
                value=hls_muxer.get("outboundFramesDiscarded"),
                ttl=BITRATE_TTL,
            )
            mux_entry: Dict[str, Any] = {
                "scope": "hls_muxer",
                "path": name,
                "created": hls_muxer.get("created"),
                "lastRequest": hls_muxer.get("lastRequest"),
                "outboundBytes": hls_muxer.get("outboundBytes"),
            }
            if mux_delta is not None:
                mux_entry["protocol_metrics"] = {
                    "family": "hls",
                    "counter_deltas": {"mux_discard": mux_delta},
                }
            _update_connection_history(
                mux_entry,
                history_key=connection_history_key(muxer_state_key),
                direction="reader",
                timestamp=now,
            )
            entry["hls_muxer"] = mux_entry

        # ---------------------------
        # Publisher-Bitrate berechnen
        # ---------------------------
        # API-Rate bevorzugen (nur SRT liefert typischerweise mbpsReceiveRate)
        api_rx_mbps = src_details.get("mbpsReceiveRate")
        # Fallback: aus Byte-Deltas berechnen. SRT behält native Transportzähler.
        # Quelle bytes: bevorzugt die Detailverbindung, sonst Path-Feld
        pub_bytes_value = first_available(src_details, "inboundBytes")
        if pub_bytes_value is None and src_type == "srtConn":
            pub_bytes_value = first_available(src_details, "bytesReceived")
        if pub_bytes_value is None:
            pub_bytes_value = entry.get("inboundBytes")

        pub_identity = connection_identity(source)
        pub_key = publisher_connection_key(
            name,
            src_type,
            pub_identity,
        )
        pub_calc_mbps = None
        if pub_bytes_value is not None:
            pub_calc_mbps = calc_bitrate(
                r,
                key=pub_key,
                bytes_now=int(pub_bytes_value),
                now=now,
                min_dt=BITRATE_MIN_DT,
                smooth_alpha=BITRATE_SMOOTH_ALPHA,
                smooth_reference_seconds=BITRATE_SMOOTH_REFERENCE_SECONDS,
                ttl=BITRATE_TTL,
            )

        if api_rx_mbps is not None:
            entry["source"]["bitrate_mbps"] = round(float(api_rx_mbps), 2)
        else:
            entry["source"]["bitrate_mbps"] = pub_calc_mbps

        # SRT transport RTT is provided natively by MediaMTX.
        if src_type == "srtConn" and src_details.get("msRTT") is not None:
            entry["source"]["transport_rtt_ms"] = round(
                float(src_details["msRTT"]), 2
            )

        if src_type == "srtConn":
            if src_details.get("msReceiveTsbPdDelay") is not None:
                entry["source"]["srt_latency_ms"] = src_details[
                    "msReceiveTsbPdDelay"
                ]
            entry["source"]["srt_health"] = build_srt_health(
                r,
                key=publisher_srt_health_key(
                    name,
                    src_type,
                    pub_identity,
                ),
                details=src_details,
                direction="publisher",
                ttl=BITRATE_TTL,
                transport_rtt_ms=entry["source"].get("transport_rtt_ms"),
            )
        else:
            _enrich_protocol_metrics(
                entry["source"],
                connection_type=src_type,
                details=src_details,
                direction="publisher",
                connection_key=pub_key,
            )

        if src_type:
            history_started = time.perf_counter()
            _update_connection_history(
                entry["source"],
                history_key=connection_history_key(pub_key),
                direction="publisher",
                timestamp=now,
                include_rate_history=src_type in RTMP_CONNECTION_TYPES,
                include_jitter_history=src_type in {
                    "rtspSession", "rtspsSession", "webRTCSession",
                },
            )
            metrics["history_duration_ms"] += (
                time.perf_counter() - history_started
            ) * 1000

        # ------------------------
        # Reader-Liste aufbereiten
        # ------------------------
        for rd in normalized_readers:
            rtype: Optional[str] = rd["type"]
            rid: Optional[str] = rd["id"]
            rd_details = rd["details"]

            # Optional lokale/loopback-Reader ignorieren
            if IGNORE_LOOPBACK:
                remote = rd_details.get("remoteAddr", "")
                if is_loopback(remote):
                    continue

            # Reader-Bitrate: API (SRT) bevorzugen, sonst Delta aus outboundBytes
            api_tx_mbps = rd_details.get("mbpsSendRate")
            rd_bytes_value = first_available(rd_details, "outboundBytes")
            if rd_bytes_value is None and rtype == "srtConn":
                rd_bytes_value = first_available(rd_details, "bytesSent")

            reader_identity = connection_identity(rd)
            rd_key = reader_connection_key(name, rtype, reader_identity)
            rd_calc_mbps = None
            if rd_bytes_value is not None:
                rd_calc_mbps = calc_bitrate(
                    r,
                    key=rd_key,
                    bytes_now=int(rd_bytes_value),
                    now=now,
                    min_dt=BITRATE_MIN_DT,
                    smooth_alpha=BITRATE_SMOOTH_ALPHA,
                    smooth_reference_seconds=BITRATE_SMOOTH_REFERENCE_SECONDS,
                    ttl=BITRATE_TTL,
                )

            bitrate_final = (
                round(float(api_tx_mbps), 2)
                if api_tx_mbps is not None
                else rd_calc_mbps
            )

            reader_entry = {
                "type": rtype,
                "id": rid,
                "bitrate_mbps": bitrate_final,
                "details": rd_details,
            }
            if rtype == "srtConn":
                if rd_details.get("msRTT") is not None:
                    reader_entry["transport_rtt_ms"] = round(
                        float(rd_details["msRTT"]), 2
                    )
                if rd_details.get("msSendTsbPdDelay") is not None:
                    reader_entry["srt_latency_ms"] = rd_details[
                        "msSendTsbPdDelay"
                    ]
                reader_entry["srt_health"] = build_srt_health(
                    r,
                    key=reader_srt_health_key(
                        name,
                        rtype,
                        reader_identity,
                    ),
                    details=rd_details,
                    direction="reader",
                    ttl=BITRATE_TTL,
                    transport_rtt_ms=reader_entry.get("transport_rtt_ms"),
                )
            else:
                _enrich_protocol_metrics(
                    reader_entry,
                    connection_type=rtype,
                    details=rd_details,
                    direction="reader",
                    connection_key=rd_key,
                )
            history_started = time.perf_counter()
            _update_connection_history(
                reader_entry,
                history_key=connection_history_key(rd_key),
                direction="reader",
                timestamp=now,
                include_rate_history=rtype in RTMP_CONNECTION_TYPES,
                rate_average_seconds=10 if rtype == "hlsSession" else None,
            )
            metrics["history_duration_ms"] += (
                time.perf_counter() - history_started
            ) * 1000
            entry["readers"].append(reader_entry)

        _enrich_rtmp_lifecycle(entry, name, now)
        aggregated.append(entry)

    # -----------------------------------------------------------------------
    # Ergebnis nach Redis und optional als JSON-Datei schreiben
    # -----------------------------------------------------------------------
    collected_at = time.time()
    snapshot_started = time.perf_counter()
    try:
        snapshot_store.write_snapshot(REDIS_KEY, aggregated)
        snapshot_store.write_snapshot(
            stream_snapshot_freshness_key(REDIS_KEY), collected_at
        )
        logging.info(
            f"✅ {len(aggregated)} Pfade in Redis gespeichert (Key: {REDIS_KEY})."
        )
    except Exception as e:
        logging.error(f"❌ Redis-Fehler beim Schreiben von {REDIS_KEY}: {e}")
    finally:
        metrics["redis_snapshot_duration_ms"] = (
            time.perf_counter() - snapshot_started
        ) * 1000

    if now >= poll_cache.next_output_write:
        try:
            Path(JSON_OUTPUT_PATH).write_text(
                json.dumps(aggregated, indent=2), encoding="utf-8"
            )
            poll_cache.next_output_write = (
                now + COLLECTOR_CFG["output_refresh_seconds"]
            )
            logging.info(f"💾 JSON gespeichert unter {JSON_OUTPUT_PATH}")
        except Exception as e:
            logging.error(f"❌ Fehler beim Schreiben der JSON-Datei: {e}")

    metrics["cycle_duration_ms"] = (
        time.perf_counter() - cycle_started
    ) * 1000
    logging.debug(
        "Collector cycle %.2f ms (MediaMTX %.2f ms/%d requests, "
        "history %.2f ms, snapshot Redis %.2f ms)",
        metrics["cycle_duration_ms"],
        metrics["api_duration_ms"],
        int(metrics["api_request_count"]),
        metrics["history_duration_ms"],
        metrics["redis_snapshot_duration_ms"],
    )
    return metrics


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _run_interval_loop(job: Callable[[], None], interval_seconds: float) -> None:
    next_run = time.monotonic() + interval_seconds
    while True:
        time.sleep(max(0.0, next_run - time.monotonic()))
        try:
            job()
        except Exception:
            logging.exception("❌ Unbehandelter Fehler im Collector-Durchlauf.")

        next_run += interval_seconds
        now = time.monotonic()
        if next_run <= now:
            missed_intervals = int((now - next_run) // interval_seconds) + 1
            next_run += missed_intervals * interval_seconds


def main(run_once: bool = False) -> None:
    """
    Startet den Collector einmalig oder als dauerhaften Hintergrundjob.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    initialize_runtime()

    if run_once:
        collect_and_store()
        return

    logging.info("🚀 Stream-Collector gestartet.")
    try:
        _run_interval_loop(collect_and_store, INTERVAL)
    except KeyboardInterrupt:
        logging.info("🛑 Collector gestoppt.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediaMTX Collector")
    parser.add_argument("--once", action="store_true", help="Nur einmal ausführen")
    args = parser.parse_args()
    main(run_once=args.once)
