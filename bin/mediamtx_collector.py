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
from typing import Any, Dict, Optional

try:
    from .bitrate import calc_bitrate
    from .mediamtx_client import MediaMTXClient, MediaMTXError, MediaMTXHTTPError
    from .mediamtx_model import (
        DETAIL_ENDPOINTS,
        MINIMUM_MEDIAMTX_VERSION,
        OPTIONAL_SECURE_ENDPOINTS,
        build_media_model,
        get_details_by_type,
        index_details,
        is_supported_version,
        track_codecs,
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
except ImportError:
    from bitrate import calc_bitrate
    from mediamtx_client import MediaMTXClient, MediaMTXError, MediaMTXHTTPError
    from mediamtx_model import (
        DETAIL_ENDPOINTS,
        MINIMUM_MEDIAMTX_VERSION,
        OPTIONAL_SECURE_ENDPOINTS,
        build_media_model,
        get_details_by_type,
        index_details,
        is_supported_version,
        track_codecs,
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

        source = path.get("source", {}) or {}
        readers = path.get("readers", []) or []

        # Publisher/Source auflösen
        src_type: Optional[str] = source.get("type")
        src_id: Optional[str] = source.get("id")
        src_details = get_details_by_type(src_type, src_id, details)
        tracks2 = path.get("tracks2", []) or []

        # Grundobjekt für die Ausgabe
        entry: Dict[str, Any] = {
            "name": name,
            "mediamtxVersion": mediamtx_version,
            "source": {
                "type": src_type,
                "id": src_id,
                "details": src_details,
            },
            "tracks2": tracks2,
            "tracks": track_codecs(tracks2),
            "media": build_media_model(tracks2),
            "inboundBytes": int(path.get("inboundBytes") or 0),
            "outboundBytes": int(path.get("outboundBytes") or 0),
            "inboundFramesInError": int(path.get("inboundFramesInError") or 0),
            "forwardDestinations": fetch(
                "/v3/paths/forward/list", params={"path": name}
            ).get("items", []),
            "readers": [],
        }

        # ---------------------------
        # Publisher-Bitrate berechnen
        # ---------------------------
        # API-Rate bevorzugen (nur SRT liefert typischerweise mbpsReceiveRate)
        api_rx_mbps = src_details.get("mbpsReceiveRate")
        # Fallback: aus Byte-Deltas berechnen. SRT behält native Transportzähler.
        # Quelle bytes: bevorzugt die Detailverbindung, sonst Path-Feld
        pub_bytes_now = int(
            src_details.get("inboundBytes")
            or (src_details.get("bytesReceived") if src_type == "srtConn" else 0)
            or entry["inboundBytes"]
            or 0
        )

        pub_identity = src_id or src_details.get("remoteAddr") or "n/a"
        pub_key = publisher_connection_key(
            name,
            src_type,
            pub_identity,
        )
        pub_calc_mbps = None
        if pub_bytes_now > 0:
            pub_calc_mbps = calc_bitrate(
                r,
                key=pub_key,
                bytes_now=pub_bytes_now,
                now=now,
                min_dt=BITRATE_MIN_DT,
                smooth_alpha=BITRATE_SMOOTH_ALPHA,
                ttl=BITRATE_TTL,
            )

        if api_rx_mbps is not None and float(api_rx_mbps) > 0:
            entry["source"]["bitrate_mbps"] = round(float(api_rx_mbps), 2)
        else:
            entry["source"]["bitrate_mbps"] = float(pub_calc_mbps or 0.0)

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
        for rd in readers:
            rtype: Optional[str] = rd.get("type")
            rid: Optional[str] = rd.get("id")

            # Detailobjekt zum Reader
            rd_details = get_details_by_type(rtype, rid, details)

            # Optional lokale/loopback-Reader ignorieren
            if IGNORE_LOOPBACK:
                remote = rd_details.get("remoteAddr", "")
                if is_loopback(remote):
                    continue

            # Reader-Bitrate: API (SRT) bevorzugen, sonst Delta aus outboundBytes
            api_tx_mbps = rd_details.get("mbpsSendRate")
            rd_bytes_now = int(
                rd_details.get("outboundBytes")
                or (rd_details.get("bytesSent") if rtype == "srtConn" else 0)
                or 0
            )

            reader_identity = rid or rd_details.get("remoteAddr") or "n/a"
            rd_key = reader_connection_key(name, rtype, reader_identity)
            rd_calc_mbps = None
            if rd_bytes_now > 0:
                rd_calc_mbps = calc_bitrate(
                    r,
                    key=rd_key,
                    bytes_now=rd_bytes_now,
                    now=now,
                    min_dt=BITRATE_MIN_DT,
                    smooth_alpha=BITRATE_SMOOTH_ALPHA,
                    ttl=BITRATE_TTL,
                )

            bitrate_final = (
                round(float(api_tx_mbps), 2)
                if (api_tx_mbps is not None and float(api_tx_mbps) > 0)
                else float(rd_calc_mbps or 0.0)
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


def main(run_once: bool = False) -> None:
    """
    Startet den Collector einmalig oder als dauerhaften Hintergrundjob.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    initialize_runtime()

    from apscheduler.schedulers.background import BackgroundScheduler

    if run_once:
        collect_and_store()
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(collect_and_store, "interval", seconds=INTERVAL)
    scheduler.start()
    logging.info("🚀 Stream-Collector gestartet.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logging.info("🛑 Collector gestoppt.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediaMTX Collector")
    parser.add_argument("--once", action="store_true", help="Nur einmal ausführen")
    args = parser.parse_args()
    main(run_once=args.once)
