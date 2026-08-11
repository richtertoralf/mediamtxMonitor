#!/usr/bin/env python3
"""
mediamtx_api.py – API-Server zur Bereitstellung von MediaMTX-Monitoringdaten

Stellt eine einfache FastAPI-Schnittstelle zur Anzeige von Streamdaten und 
eine statische Weboberfläche bereit. 
Die Konfiguration erfolgt zentral über collector.yaml.
"""

from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path

import redis
import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from .monitoring_config import resolve_system_monitor_config
except ImportError:
    from monitoring_config import resolve_system_monitor_config

CONFIG_PATH = "/opt/mediamtx-monitoring-backend/config/collector.yaml"
config = {}
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_KEY = "mediamtx:streams:latest"
SYSTEM_REDIS_KEY = resolve_system_monitor_config(config)["redis_key"]
r = None


def load_config(path: str = CONFIG_PATH) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as config_file:
            return yaml.safe_load(config_file) or {}
    except Exception as exc:
        print(f"⚠️ Fehler beim Laden der Konfiguration: {exc}")
        return {}


def initialize_runtime() -> None:
    global config, REDIS_HOST, REDIS_PORT, REDIS_KEY, SYSTEM_REDIS_KEY, r

    config = load_config()
    redis_cfg = config.get("redis", {}) or {}
    REDIS_HOST = redis_cfg.get("host", "localhost")
    REDIS_PORT = redis_cfg.get("port", 6379)
    REDIS_KEY = redis_cfg.get("key", "mediamtx:streams:latest")
    SYSTEM_REDIS_KEY = resolve_system_monitor_config(config)["redis_key"]

    log_cfg = config.get("logging", {})
    log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        logging.info("🔌 Verbindung zu Redis hergestellt.")
    except Exception as exc:
        logging.error(f"❌ Redis-Verbindung fehlgeschlagen: {exc}")
        raise


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_runtime()
    if not static_dir.is_dir():
        raise RuntimeError(f"Directory '{static_dir}' does not exist")
    yield

# 🌐 FastAPI-Instanz erstellen
app = FastAPI(
    title="MediaMTX Monitoring API",
    version="1.0",
    lifespan=lifespan,
)

# 📁 Statische Dateien einbinden (Frontend)
static_dir = Path("/opt/mediamtx-monitoring-backend/static")
app.mount(
    "/static",
    StaticFiles(directory=static_dir, check_dir=False),
    name="static",
)

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
    system_raw = r.get(SYSTEM_REDIS_KEY)
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

def main() -> None:
    import uvicorn

    # Host und Port aus YAML holen (Fallback optional)
    server_cfg = load_config().get("api_server", {})
    host = server_cfg.get("listen_host", "127.0.0.1")
    port = server_cfg.get("listen_port", 8080)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
