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
1) MediaMTX-API abfragen (Paths, SRT/RTMP/WebRTC/RTSP, HLS).
2) Pro Path:
   - Publisher-Details auflösen (je nach Typ).
   - Publisher-Bitrate: API (SRT) bevorzugen; sonst Delta aus bytesReceived.
   - Reader-Liste auflösen; pro Reader Bitrate: API (SRT) bevorzugen; sonst Delta aus bytesSent.
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

import redis
import requests
import yaml
from apscheduler.schedulers.background import BackgroundScheduler

# Einheitliche Bitraten-Berechnung (Publisher & Reader)
from bitrate import calc_bitrate

# RTT nur für Publisher (Nicht-SRT)
from rtt import measure_publisher_rtt_ms


# ---------------------------------------------------------------------------
# Konfiguration laden
# ---------------------------------------------------------------------------

CONFIG_PATH = "/opt/mediamtx-monitoring-backend/config/collector.yaml"

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
except Exception as e:
    print(f"❌ Fehler beim Laden der Konfigurationsdatei {CONFIG_PATH}: {e}")
    sys.exit(1)

API_BASE: str = config.get("api_base_url", "http://localhost:9997")
REDIS_CFG: Dict[str, Any] = config.get("redis", {}) or {}
REDIS_HOST: str = REDIS_CFG.get("host", "localhost")
REDIS_PORT: int = int(REDIS_CFG.get("port", 6379))
REDIS_KEY: str = REDIS_CFG.get("key", "mediamtx:streams:latest")
JSON_OUTPUT_PATH: str = config.get("output_json_path", "/tmp/mediamtx_streams.json")
INTERVAL: int = int(config.get("interval_seconds", 10))

BITRATE_CFG: Dict[str, Any] = config.get("bitrate", {}) or {}
BITRATE_MIN_DT: float = float(BITRATE_CFG.get("min_dt", 0.5))
BITRATE_SMOOTH_ALPHA: Optional[float] = BITRATE_CFG.get("smooth_alpha", 0.5)
if BITRATE_SMOOTH_ALPHA is not None:
    BITRATE_SMOOTH_ALPHA = float(BITRATE_SMOOTH_ALPHA)
BITRATE_TTL: int = int(BITRATE_CFG.get("ttl", 300))
IGNORE_LOOPBACK: bool = bool(BITRATE_CFG.get("ignore_loopback", True))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ---------------------------------------------------------------------------
# Redis-Verbindung testen
# ---------------------------------------------------------------------------

