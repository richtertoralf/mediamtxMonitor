#!/usr/bin/env python3
"""
MediaMTX Collector Script

Dieses Skript sammelt regelmäßig Statusdaten von einem MediaMTX-Server (per HTTP-API),
aggregiert sie und speichert sie:
- als JSON-Datei auf dem Dateisystem (z. B. zur Webanzeige)
- in Redis (z. B. für eine API)

Es kann entweder einmalig oder kontinuierlich im Hintergrund laufen (Scheduler).
Die Konfiguration erfolgt über eine YAML-Datei.

Autor: snowgames.live
Lizenz: MIT
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

# 🔧 Konfigurationsdatei laden
CONFIG_PATH = "/opt/mediamtx-monitoring-backend/config/collector.yaml"
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"❌ Fehler beim Laden der Konfigurationsdatei: {e}")
    sys.exit(1)

# 🔗 Konfigurationswerte extrahieren
API_BASE = config["api_base_url"]
REDIS_HOST = config["redis"]["host"]
REDIS_PORT = config["redis"]["port"]
REDIS_KEY = config["redis"]["key"]
JSON_OUTPUT_PATH = config["output_json_path"]
INTERVAL = config.get("interval_seconds", 2)

# 📝 Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# 🧠 Redis-Verbindung testen
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
except Exception as e:
    logging.error(f"❌ Verbindung zu Redis fehlgeschlagen: {e}")
    sys.exit(1)


def fetch(endpoint: str) -> dict:
    """
    Holt JSON-Daten vom angegebenen MediaMTX-Endpunkt.

    Args:
        endpoint (str): API-Endpunkt (z. B. "/v3/paths/list")

    Returns:
        dict: Antwortdaten (oder {"items": []} bei Fehler)
    """
    try:
        res = requests.get(f"{API_BASE}{endpoint}")
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logging.warning(f"⚠️ API-Fehler bei {endpoint}: {e}")
        return {"items": []}


def collect_and_store():
    """
    Aggregiert alle relevanten Streamdaten und speichert sie:
    - in Redis unter dem angegebenen Key
    - als JSON-Datei im Dateisystem
    """

    # API-Daten holen
    paths = fetch("/v3/paths/list").get("items", [])
    srtconns = {s["id"]: s for s in fetch("/v3/srtconns/list").get("items", [])}
    rtmpconns = {r["id"]: r for r in fetch("/v3/rtmpconns/list").get("items", [])}
    webrtcs = {w["id"]: w for w in fetch("/v3/webrtcsessions/list").get("items", [])}
    hlsmuxers = fetch("/v3/hlsmuxers/list").get("items", [])
    hls_by_path = {h["path"]: h for h in hlsmuxers}

    aggregated = []

    for path in paths:
        name = path.get("name")
        source = path.get("source", {})
        readers = path.get("readers", [])

        entry = {
            "name": name,
            "source": {
                "type": source.get("type"),
                "id": source.get("id"),
                "details": srtconns.get(source.get("id")) if source.get("type") == "srtConn" else {}
            },
            "tracks": path.get("tracks", []),
            "bytesReceived": path.get("bytesReceived"),
            "bytesSent": path.get("bytesSent"),
            "readers": []
        }

        for reader in readers:
            rtype = reader.get("type")
            rid = reader.get("id")

            # Verknüpfung mit konkreten Reader-Daten je nach Typ
            if rtype == "srtConn":
                data = srtconns.get(rid, {})
            elif rtype == "rtmpConn":
                data = rtmpconns.get(rid, {})
            elif rtype == "webRTCSession":
                data = webrtcs.get(rid, {})
            elif rtype == "hlsMuxer":
                data = hls_by_path.get(name, {})
            else:
                data = {}

            entry["readers"].append({
                "type": rtype,
                "id": rid,
                "details": data
            })

        aggregated.append(entry)

    # 🔁 Daten in Redis speichern
    try:
        r.set(REDIS_KEY, json.dumps(aggregated))
        logging.info(f"✅ {len(aggregated)} Pfade in Redis gespeichert.")
    except Exception as e:
        logging.error(f"❌ Redis-Fehler: {e}")

    # 💾 Daten als JSON-Datei speichern
    try:
        Path(JSON_OUTPUT_PATH).write_text(json.dumps(aggregated, indent=2))
        logging.info(f"💾 JSON gespeichert unter {JSON_OUTPUT_PATH}")
    except Exception as e:
        logging.error(f"❌ Fehler beim Schreiben der JSON-Datei: {e}")


def main(run_once: bool = False):
    """
    Startet den Collector entweder einmalig oder dauerhaft mit Intervall.

    Args:
        run_once (bool): Wenn True, wird nur ein Durchlauf gemacht.
    """
    if run_once:
        collect_and_store()
    else:
        scheduler = BackgroundScheduler()
        scheduler.add_job(collect_and_store, 'interval', seconds=INTERVAL)
        scheduler.start()
        logging.info(f"🔄 Collector läuft alle {INTERVAL} Sekunden...")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            logging.info("🛑 Collector beendet.")


# ▶️ CLI-Startpunkt
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediaMTX Collector")
    parser.add_argument("--once", action="store_true", help="Nur einmal ausführen")
    args = parser.parse_args()
    main(run_once=args.once)
