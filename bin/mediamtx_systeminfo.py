#!/usr/bin/env python3
"""
mediamtx_systeminfo.py – Systemmonitoring für MediaMTX

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
    level=logging.DEBUG,
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

# 🌡️ Temperatur auslesen
def get_temperatures():
    try:
        temps = psutil.sensors_temperatures()
        return {k: [t._asdict() for t in v] for k, v in temps.items()}
    except Exception as e:
        logging.warning(f"🌡️ Temperaturdaten nicht verfügbar: {e}")
        return {}

# 📶 Netzwerkfilter (nur echte NICs)
def get_filtered_net_io():
    """
    Gibt aufsummierte Netzwerknutzung (bytes_recv, bytes_sent) aller physikalischen NICs zurück.
    Ignoriert Loopback, Docker, virtuelle Bridges, VPNs etc.
    """
    interfaces = psutil.net_io_counters(pernic=True)
    filtered = {
        name: stats for name, stats in interfaces.items()
        if not (
            name.startswith("lo")
            or name.startswith("docker")
            or name.startswith("br")
            or name.startswith("veth")
            # or name.startswith("wg") # wireguard Interface
            or name.startswith("tun")
        )
    }
    return {
        "bytes_recv": sum(stats.bytes_recv for stats in filtered.values()),
        "bytes_sent": sum(stats.bytes_sent for stats in filtered.values()),
    }

# ⏱️ Zwischenspeicher für Netzwerk-Bitrate
_last_net_io = {
    "bytes_recv": None,
    "bytes_sent": None,
    "timestamp": None
}

# 📊 Netzwerkbitrate berechnen
def calculate_network_bitrate(current_net_io, current_time):
    global _last_net_io

    prev_recv = _last_net_io["bytes_recv"]
    prev_sent = _last_net_io["bytes_sent"]
    prev_time = _last_net_io["timestamp"]

    if prev_recv is None or prev_sent is None or prev_time is None:
        _last_net_io = {
            "bytes_recv": current_net_io["bytes_recv"],
            "bytes_sent": current_net_io["bytes_sent"],
            "timestamp": current_time
        }
        return {
            "net_mbit_rx": None,
            "net_mbit_tx": None
        }

    delta_recv = current_net_io["bytes_recv"] - prev_recv
    delta_sent = current_net_io["bytes_sent"] - prev_sent
    delta_time = current_time - prev_time

    _last_net_io = {
        "bytes_recv": current_net_io["bytes_recv"],
        "bytes_sent": current_net_io["bytes_sent"],
        "timestamp": current_time
    }

    if delta_time <= 0:
        return {
            "net_mbit_rx": None,
            "net_mbit_tx": None
        }

    net_mbit_rx = (delta_recv * 8) / delta_time / 1_000_000
    net_mbit_tx = (delta_sent * 8) / delta_time / 1_000_000

    return {
        "net_mbit_rx": round(net_mbit_rx, 2),
        "net_mbit_tx": round(net_mbit_tx, 2)
    }

# 📥 Daten sammeln und speichern
def collect_and_store():
    now = time.time()
    try:
        net_io = get_filtered_net_io()

        data = {
            "host": socket.gethostname(),
            "timestamp": now,
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory()._asdict(),
            "swap": psutil.swap_memory()._asdict(),
            "disk": psutil.disk_usage("/")._asdict(),
            "loadavg": psutil.getloadavg() if hasattr(psutil, "getloadavg") else None,
            "net_io": net_io,
            "temperature": get_temperatures(),
        }

        data["temperature_celsius"] = extract_temperature(data["temperature"])

        bitrate = calculate_network_bitrate(net_io, now)
        data.update(bitrate)
        logging.debug(f"📶 Netzwerk: RX {bitrate['net_mbit_rx']} Mbit/s, TX {bitrate['net_mbit_tx']} Mbit/s")

        r.set(REDIS_KEY, json.dumps(data))
        logging.debug("📊 Systemdaten in Redis gespeichert.")

        Path(JSON_OUTPUT_PATH).write_text(json.dumps(data, indent=2))
        logging.debug(f"💾 JSON gespeichert unter {JSON_OUTPUT_PATH}")

    except Exception as e:
        logging.error(f"❌ Fehler beim Erfassen der Systemdaten: {e}")

# 🌡️ Temperatur extrahieren
def extract_temperature(temp_data):
    """
    Extrahiert bevorzugt die Temperatur von 'coretemp' → 'Package id 0'.
    Falls nicht verfügbar, nimmt den ersten verfügbaren Sensorwert mit 'current'.
    """
    # Bevorzugt: Package id 0 bei coretemp
    for entry in temp_data.get("coretemp", []):
        if entry.get("label") == "Package id 0":
            return round(entry.get("current", 0), 1)

    # Fallback: erster beliebiger Sensorwert mit 'current'
    for group in temp_data.values():
        for sensor in group:
            if isinstance(sensor, dict) and "current" in sensor:
                return round(sensor["current"], 1)

    return None


# 📤 API-Datenstruktur bereitstellen
def get_system_info():
    try:
        raw = r.get(REDIS_KEY)
        if not raw:
            return {}
        data = json.loads(raw)

        return {
            "cpu_percent": data["cpu_percent"],
            "memory_total_bytes": data["memory"]["total"],
            "memory_used_bytes": data["memory"]["used"],
            "swap_total_bytes": data["swap"]["total"],
            "swap_used_bytes": data["swap"]["used"],
            "disk_total_bytes": data["disk"]["total"],
            "disk_used_bytes": data["disk"]["used"],
            "loadavg": data.get("loadavg", []),
            "net_mbit_rx": data.get("net_mbit_rx"),
            "net_mbit_tx": data.get("net_mbit_tx"),
            "temperature_celsius": extract_temperature(data.get("temperature", {}))
        }
    except Exception as e:
        logging.warning(f"⚠️ Fehler beim Parsen von Systemdaten: {e}")
        return {}

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