try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    logging.info("🔌 Verbindung zu Redis hergestellt.")
except Exception as e:
    logging.error(f"❌ Verbindung zu Redis fehlgeschlagen: {e}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def fetch(endpoint: str) -> Dict[str, Any]:
    """
    Holt JSON vom MediaMTX-API-Endpunkt. Gibt dict mit 'items' zurück (Liste),
    oder {'items': []} bei Fehlern.
    """
    url = f"{API_BASE}{endpoint}"
    try:
        res = requests.get(url, timeout=3.0)
        res.raise_for_status()
        data = res.json()
        # MediaMTX liefert i. d. R. {'items': [...]}
        if isinstance(data, dict) and "items" in data:
            return data
        return {"items": []}
    except Exception as e:
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


def get_details_by_type(
    obj_type: Optional[str],
    obj_id: Optional[str],
    name: str,
    srtconns: Dict[str, Any],
    rtmpconns: Dict[str, Any],
    webrtcs: Dict[str, Any],
    rtspconns: Dict[str, Any],
    hls_by_path: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Liefert das Detailobjekt passend zum Verbindungstyp.
    Für HLS auf Reader-Seite wird per Path aufgelöst.
    """
    if obj_type == "srtConn":
        return srtconns.get(obj_id or "", {})
    if obj_type == "rtmpConn":
        return rtmpconns.get(obj_id or "", {})
    if obj_type == "webRTCSession":
        return webrtcs.get(obj_id or "", {})
    if obj_type == "rtspSession":
        # RTSP mappt häufig über 'session' statt 'id'
        return rtspconns.get(obj_id or "", {})
    if obj_type == "hlsMuxer":
        # HLS-Reader werden über den Pfad gefunden
        return hls_by_path.get(name, {})
    return {}


# ---------------------------------------------------------------------------
# Kernfunktion: Sammeln und Speichern
# ---------------------------------------------------------------------------

def collect_and_store() -> None:
    """
    Sammelt Pfad-, Publisher- und Reader-Infos aus der MediaMTX-API,
    reichert diese um berechnete Bitraten an und schreibt das Ergebnis
    nach Redis und optional als JSON-Datei.
    """
    # API-Aufrufe (alle Listen einmal zentral einsammeln)
    paths = fetch("/v3/paths/list").get("items", [])
    srtconns = {s.get("id"): s for s in fetch("/v3/srtconns/list").get("items", [])}
    rtmpconns = {x.get("id"): x for x in fetch("/v3/rtmpconns/list").get("items", [])}
    webrtcs = {w.get("id"): w for w in fetch("/v3/webrtcsessions/list").get("items", [])}
    rtspconns = {rs.get("session"): rs for rs in fetch("/v3/rtspconns/list").get("items", [])}
    hlsmuxers = fetch("/v3/hlsmuxers/list").get("items", [])
    hls_by_path = {h.get("path"): h for h in hlsmuxers}

    aggregated = []
    now = time.time()

    for path in paths:
        name: str = path.get("name", "")
        source = path.get("source", {}) or {}
        readers = path.get("readers", []) or []

        # Publisher/Source auflösen
        src_type: Optional[str] = source.get("type")
        src_id: Optional[str] = source.get("id")
        src_details = get_details_by_type(
            src_type, src_id, name,
            srtconns, rtmpconns, webrtcs, rtspconns, hls_by_path
        )

        # Grundobjekt für die Ausgabe
        entry: Dict[str, Any] = {
            "name": name,
            "source": {
                "type": src_type,
                "id": src_id,
                "details": src_details,
            },
            "tracks": path.get("tracks", []),
            "bytesReceived": int(path.get("bytesReceived") or 0),
            "bytesSent": int(path.get("bytesSent") or 0),
            "readers": [],
        }

        # ---------------------------
        # Publisher-Bitrate berechnen
        # ---------------------------
        # API-Rate bevorzugen (nur SRT liefert typischerweise mbpsReceiveRate)
        api_rx_mbps = src_details.get("mbpsReceiveRate")
        # Fallback: aus Bytes-Deltas (bytesReceived) berechnen
        # Quelle bytes: bevorzugt die Detailverbindung, sonst Path-Feld
        pub_bytes_now = int(src_details.get("bytesReceived") or entry["bytesReceived"] or 0)

        pub_key = f"pub:{name}:{src_type}:{src_id or src_details.get('remoteAddr') or 'n/a'}"
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
        # --- Publisher-RTT (nur für Nicht-SRT) ---
        # -----------------------------------------
        remote = src_details.get("remoteAddr", "")
        if (src_type != "srtConn") and remote:
            try:
                rtt_ms = measure_publisher_rtt_ms(
                    r,
                    remote_addr=remote,
                    ewma_alpha=float(BITRATE_SMOOTH_ALPHA or 0.5),
                    min_period_s=30,
                    ttl_s=300,
                    key_prefix="rtt:pub",
                    timeout_s=0.9,
                )
                if rtt_ms is not None:
                    entry["source"]["rtt_ms"] = round(rtt_ms, 2)
            except Exception as e:
                logging.debug(f"RTT-Messung fehlgeschlagen für {name} ({remote}): {e}")

        # ------------------------
        # Reader-Liste aufbereiten
        # ------------------------
        for rd in readers:
            rtype: Optional[str] = rd.get("type")
            rid: Optional[str] = rd.get("id")

            # Detailobjekt zum Reader
            rd_details = get_details_by_type(
                rtype, rid, name,
                srtconns, rtmpconns, webrtcs, rtspconns, hls_by_path
            )

            # Optional lokale/loopback-Reader ignorieren
            if IGNORE_LOOPBACK:
                remote = rd_details.get("remoteAddr", "")
                if is_loopback(remote):
                    continue

            # Reader-Bitrate: API (SRT) bevorzugen, sonst Delta aus bytesSent
            api_tx_mbps = rd_details.get("mbpsSendRate")
            rd_bytes_now = int(rd_details.get("bytesSent") or 0)

            rd_key = f"rd:{name}:{rtype}:{rid or rd_details.get('remoteAddr') or 'n/a'}"
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

            entry["readers"].append(
                {
                    "type": rtype,
                    "id": rid,
                    "bitrate_mbps": bitrate_final,
                    "details": rd_details,
                }
            )

        aggregated.append(entry)

    # -----------------------------------------------------------------------
    # Ergebnis nach Redis und optional als JSON-Datei schreiben
    # -----------------------------------------------------------------------
    try:
        r.set(REDIS_KEY, json.dumps(aggregated))
        logging.info(f"✅ {len(aggregated)} Pfade in Redis gespeichert (Key: {REDIS_KEY}).")
    except Exception as e:
        logging.error(f"❌ Redis-Fehler beim Schreiben von {REDIS_KEY}: {e}")

    try:
        Path(JSON_OUTPUT_PATH).write_text(json.dumps(aggregated, indent=2), encoding="utf-8")
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
