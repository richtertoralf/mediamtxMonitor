"""
mediamtx_monitor_api.py

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
    Gibt die zuletzt gespeicherten Streamdaten aus Redis zurück.

    Returns:
        JSONResponse: JSON-Objekt mit den Streamdaten, oder leeres Array bei Fehler/nicht vorhandenem Key.
    """
    raw = r.get("mediamtx:streams:latest")
    if raw:
        return JSONResponse(content=json.loads(raw))
    return JSONResponse(content=[], status_code=204)
