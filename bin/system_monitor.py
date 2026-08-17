#!/usr/bin/env python3
"""
system_monitor.py – Systemmonitoring für MediaMTX

Erfasst CPU, RAM, Swap, Disk, Netzwerk und Temperaturinformationen und speichert:
- in Redis (Key: mediamtx:system:latest)
- optional als JSON-Datei (z. B. /tmp/mediamtx_system.json)

Läuft als eigenständiger Dienst analog zu mediamtx_collector.py.
Die Konfiguration erfolgt über collector.yaml.
"""

import ipaddress
import json
import socket
import time
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict

try:
    from .monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from .redis_store import RedisStore
except ImportError:
    from monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from redis_store import RedisStore

config = resolve_monitoring_config({})
redis_cfg = config["redis"]
REDIS_HOST = redis_cfg["host"]
REDIS_PORT = redis_cfg["port"]
system_monitor_cfg = config["system_monitor"]
REDIS_KEY = system_monitor_cfg["redis_key"]
JSON_OUTPUT_PATH = system_monitor_cfg["output_json_path"]
INTERVAL_SECONDS = system_monitor_cfg["interval_seconds"]
r = None
snapshot_store = None
psutil = None


def _is_traffic_interface(name: str) -> bool:
    return not (
        name.startswith("lo")
        or name.startswith("docker")
        or name.startswith("br")
        or name.startswith("veth")
        or name.startswith("tun")
    )


def _is_identity_interface(name: str) -> bool:
    return not (name.startswith("docker") or name.startswith("veth"))


def configure_runtime(raw_config: Dict[str, Any]) -> None:
    global config, redis_cfg, REDIS_HOST, REDIS_PORT
    global system_monitor_cfg, REDIS_KEY, JSON_OUTPUT_PATH, INTERVAL_SECONDS

    config = resolve_monitoring_config(raw_config)
    redis_cfg = config["redis"]
    REDIS_HOST = redis_cfg["host"]
    REDIS_PORT = redis_cfg["port"]
    system_monitor_cfg = config["system_monitor"]
    REDIS_KEY = system_monitor_cfg["redis_key"]
    JSON_OUTPUT_PATH = system_monitor_cfg["output_json_path"]
    INTERVAL_SECONDS = system_monitor_cfg["interval_seconds"]


def initialize_runtime(config_path: Path | str = DEFAULT_CONFIG_PATH) -> None:
    global r, snapshot_store, psutil

    import psutil as psutil_module
    import redis

    psutil = psutil_module
    try:
        configure_runtime(load_monitoring_config(config_path))
    except Exception as exc:
        print(f"❌ Fehler beim Laden der Konfigurationsdatei: {exc}")
        sys.exit(1)
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        snapshot_store = RedisStore(r)
        logging.info("🔌 Verbindung zu Redis hergestellt.")
    except Exception as exc:
        logging.error(f"❌ Verbindung zu Redis fehlgeschlagen: {exc}")
        sys.exit(1)

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
        if _is_traffic_interface(name)
    }
    return {
        "bytes_recv": sum(stats.bytes_recv for stats in filtered.values()),
        "bytes_sent": sum(stats.bytes_sent for stats in filtered.values()),
    }


def get_server_ips() -> list[str]:
    """Return up to three relevant IPv4 addresses in system interface order."""
    addresses = []
    seen = set()
    for name, interface_addresses in psutil.net_if_addrs().items():
        if not _is_identity_interface(name):
            continue
        for address in interface_addresses:
            if address.family != socket.AF_INET:
                continue
            parsed_address = ipaddress.ip_address(address.address)
            if parsed_address.is_loopback or parsed_address.is_link_local:
                continue
            if address.address in seen:
                continue
            addresses.append(address.address)
            seen.add(address.address)
            if len(addresses) == 3:
                return addresses
    return addresses

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
            "server_ips": get_server_ips(),
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

        snapshot_store.write_snapshot(REDIS_KEY, data)
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
        data = snapshot_store.read_snapshot(REDIS_KEY)
        if data is None:
            return {}

        return {
            "host": data.get("host"),
            "server_ips": data.get("server_ips", []),
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


def _run_interval_loop(job: Callable[[], None], interval_seconds: float) -> None:
    next_run = time.monotonic() + interval_seconds
    while True:
        time.sleep(max(0.0, next_run - time.monotonic()))
        try:
            job()
        except Exception:
            logging.exception("❌ Unbehandelter Fehler im Systemmonitor-Durchlauf.")

        next_run += interval_seconds
        now = time.monotonic()
        if next_run <= now:
            missed_intervals = int((now - next_run) // interval_seconds) + 1
            next_run += missed_intervals * interval_seconds


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    initialize_runtime()

    logging.info("🚀 Systemmonitor gestartet.")

    try:
        _run_interval_loop(collect_and_store, INTERVAL_SECONDS)
    except (KeyboardInterrupt, SystemExit):
        logging.info("🛑 Systemmonitor gestoppt.")


if __name__ == "__main__":
    main()
