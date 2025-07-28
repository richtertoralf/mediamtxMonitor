#!/usr/bin/env python3
"""
mediamtx_system.py – Systemmonitoring für MediaMTX

Erfasst CPU, RAM, Swap, Disk, Netzwerk und Temperaturinformationen und speichert:
- in Redis (Key: mediamtx:system:latest)
- optional als JSON-Datei (z. B. /tmp/mediamtx_system.json)

Läuft als eigenständiger Dienst analog zu mediamtx_collector.py.
Die Konfiguration erfolgt über collector.yaml.
"""

import psutil
import redis
import yaml
import json
import socket
import time
import logging
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler

# 🔧 Konfigurationsdatei laden
CONFIG_PATH = "/opt/mediamtx-monitoring-backend/config/collector.yaml"
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"❌ Fehler beim Laden der Konfigurationsdatei: {e}")
    exit(1)

# 🔗 Konfigurationswerte extrahieren
redis_cfg = config.get("redis", {})
REDIS_HOST = redis_cfg.get("host", "localhost")
REDIS_PORT = redis_cfg.get("port", 6379)
REDIS_KEY = redis_cfg.get("system_key", "mediamtx:system:latest")
JSON_OUTPUT_PATH = config.get("system_output_json_path", "/tmp/mediamtx_system.json")
INTERVAL_SECONDS = config.get("system_interval_seconds", 10)

# 📝 Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# 🧠 Redis-Verbindung aufbauen
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    logging.info("🔌 Verbindung zu Redis hergestellt.")
except Exception as e:
    logging.error(f"❌ Verbindung zu Redis fehlgeschlagen: {e}")
    exit(1)


def get_temperatures():
    """Temperatursensoren auslesen (falls verfügbar)"""
    try:
        temps = psutil.sensors_temperatures()
        return {k: [t._asdict() for t in v] for k, v in temps.items()}
    except Exception as e:
        logging.warning(f"🌡️ Temperaturdaten nicht verfügbar: {e}")
        return {}


def collect_and_store():
    """Systemdaten erfassen und speichern"""
    now = time.time()
    try:
        data = {
            "host": socket.gethostname(),
            "timestamp": now,
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory()._asdict(),
            "swap": psutil.swap_memory()._asdict(),
            "disk": psutil.disk_usage("/")._asdict(),
            "loadavg": psutil.getloadavg() if hasattr(psutil, "getloadavg") else None,
            "net_io": psutil.net_io_counters()._asdict(),
            "temperature": get_temperatures(),
        }

        # In Redis speichern
        r.set(REDIS_KEY, json.dumps(data))
        logging.debug("📊 Systemdaten in Redis gespeichert.")

        # Optional als JSON-Datei
        Path(JSON_OUTPUT_PATH).write_text(json.dumps(data, indent=2))
        logging.debug(f"💾 JSON gespeichert unter {JSON_OUTPUT_PATH}")

    except Exception as e:
        logging.error(f"❌ Fehler beim Erfassen der Systemdaten: {e}")


# ▶️ Scheduler starten
scheduler = BackgroundScheduler()
scheduler.add_job(collect_and_store, "interval", seconds=INTERVAL_SECONDS)
scheduler.start()
logging.info("🚀 Systemmonitor gestartet.")

try:
    while True:
        time.sleep(60)
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    logging.info("🛑 Systemmonitor gestoppt.")
