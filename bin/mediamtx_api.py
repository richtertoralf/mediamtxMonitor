#!/usr/bin/env python3
"""
mediamtx_api.py – API-Server zur Bereitstellung von MediaMTX-Monitoringdaten

Stellt eine einfache FastAPI-Schnittstelle zur Anzeige von Streamdaten und 
eine statische Weboberfläche bereit. 
Die Konfiguration erfolgt zentral über collector.yaml.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

import redis
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from .monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from .redis_store import RedisStore, SnapshotDecodeError
except ImportError:
    from monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from redis_store import RedisStore, SnapshotDecodeError

config = resolve_monitoring_config({})
redis_cfg = config["redis"]
REDIS_HOST = redis_cfg["host"]
REDIS_PORT = redis_cfg["port"]
REDIS_KEY = redis_cfg["key"]
SYSTEM_REDIS_KEY = config["system_monitor"]["redis_key"]
r = None
snapshot_store = None


def load_runtime_config(path: Path | str = DEFAULT_CONFIG_PATH) -> dict:
    try:
        return resolve_monitoring_config(load_monitoring_config(path))
    except Exception as exc:
        print(f"⚠️ Fehler beim Laden der Konfiguration: {exc}")
        return resolve_monitoring_config({})


def initialize_runtime(config_path: Path | str = DEFAULT_CONFIG_PATH) -> None:
    global config, redis_cfg, REDIS_HOST, REDIS_PORT, REDIS_KEY
    global SYSTEM_REDIS_KEY, r, snapshot_store

    config = load_runtime_config(config_path)
    redis_cfg = config["redis"]
    REDIS_HOST = redis_cfg["host"]
    REDIS_PORT = redis_cfg["port"]
    REDIS_KEY = redis_cfg["key"]
    SYSTEM_REDIS_KEY = config["system_monitor"]["redis_key"]

    log_cfg = config["logging"]
    log_level = getattr(logging, log_cfg["level"].upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()
        snapshot_store = RedisStore(r)
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
static_dir = Path(config["api_server"]["static_dir"])
index_file = config["api_server"]["index_file"]
app.mount(
    "/static",
    StaticFiles(directory=static_dir, check_dir=False),
    name="static",
)

@app.get("/")
def serve_index():
    """Liefert die HTML-Startseite (Frontend)."""
    return FileResponse(static_dir / index_file)

@app.get("/api/streams", response_class=JSONResponse, summary="Streamdaten abrufen")
def get_streams():
    """Liefert aktuelle Streamdaten aus Redis, inkl. UI-Refresh-Konfiguration und Systeminfos."""
    try:
        streams = snapshot_store.read_snapshot(REDIS_KEY)
        if streams is None:
            streams = []
    except SnapshotDecodeError:
        streams = []

    # Systeminfos aus Redis holen
    try:
        systeminfo = snapshot_store.read_snapshot(SYSTEM_REDIS_KEY)
        if systeminfo is None:
            systeminfo = {}
    except SnapshotDecodeError:
        systeminfo = {}

    frontend_cfg = config["frontend"]

    return JSONResponse(content={
        "streams": streams,
        "snapshot_refresh_ms": frontend_cfg["snapshot_refresh_ms"],
        "streamlist_refresh_ms": frontend_cfg["streamlist_refresh_ms"],
        "systeminfo": systeminfo
    })

def main() -> None:
    import uvicorn

    # Host und Port aus YAML holen (Fallback optional)
    server_cfg = load_runtime_config()["api_server"]
    host = server_cfg["listen_host"]
    port = server_cfg["listen_port"]

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
