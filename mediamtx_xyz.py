#!/usr/bin/env python3
"""
mediamtx_XYZ.py – <kurze Funktionsbeschreibung>

Erfasst <Datenquelle> und speichert sie:
- in Redis unter <Key>
- optional als JSON-Datei unter <Pfad>

Läuft als eigenständiger Dienst analog zu mediamtx_collector.py.
Die Konfiguration erfolgt über die zentrale collector.yaml.
"""

import time
import socket
import logging
import redis
import yaml
import json
from apscheduler.schedulers.background import BackgroundScheduler

# 📁 Konfigurationsdatei einlesen
CONFIG_PATH = "/opt/mediamtx-monitoring-backend/collector.yaml"
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

# 🔧 Redis-Konfiguration
redis_cfg = config.get("redis", {})
REDIS_HOST = redis_cfg.get("host", "localhost")
REDIS_PORT = redis_cfg.get("port", 6379)
REDIS_KEY = "<DEIN_KEY>"  # z. B. mediamtx:system:latest

# 💾 Datei-Ausgabe konfigurieren
output_cfg = config.get("XYZ_monitor", {})  # z. B. "system_monitor"
JSON_OUTPUT_PATH = output_cfg.get("output_json_path", "/tmp/XYZ.json")
INTERVAL_SECONDS = output_cfg.get("interval_seconds", 10)

# 📝 Logging einrichten
log_cfg = config.get("logging", {})
log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

# 🔌 Redis-Verbindung
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    logging.info("🔌 Redis-Verbindung erfolgreich.")
except Exception as e:
    logging.error(f"❌ Redis-Verbindung fehlgeschlagen: {e}")
    exit(1)

# 🔁 Hauptfunktion
def collect_and_store():
    try:
        data = {
            "host": socket.gethostname(),
            "timestamp": time.time(),
            "example_key": "example_value"
        }

        r.set(REDIS_KEY, json.dumps(data))
        logging.debug(f"📦 Daten in Redis unter {REDIS_KEY} gespeichert.")

        with open(JSON_OUTPUT_PATH, "w") as f:
            json.dump(data, f)
        logging.debug(f"💾 JSON gespeichert unter {JSON_OUTPUT_PATH}")
    except Exception as e:
        logging.error(f"❌ Fehler bei collect_and_store(): {e}")

# 🕒 Scheduler starten
scheduler = BackgroundScheduler()
scheduler.add_job(collect_and_store, "interval", seconds=INTERVAL_SECONDS)
scheduler.start()
logging.info(f"🚀 Dienst gestartet (alle {INTERVAL_SECONDS} s)")

try:
    while True:
        time.sleep(60)
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    logging.info("🛑 Dienst gestoppt.")
