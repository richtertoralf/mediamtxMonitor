#!/usr/bin/env python3
"""
mediamtx_snapshots.py – Snapshot-Manager für MediaMTX-Streams

Startet pro aktivem Stream genau einen ffmpeg-Prozess zur Snapshot-Erzeugung.
Verwendet eine zentrale YAML-Konfiguration (collector.yaml).

- Speichert Snapshots im angegebenen Verzeichnis
- Erkennt automatisch neue/entfallene Streams
- Entfernt veraltete Snapshot-Dateien

Läuft als eigenständiger Dienst analog zu mediamtx_collector.py und mediamtx_system.py.
"""

import redis
import subprocess
import time
import os
import logging
import json
import yaml
from pathlib import Path
from glob import glob

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
snapshot_cfg = config.get("snapshots", {})
REDIS_HOST = redis_cfg.get("host", "localhost")
REDIS_PORT = redis_cfg.get("port", 6379)
REDIS_KEY = redis_cfg.get("key", "mediamtx:streams:latest")
OUTPUT_DIR = snapshot_cfg.get("output_dir", "/tmp/snapshots")
PORT = snapshot_cfg.get("port", 8554)
PROTOCOL = snapshot_cfg.get("protocol", "rtsp")
INTERVAL = int(snapshot_cfg.get("interval", 10))
WIDTH = snapshot_cfg.get("width", 320)
HEIGHT = snapshot_cfg.get("height", 180)

# 📝 Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# 📦 Laufende ffmpeg-Prozesse
running = {}


def get_active_streams():
    """Aktive Streams aus Redis lesen"""
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        data = r.get(REDIS_KEY)
        if not data:
            return []
        parsed = json.loads(data)
        return [s["name"] for s in parsed if s.get("source", {}).get("type")]
    except Exception as e:
        logging.error(f"❌ Fehler beim Lesen aus Redis: {e}")
        return []


def start_ffmpeg_process(stream_name):
    """ffmpeg-Prozess für Snapshot-Erzeugung starten"""
    output_path = os.path.join(OUTPUT_DIR, f"{stream_name}.jpg")
    stream_url = f"{PROTOCOL}://localhost:{PORT}/{stream_name}"
    fps_expr = f"fps=1/{INTERVAL},scale={WIDTH}:{HEIGHT}"

    cmd = [
        "ffmpeg", "-i", stream_url,
        "-vf", fps_expr,
        "-update", "1",
        "-y", output_path
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"▶️ ffmpeg gestartet für {stream_name} (alle {INTERVAL}s)")
        return proc
    except Exception as e:
        logging.error(f"❌ ffmpeg-Start fehlgeschlagen für {stream_name}: {e}")
        return None


def cleanup_snapshots(active_streams):
    """Snapshots von Streams löschen, die nicht mehr aktiv sind"""
    active_files = {f"{s}.jpg" for s in active_streams}
    for file_path in glob(os.path.join(OUTPUT_DIR, "*.jpg")):
        if os.path.basename(file_path) not in active_files:
            try:
                os.remove(file_path)
                logging.info(f"🗑️ Ungenutztes Snapshot gelöscht: {file_path}")
            except Exception as e:
                logging.warning(f"⚠️ Konnte Datei nicht löschen: {file_path}: {e}")


def main_loop():
    """Hauptschleife zur Verwaltung der Snapshot-Prozesse"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # 🔐 Schreibrechte testen
    testfile = os.path.join(OUTPUT_DIR, ".write_test")
    try:
        with open(testfile, "w") as f:
            f.write("test")
        os.remove(testfile)
    except Exception as e:
        logging.error(f"❌ Keine Schreibrechte im OUTPUT_DIR {OUTPUT_DIR}: {e}")
        exit(1)

    while True:
        active_streams = get_active_streams()

        # Prozesse starten
        for stream in active_streams:
            proc = running.get(stream)
            if proc is None or proc.poll() is not None:
                proc = start_ffmpeg_process(stream)
                if proc:
                    running[stream] = proc

        # Beendete Prozesse entfernen
        for stream in list(running):
            if stream not in active_streams or running[stream].poll() is not None:
                del running[stream]

        # Veraltete Snapshots löschen
        cleanup_snapshots(active_streams)

        time.sleep(2)


# ▶️ Startpunkt
if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logging.info("🛑 Beendet durch Benutzer.")
