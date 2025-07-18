from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import redis
import json

app = FastAPI()

# Redis-Verbindung
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Statische Dateien unter /static bereitstellen (optional)
app.mount("/static", StaticFiles(directory="/opt/mediamtx-monitoring-backend/static"), name="static")

# index.html direkt auf /
@app.get("/")
def index():
    return FileResponse("/opt/mediamtx-monitoring-backend/static/index.html")

# API-Endpunkt für Stream-Daten
@app.get("/api/streams")
def get_streams():
    raw = r.get("mediamtx:streams:latest")
    if raw:
        return JSONResponse(content=json.loads(raw))
    return JSONResponse(content=[], status_code=204)
