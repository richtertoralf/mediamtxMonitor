#!/usr/bin/env python3

import requests
import redis
import json
import sys
import time
import logging
import argparse
from apscheduler.schedulers.background import BackgroundScheduler

# --- Konfiguration ---
MEDIA_MTX_API_URL = "http://localhost:9997"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_KEY = "mediamtx:streams:latest"
JSON_OUTPUT_PATH = "/tmp/mediamtx_streams.json"

# --- Logging einrichten ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# --- Redis-Verbindung ---
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
except Exception as e:
    logging.error(f"Verbindung zu Redis fehlgeschlagen: {e}")
    sys.exit(1)

# --- Daten holen & aggregieren ---
def fetch_data(endpoint):
    try:
        response = requests.get(f"{MEDIA_MTX_API_URL}{endpoint}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        logging.error(f"Verbindung zu MediaMTX unter {MEDIA_MTX_API_URL} fehlgeschlagen. Läuft der Server?")
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP-Fehler bei {endpoint}: {e}")
    except json.decoder.JSONDecodeError:
        logging.error(f"Ungültiges JSON von {endpoint}")
    except Exception as e:
        logging.error(f"Allgemeiner Fehler bei {endpoint}: {e}")
    return {}

def collect_and_store():
    paths = fetch_data("/v3/paths/list")
    srtconns = fetch_data("/v3/srtconns/list")

    if not paths or "items" not in paths:
        logging.warning("Keine 'paths'-Daten erhalten.")
        return

    aggregated = []

    for path in paths.get("items", []):
        name = path.get("name")
        source_type = path.get("source", {}).get("type", "unknown")
        tracks = path.get("tracks", [])
        bytes_received = path.get("bytesReceived", 0)
        readers = len(path.get("readers", []))

        entry = {
            "name": name,
            "sourceType": source_type,
            "tracks": tracks,
            "bytesReceived": bytes_received,
            "readers": readers,
        }

        if source_type == "srtConn":
            srt_data = next((s for s in srtconns.get("items", []) if s.get("path") == name), None)
            if srt_data:
                entry.update({
                    "rtt": srt_data.get("msRTT"),
                    "recvRateMbps": srt_data.get("mbpsReceiveRate"),
                    "linkCapacityMbps": srt_data.get("mbpsLinkCapacity"),
                })

        aggregated.append(entry)

    # In Redis speichern
    try:
        r.set(REDIS_KEY, json.dumps(aggregated))
        logging.info(f"{len(aggregated)} Einträge in Redis gespeichert.")
    except Exception as e:
        logging.error(f"Fehler beim Speichern in Redis: {e}")

    # In Datei schreiben
    try:
        with open(JSON_OUTPUT_PATH, "w") as f:
            json.dump(aggregated, f, indent=2)
        logging.info(f"JSON-Datei geschrieben: {JSON_OUTPUT_PATH}")
    except Exception as e:
        logging.error(f"Fehler beim Schreiben der JSON-Datei: {e}")

# --- Hauptfunktion ---
def main(run_once=False):
    if run_once:
        collect_and_store()
    else:
        scheduler = BackgroundScheduler()
        scheduler.add_job(collect_and_store, 'interval', seconds=2)
        scheduler.start()
        logging.info("MediaMTX Collector läuft (alle 2 Sekunden)... [STRG+C zum Beenden]")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            logging.info("MediaMTX Collector wurde gestoppt.")

# --- Kommandozeilenparameter ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MediaMTX Stream Collector")
    parser.add_argument("--once", action="store_true", help="Nur einmalige Abfrage und Ausgabe")
    args = parser.parse_args()

    main(run_once=args.once)
