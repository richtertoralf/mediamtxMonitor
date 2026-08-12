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
    interval_seconds: 10
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
- Modul bitrate.py und rtt.py im selben bin/-Verzeichnis:
  from bitrate import calc_bitrate
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from .bitrate import calc_bitrate
    from .mediamtx_client import MediaMTXClient, MediaMTXError, MediaMTXHTTPError
    from .mediamtx_model import (
        DETAIL_ENDPOINTS,
        MINIMUM_MEDIAMTX_VERSION,
        OPTIONAL_SECURE_ENDPOINTS,
        index_details,
        is_supported_version,
    )
    from .monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        measure_configured_rtt,
        resolve_monitoring_config,
    )
    from .rtt import measure_publisher_rtt_ms
    from .redis_keys import (
        publisher_connection_key,
        publisher_srt_health_key,
        reader_connection_key,
        reader_srt_health_key,
    )
    from .redis_store import RedisStore
    from .srt_health import build_srt_health
    from .stream_normalizer import connection_identity, normalize_stream
except ImportError:
    from bitrate import calc_bitrate
    from mediamtx_client import MediaMTXClient, MediaMTXError, MediaMTXHTTPError
    from mediamtx_model import (
        DETAIL_ENDPOINTS,
        MINIMUM_MEDIAMTX_VERSION,
        OPTIONAL_SECURE_ENDPOINTS,
        index_details,
        is_supported_version,
    )
    from monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        measure_configured_rtt,
        resolve_monitoring_config,
    )
    from rtt import measure_publisher_rtt_ms
    from redis_keys import (
        publisher_connection_key,
        publisher_srt_health_key,
        reader_connection_key,
        reader_srt_health_key,
    )
    from redis_store import RedisStore
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
BITRATE_TTL = BITRATE_CFG["ttl"]
IGNORE_LOOPBACK = BITRATE_CFG["ignore_loopback"]
RTT_CFG = config["rtt"]
r = None
snapshot_store = None
mediamtx_client = None


def configure_runtime(raw_config: Dict[str, Any]) -> None:
    global config, API_BASE, REDIS_CFG, REDIS_HOST, REDIS_PORT, REDIS_KEY
    global COLLECTOR_CFG, JSON_OUTPUT_PATH, INTERVAL, IGNORE_PATH_PREFIXES
    global BITRATE_CFG, BITRATE_MIN_DT, BITRATE_SMOOTH_ALPHA, BITRATE_TTL
    global IGNORE_LOOPBACK, RTT_CFG

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
    BITRATE_TTL = BITRATE_CFG["ttl"]
    IGNORE_LOOPBACK = BITRATE_CFG["ignore_loopback"]
    RTT_CFG = config["rtt"]


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


def fetch(endpoint: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Holt JSON vom MediaMTX-API-Endpunkt. Gibt dict mit 'items' zurück (Liste),
    oder {'items': []} bei Fehlern.
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


# ---------------------------------------------------------------------------
# Kernfunktion: Sammeln und Speichern
# ---------------------------------------------------------------------------


def collect_and_store() -> None:
    """
    Sammelt Pfad-, Publisher- und Reader-Infos aus der MediaMTX-API,
    reichert diese um berechnete Bitraten an und schreibt das Ergebnis
    nach Redis und optional als JSON-Datei.
    """
    info = fetch("/v3/info")
    mediamtx_version = info.get("version")
    if not is_supported_version(mediamtx_version):
        required = ".".join(str(part) for part in MINIMUM_MEDIAMTX_VERSION)
        shown_version = mediamtx_version or "unbekannt"
        logging.error(
            "❌ MediaMTX %s wird nicht unterstützt; erforderlich ist v%s oder neuer.",
            shown_version,
            required,
        )
        return

    # API-Aufrufe (alle Protokolllisten einmal zentral einsammeln)
    paths = fetch("/v3/paths/list").get("items", [])
    details = index_details({
        obj_type: fetch(endpoint).get("items", [])
        for obj_type, endpoint in DETAIL_ENDPOINTS.items()
    })

    aggregated = []
    now = time.time()

    for path in paths:
        name: str = path.get("name", "")

        if any(name.startswith(prefix) for prefix in IGNORE_PATH_PREFIXES):
            logging.debug(f"⏭️ Interner Pfad ignoriert: {name}")
            continue

        forward_destinations = fetch(
            "/v3/paths/forward/list", params={"path": name}
        ).get("items", [])
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
                ttl=BITRATE_TTL,
            )

        if api_rx_mbps is not None:
            entry["source"]["bitrate_mbps"] = round(float(api_rx_mbps), 2)
        else:
            entry["source"]["bitrate_mbps"] = pub_calc_mbps

        # -----------------------------------------
        # SRT liefert Transport-RTT; für andere Protokolle bleibt ICMP separat.
        # -----------------------------------------
        remote = src_details.get("remoteAddr", "")
        if src_type == "srtConn" and src_details.get("msRTT") is not None:
            entry["source"]["transport_rtt_ms"] = round(
                float(src_details["msRTT"]), 2
            )
        elif remote:
            try:
                rtt_ms = measure_configured_rtt(
                    r,
                    remote_addr=remote,
                    rtt_config=RTT_CFG,
                    measure_func=measure_publisher_rtt_ms,
                )
                if rtt_ms is not None:
                    entry["source"]["icmp_rtt_ms"] = round(rtt_ms, 2)
            except Exception as e:
                logging.debug(f"RTT-Messung fehlgeschlagen für {name} ({remote}): {e}")

        if src_type == "srtConn":
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
                )
            entry["readers"].append(reader_entry)

        aggregated.append(entry)

    # -----------------------------------------------------------------------
    # Ergebnis nach Redis und optional als JSON-Datei schreiben
    # -----------------------------------------------------------------------
    try:
        snapshot_store.write_snapshot(REDIS_KEY, aggregated)
        logging.info(
            f"✅ {len(aggregated)} Pfade in Redis gespeichert (Key: {REDIS_KEY})."
        )
    except Exception as e:
        logging.error(f"❌ Redis-Fehler beim Schreiben von {REDIS_KEY}: {e}")

    try:
        Path(JSON_OUTPUT_PATH).write_text(
            json.dumps(aggregated, indent=2), encoding="utf-8"
        )
        logging.info(f"💾 JSON gespeichert unter {JSON_OUTPUT_PATH}")
    except Exception as e:
        logging.error(f"❌ Fehler beim Schreiben der JSON-Datei: {e}")


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
