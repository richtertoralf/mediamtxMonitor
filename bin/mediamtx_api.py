#!/usr/bin/env python3
"""
mediamtx_api.py – API-Server zur Bereitstellung von MediaMTX-Monitoringdaten

Stellt eine einfache FastAPI-Schnittstelle zur Anzeige von Streamdaten und 
eine statische Weboberfläche bereit. 
Die Konfiguration erfolgt zentral über collector.yaml.
"""

import redis
import json
import yaml
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# 📄 Konfiguration laden
CONFIG_PATH = "/opt/mediamtx-monitoring-backend/config/collector.yaml"
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"⚠️ Fehler beim Laden der Konfiguration: {e}")
    config = {}

# 🧠 Redis-Konfiguration lesen
redis_cfg = config.get("redis", {})
REDIS_HOST = redis_cfg.get("host", "localhost")
REDIS_PORT = redis_cfg.get("port", 6379)
REDIS_KEY = redis_cfg.get("key", "mediamtx:streams:latest")

# 📝 Logging einrichten
log_cfg = config.get("logging", {})
log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

# 🔌 Redis-Verbindung herstellen
try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.ping()
    logging.info("🔌 Verbindung zu Redis hergestellt.")
except Exception as e:
    logging.error(f"❌ Redis-Verbindung fehlgeschlagen: {e}")
    raise

# 🌐 FastAPI-Instanz erstellen
app = FastAPI(title="MediaMTX Monitoring API", version="1.0")

# 📁 Statische Dateien einbinden (Frontend)
static_dir = Path("/opt/mediamtx-monitoring-backend/static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_index():
    """Liefert die HTML-Startseite (Frontend)."""
    return FileResponse(static_dir / "index.html")

@app.get("/api/streams", response_class=JSONResponse, summary="Streamdaten abrufen")
def get_streams():
    """Liefert aktuelle Streamdaten aus Redis, inkl. UI-Refresh-Konfiguration und Systeminfos."""
    raw = r.get(REDIS_KEY)
    try:
        streams = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        streams = []

    # Systeminfos aus Redis holen
    system_raw = r.get("mediamtx:system:latest")
    try:
        systeminfo = json.loads(system_raw) if system_raw else {}
    except json.JSONDecodeError:
        systeminfo = {}

    frontend_cfg = config.get("frontend", {})

    return JSONResponse(content={
        "streams": streams,
        "snapshot_refresh_ms": frontend_cfg.get("snapshot_refresh_ms", 2000),
        "streamlist_refresh_ms": frontend_cfg.get("streamlist_refresh_ms", 5000),
        "systeminfo": systeminfo
    })
