#!/usr/bin/env python3
"""
MediaMTX Monitor - read-only monitoring API.

Serves current stream and host-system snapshots, snapshot freshness, frontend
refresh settings, and the static dashboard.

Does not poll the MediaMTX Control API, calculate stream metrics, or produce
monitoring snapshots.
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
    from .redis_store import NamespacedRedis, RedisStore, SnapshotDecodeError
    from .redis_keys import stream_snapshot_freshness_key
except ImportError:
    from monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from redis_store import NamespacedRedis, RedisStore, SnapshotDecodeError
    from redis_keys import stream_snapshot_freshness_key

config = resolve_monitoring_config({})
redis_cfg = config["redis"]
REDIS_HOST = redis_cfg["host"]
REDIS_PORT = redis_cfg["port"]
REDIS_KEY = redis_cfg["key"]
SYSTEM_REDIS_KEY = config["system_monitor"]["redis_key"]
VERSION_PATH = Path(__file__).resolve().parents[1] / "VERSION"
monitor_version = None
r = None
snapshot_store = None


def load_runtime_config(path: Path | str = DEFAULT_CONFIG_PATH) -> dict:
    """Load normalized settings, defaulting only when the file is unavailable."""
    try:
        return resolve_monitoring_config(load_monitoring_config(path))
    except OSError as exc:
        print(f"⚠️ Fehler beim Laden der Konfiguration: {exc}")
        return resolve_monitoring_config({})


def load_monitor_version(path: Path = VERSION_PATH) -> str | None:
    """Return the version file content without surrounding whitespace."""
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def initialize_runtime(config_path: Path | str = DEFAULT_CONFIG_PATH) -> None:
    """Configure logging and initialize the API snapshot store."""
    global config, redis_cfg, REDIS_HOST, REDIS_PORT, REDIS_KEY
    global SYSTEM_REDIS_KEY, monitor_version, r, snapshot_store

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
    monitor_version = load_monitor_version()
    if monitor_version is None:
        logging.warning("Monitor version file could not be read: %s", VERSION_PATH)

    try:
        raw_redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
        )
        r = NamespacedRedis(raw_redis, redis_cfg["namespace"], config["node"]["id"])
        r.ping()
        snapshot_store = RedisStore(r)
        logging.info("🔌 Verbindung zu Redis hergestellt.")
    except Exception as exc:
        logging.error(f"❌ Redis-Verbindung fehlgeschlagen: {exc}")
        raise


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize runtime dependencies and validate the static directory."""
    initialize_runtime()
    if not static_dir.is_dir():
        raise RuntimeError(f"Directory '{static_dir}' does not exist")
    yield

app = FastAPI(
    title="MediaMTX Monitoring API",
    version="1.0",
    lifespan=lifespan,
)

static_dir = Path(config["api_server"]["static_dir"])
index_file = config["api_server"]["index_file"]
app.mount(
    "/static",
    StaticFiles(directory=static_dir, check_dir=False),
    name="static",
)

@app.get("/")
def serve_index():
    """Return the static dashboard entry page."""
    return FileResponse(static_dir / index_file)

@app.get("/api/streams", response_class=JSONResponse, summary="Streamdaten abrufen")
def get_streams():
    """Return current snapshots, freshness, and frontend refresh settings."""
    try:
        streams = snapshot_store.read_snapshot(REDIS_KEY)
        if streams is None:
            streams = []
    except SnapshotDecodeError:
        streams = []

    try:
        collected_at = snapshot_store.read_snapshot(
            stream_snapshot_freshness_key(REDIS_KEY)
        )
    except SnapshotDecodeError:
        collected_at = None

    try:
        systeminfo = snapshot_store.read_snapshot(SYSTEM_REDIS_KEY)
        if systeminfo is None:
            systeminfo = {}
    except SnapshotDecodeError:
        systeminfo = {}

    frontend_cfg = config["frontend"]

    return JSONResponse(content={
        "streams": streams,
        "collected_at": collected_at,
        "snapshot_refresh_ms": frontend_cfg["snapshot_refresh_ms"],
        "streamlist_refresh_ms": frontend_cfg["streamlist_refresh_ms"],
        "monitor_version": monitor_version,
        "systeminfo": systeminfo
    })

def main() -> None:
    """Run the configured monitoring API server."""
    import uvicorn

    server_cfg = load_runtime_config()["api_server"]
    host = server_cfg["listen_host"]
    port = server_cfg["listen_port"]

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
