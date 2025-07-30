#!/usr/bin/env python3
"""
mediamtx_collector.py – Streamdaten-Monitoring für MediaMTX

Erfasst alle aktiven Pfade, Quellen, Leser und Bitraten von einem MediaMTX-Server.
Speichert:
- in Redis (Key: mediamtx:streams:latest)
- optional als JSON-Datei (z. B. /tmp/mediamtx_streams.json)

Läuft als eigenständiger Dienst analog zu mediamtx_system.py.
Die Konfiguration erfolgt über collector.yaml.
"""

import requests
import redis
import yaml
import json
import sys
import time
import logging
import argparse
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from reader_bitrate import calculate_reader_bitrate, store_reader_state

# 🔧 Konfigurationsdatei laden
CONFIG_PATH = "/opt/mediamtx-monitoring-backend/config/collector.yaml"
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"❌ Fehler beim Laden der Konfigurationsdatei: {e}")
    sys.exit(1)

# 🔗 Konfigurationswerte extrahieren
API_BASE = config.get("api_base_url", "http://localhost:9997")
redis_cfg = config.get("redis", {})
REDIS_HOST = redis_cfg.get("host", "localhost")
REDIS_PORT = redis_cfg.get("port", 6379)
REDIS_KEY = redis_cfg.get("key", "mediamtx:streams:latest")
JSON_OUTPUT_PATH = config.get("output_json_path", "/tmp/mediamtx_streams.json")
INTERVAL = config.get("interval_seconds", 10)

# 📝 Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# 🧠 Redis-Verbindung testen
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    logging.info("🔌 Verbindung zu Redis hergestellt.")
except Exception as e:
    logging.error(f"❌ Verbindung zu Redis fehlgeschlagen: {e}")
    sys.exit(1)

def fetch(endpoint: str) -> dict:
    """Holt JSON-Daten vom angegebenen MediaMTX-Endpunkt."""
    try:
        res = requests.get(f"{API_BASE}{endpoint}")
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logging.warning(f"⚠️ API-Fehler bei {endpoint}: {e}")
        return {"items": []}

def collect_and_store():
    """Sammelt Pfad-, Reader- und Verbindungsinformationen aus MediaMTX."""
    paths = fetch("/v3/paths/list").get("items", [])
    srtconns = {s["id"]: s for s in fetch("/v3/srtconns/list").get("items", [])}
    rtmpconns = {r["id"]: r for r in fetch("/v3/rtmpconns/list").get("items", [])}
    webrtcs = {w["id"]: w for w in fetch("/v3/webrtcsessions/list").get("items", [])}
    rtspconns = {r["session"]: r for r in fetch("/v3/rtspconns/list").get("items", [])}
    hlsmuxers = fetch("/v3/hlsmuxers/list").get("items", [])
    hls_by_path = {h["path"]: h for h in hlsmuxers}

    aggregated = []
    now = time.time()

    for path in paths:
        name = path.get("name")
        source = path.get("source", {})
        readers = path.get("readers", [])
        bytes_sent = path.get("bytesSent", 0)

        entry = {
            "name": name,
            "source": {
                "type": source.get("type"),
                "id": source.get("id"),
                "details": srtconns.get(source.get("id")) if source.get("type") == "srtConn" else {}
            },
            "tracks": path.get("tracks", []),
            "bytesReceived": path.get("bytesReceived"),
            "bytesSent": bytes_sent,
            "readers": []
        }

        for reader in readers:
            rtype = reader.get("type")
            rid = reader.get("id")

            if rtype == "srtConn":
                data = srtconns.get(rid, {})
            elif rtype == "rtmpConn":
                data = rtmpconns.get(rid, {})
            elif rtype == "webRTCSession":
                data = webrtcs.get(rid, {})
            elif rtype == "hlsMuxer":
                data = hls_by_path.get(name, {})
            elif rtype == "rtspSession":
                data = rtspconns.get(rid, {})
            else:
                data = {}

            # Nur Remote-Clients analysieren
            remote = data.get("remoteAddr", "")
            if remote.startswith("127.") or remote.startswith("[::1]") or remote.startswith("::1"):
                continue

            # 📊 Bitrate berechnen
            reader_bytes = data.get("bytesSent")
            bitrate_mbps = None
            if reader_bytes is not None:
                bitrate_mbps = calculate_reader_bitrate(r, rid, reader_bytes, now)
                store_reader_state(r, rid, reader_bytes, now)

            entry["readers"].append({
                "type": rtype,
                "id": rid,
                "bitrate_mbps": bitrate_mbps,
                "details": data
            })

        aggregated.append(entry)

    # Redis schreiben
    try:
        r.set(REDIS_KEY, json.dumps(aggregated))
        logging.info(f"✅ {len(aggregated)} Pfade in Redis gespeichert.")
    except Exception as e:
        logging.error(f"❌ Redis-Fehler: {e}")

    # JSON schreiben
    try:
        Path(JSON_OUTPUT_PATH).write_text(json.dumps(aggregated, indent=2))
        logging.info(f"💾 JSON gespeichert unter {JSON_OUTPUT_PATH}")
    except Exception as e:
        logging.error(f"❌ Fehler beim Schreiben der JSON-Datei: {e}")

def main(run_once: bool = False):
    """Startet den Collector einmalig oder dauerhaft im Intervall."""
    if run_once:
        collect_and_store()
    else:
        scheduler = BackgroundScheduler()
        scheduler.add_job(collect_and_store, 'interval', seconds=INTERVAL)
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
