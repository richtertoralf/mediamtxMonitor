"""
mediamtx_api.py

Dieses Modul stellt eine einfache API und statische Weboberfläche zur Anzeige von Stream-Informationen aus MediaMTX bereit.
Verwendet werden FastAPI und Redis.

Endpoints:
- GET /                 → index.html ausliefern (statische Weboberfläche)
- GET /api/streams      → aktuelle Streamdaten aus Redis als JSON zurückgeben

Abhängigkeiten:
- FastAPI
- Redis (Python-Client)
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import redis
import json
import yaml
from pathlib import Path

# YAML-Konfiguration laden (muss vor Verwendung passieren!)
CONFIG_PATH = "/opt/mediamtx-monitoring-backend/config/collector.yaml"
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"⚠️ Fehler beim Laden der collector.yaml: {e}")
    config = {}

# FastAPI-Instanz
app = FastAPI(title="MediaMTX Monitoring API", version="1.0")


# Redis-Verbindung auf localhost (Standardport)
# Die Antwortdaten werden als UTF-8-Strings dekodiert (decode_responses=True)
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Statische Dateien unter /static verfügbar machen (HTML, JS, CSS)
app.mount("/static", StaticFiles(directory="/opt/mediamtx-monitoring-backend/static"), name="static")


@app.get("/")
def index():
    """
    Liefert die index.html als Startseite aus.

    Returns:
        FileResponse: Die statische HTML-Datei zur Visualisierung der Streams.
    """
    return FileResponse("/opt/mediamtx-monitoring-backend/static/index.html")

# API-Endpunkt für Stream-Daten
@app.get("/api/streams", response_class=JSONResponse, summary="Streamdaten abrufen")
def get_streams():
    """
    Gibt die zuletzt gespeicherten Streamdaten aus Redis zurück,
    ergänzt um Snapshot- und UI-Aktualisierungszeiten aus collector.yaml.
    """
    raw = r.get("mediamtx:streams:latest")
    try:
        streams = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        streams = []

    frontend_cfg = config.get("frontend", {})
    return JSONResponse(content={
        "streams": streams,
        "snapshot_refresh_ms": frontend_cfg.get("snapshot_refresh_ms", 5000),
        "streamlist_refresh_ms": frontend_cfg.get("streamlist_refresh_ms", 5000)
    })
