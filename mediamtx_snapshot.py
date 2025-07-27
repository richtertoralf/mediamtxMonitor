#!/usr/bin/env python3
"""
📸 Snapshot-Manager (FFmpeg-Version, YAML-gesteuert)

Startet pro aktivem Stream genau einen ffmpeg-Prozess zur Snapshot-Erzeugung.
Verwendet eine zentrale YAML-Konfiguration (collector.yaml) wie die anderen Module.

Autor: snowgames.live
Lizenz: MIT
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

# 🧾 Konfigurationspfad
CONFIG_PATH = "/opt/mediamtx-monitoring-backend/config/collector.yaml"

# 📦 Laufende Prozesse
running = {}

# 🛠️ Konfiguration laden
def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"❌ Fehler beim Laden der YAML-Konfiguration: {e}")
        exit(1)

# 🔌 Aktive Streams aus Redis holen
def get_active_streams(redis_host, redis_port, redis_key):
    try:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        data = r.get(redis_key)
        if not data:
            return []
        parsed = json.loads(data)
        return [s["name"] for s in parsed if s.get("source", {}).get("type")]
    except Exception as e:
        logging.error(f"❌ Fehler beim Lesen aus Redis: {e}")
        return []

# ▶️ ffmpeg-Prozess starten
def start_ffmpeg_process(stream_name, snapshot_cfg):
    output_path = os.path.join(snapshot_cfg["output_dir"], f"{stream_name}.jpg")
    stream_url = f"{snapshot_cfg['protocol']}://localhost:{snapshot_cfg['port']}/{stream_name}"

    interval = int(snapshot_cfg.get("interval", 10))  # Default: 10 Sekunden
    fps_expr = f"fps=1/{interval},scale={snapshot_cfg['width']}:{snapshot_cfg['height']}"

    cmd = [
        "ffmpeg",
        "-i", stream_url,
        "-vf", fps_expr,
        "-update", "1",
        "-y", output_path
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"▶️ ffmpeg gestartet für {stream_name} (alle {interval}s)")
        return proc
    except Exception as e:
        logging.error(f"❌ ffmpeg-Start fehlgeschlagen für {stream_name}: {e}")
        return None

# 🧹 Veraltete Snapshots löschen
def cleanup_snapshots(active_streams, snapshot_cfg):
    active_files = {f"{s}.jpg" for s in active_streams}
    for file_path in glob(os.path.join(snapshot_cfg["output_dir"], "*.jpg")):
        if os.path.basename(file_path) not in active_files:
            try:
                os.remove(file_path)
                logging.info(f"🗑️ Ungenutztes Snapshot gelöscht: {file_path}")
            except Exception as e:
                logging.warning(f"⚠️ Konnte Datei nicht löschen: {file_path}: {e}")

# 🔁 Hauptschleife
def main_loop(config):
    snapshot_cfg = config.get("snapshots", {})
    redis_cfg = config.get("redis", {})

    os.makedirs(snapshot_cfg["output_dir"], exist_ok=True)

    while True:
        active_streams = get_active_streams(
            redis_host=redis_cfg.get("host", "localhost"),
            redis_port=redis_cfg.get("port", 6379),
            redis_key=redis_cfg.get("key", "mediamtx:streams:latest")
        )

        # Prozesse starten
        for stream in active_streams:
            proc = running.get(stream)
            if proc is None or proc.poll() is not None:
                proc = start_ffmpeg_process(stream, snapshot_cfg)
                if proc:
                    running[stream] = proc

        # Beendete Prozesse entfernen
        for stream in list(running):
            if stream not in active_streams or running[stream].poll() is not None:
                del running[stream]

        # Alte Snapshots aufräumen
        cleanup_snapshots(active_streams, snapshot_cfg)

        time.sleep(2)

# 🧠 Logging und Start
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    try:
        config = load_config()
        main_loop(config)
    except KeyboardInterrupt:
        logging.info("🛑 Beendet durch Benutzer.")
