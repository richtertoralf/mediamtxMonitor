"""
MediaMTX Monitor - read-only operating status (mediamtx-monitor --status).

Answers: does the monitor run, does it receive current data, and where can
the dashboard be reached? Whether the configuration is correct is the job of
config_check.py (mediamtx-monitor --check-config).

Does not:
- Write files or Redis, start or restart services, or change configuration.
- Ask external services; network URLs come from local interfaces only.
- Claim external reachability; network URLs are marked as possible.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import ipaddress
import re
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Callable, List, Optional

try:
    from .config_check import mask
    from .mediamtx_client import MediaMTXClient, MediaMTXError
    from .mediamtx_model import is_supported_version
    from .monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from .redis_keys import stream_snapshot_freshness_key
    from .redis_store import NamespacedRedis, RedisStore
except ImportError:
    from config_check import mask
    from mediamtx_client import MediaMTXClient, MediaMTXError
    from mediamtx_model import is_supported_version
    from monitoring_config import (
        DEFAULT_CONFIG_PATH,
        load_monitoring_config,
        resolve_monitoring_config,
    )
    from redis_keys import stream_snapshot_freshness_key
    from redis_store import NamespacedRedis, RedisStore


SERVICES = (
    "mediamtx-collector.service",
    "mediamtx-system.service",
    "mediamtx-api.service",
)
WILDCARD_HOSTS = {"", "0.0.0.0", "::", "[::]"}
VERSION_PATH = Path(__file__).absolute().parents[1] / "VERSION"
REVISION_PATH = Path(__file__).absolute().parents[1] / "REVISION"
PROBE_TIMEOUT_SECONDS = 2.0


def read_version(
    path: Path = VERSION_PATH, revision_path: Path = REVISION_PATH
) -> Optional[str]:
    """Return the installed version plus the short commit written by --upgrade."""
    try:
        version = path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None
    try:
        revision = revision_path.read_text(encoding="utf-8").strip()
    except OSError:
        revision = ""
    if version and re.fullmatch(r"[0-9a-f]{40}", revision):
        return f"{version} ({revision[:7]})"
    return version


def service_state(unit: str) -> str:
    """Return ``systemctl is-active`` for one unit; works without sudo."""
    if shutil.which("systemctl") is None:
        return "nicht prüfbar (systemctl fehlt)"
    try:
        result = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "nicht prüfbar"
    return result.stdout.strip() or "unbekannt"


def local_ipv4_addresses() -> List[str]:
    """Return the host's own IPv4 addresses as the dashboard header shows them."""
    try:
        import psutil
        try:
            from . import system_monitor
        except ImportError:
            import system_monitor
    except ImportError:
        return []
    system_monitor.psutil = psutil
    try:
        return system_monitor.get_server_ips()
    except Exception:
        return []


def http_reachable(url: str) -> bool:
    import requests

    try:
        return requests.get(url, timeout=PROBE_TIMEOUT_SECONDS).status_code == 200
    except requests.RequestException:
        return False


def mediamtx_version(api_base_url: str) -> Optional[str]:
    """Return the version from /v3/info; raises MediaMTXError if unreachable."""
    client = MediaMTXClient(api_base_url, timeout=PROBE_TIMEOUT_SECONDS)
    info = client.get_json("/v3/info")
    return info.get("version") if isinstance(info, dict) else None


def redis_client(host: str, port: int) -> Any:
    import redis

    return redis.Redis(
        host=host, port=port, decode_responses=True,
        socket_timeout=PROBE_TIMEOUT_SECONDS,
        socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
    )


@dataclass
class Probes:
    """Read-only probes; tests replace them with fakes."""

    service_state: Callable[[str], str] = service_state
    addresses: Callable[[], List[str]] = local_ipv4_addresses
    http_reachable: Callable[[str], bool] = http_reachable
    mediamtx_version: Callable[[str], Optional[str]] = mediamtx_version
    redis_client: Callable[[str, int], Any] = redis_client
    hostname: Callable[[], str] = socket.gethostname
    version: Callable[[], Optional[str]] = read_version
    now: Callable[[], float] = time.time


def _url(host: str, port: int) -> str:
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:{port}/"


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def dashboard_urls(host: str, port: int, addresses: List[str]) -> tuple[List[str], List[str]]:
    """Return local and possible network URLs; never a wildcard bind address."""
    host = str(host).strip()
    if host in WILDCARD_HOSTS:
        return [_url("127.0.0.1", port)], [_url(address, port) for address in addresses]
    if _is_loopback(host):
        return [_url(host, port)], []
    return [], [_url(host, port)]


def _age(timestamp: Any, now: float) -> Optional[float]:
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        return None
    return max(0.0, now - float(timestamp))


@dataclass
class Report:
    lines: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)


def build_status(path: Path, probes: Probes | None = None) -> Report:
    """Collect the operating status without changing anything."""
    probes = probes or Probes()
    report = Report()
    lines, hints = report.lines, report.hints

    try:
        config = resolve_monitoring_config(load_monitoring_config(path))
        config_note = ""
    except OSError as exc:
        config = resolve_monitoring_config({})
        config_note = " (nicht lesbar, angezeigt werden Defaults)"
        hints.append(
            f"Konfiguration nicht lesbar ({exc.strerror or exc}); alle Werte unten "
            "sind Defaults. Prüfen mit: mediamtx-monitor --check-config"
        )
    except (TypeError, ValueError) as exc:
        config = resolve_monitoring_config({})
        config_note = " (ungültig, angezeigt werden Defaults)"
        hints.append(
            f"Konfiguration ungültig: {exc}. Details: mediamtx-monitor --check-config"
        )

    version = probes.version()
    lines.append(f"MediaMTX Monitor {version or 'Version unbekannt'} auf {probes.hostname()}")
    lines.append(f"Konfiguration: {path}{config_note}")

    server = config["api_server"]
    local, network = dashboard_urls(
        server["listen_host"], server["listen_port"], probes.addresses()
    )
    lines.append("")
    lines.append("Dashboard")
    for url in local:
        reachable = probes.http_reachable(url)
        lines.append(f"  lokal:          {url}  ({'erreichbar' if reachable else 'nicht erreichbar'})")
        if not reachable:
            hints.append(f"Dashboard lokal nicht erreichbar: {url}")
    for url in network:
        lines.append(f"  mögliches Netz: {url}  (nicht geprüft; Firewall, NAT und Routing entscheiden)")
    if not local:
        lines.append("  lokal:          über die Netzadresse (listen_host ist keine Loopback-Adresse)")
    if not network and str(server["listen_host"]).strip() in WILDCARD_HOSTS:
        lines.append("  mögliches Netz: unbekannt (keine IPv4-Adresse ermittelt)")
    elif not network:
        lines.append("  mögliches Netz: keines (listen_host erlaubt nur lokalen Zugriff)")

    lines.append("")
    lines.append("Dienste")
    for unit in SERVICES:
        state = probes.service_state(unit)
        lines.append(f"  {unit:<28} {state}")
        if state != "active" and not state.startswith("nicht prüfbar"):
            hints.append(f"{unit} ist {state}. Log: journalctl -u {unit} -n 50")
        elif state.startswith("nicht prüfbar"):
            hints.append(f"Zustand von {unit} nicht prüfbar.")

    lines.append("")
    api_url = mask("api_base_url", config["api_base_url"])
    try:
        mtx_version = probes.mediamtx_version(config["api_base_url"])
        mtx_version = str(mtx_version).lstrip("v") if mtx_version else None
        shown = f"v{mtx_version}" if mtx_version else "Version unbekannt"
        lines.append(f"MediaMTX-API  {api_url}  erreichbar, {shown}")
        if mtx_version and not is_supported_version(mtx_version):
            hints.append(f"MediaMTX v{mtx_version} wird nicht unterstützt; erforderlich ist v1.21.0 oder neuer.")
    except MediaMTXError as exc:
        lines.append(f"MediaMTX-API  {api_url}  nicht erreichbar")
        hints.append(f"MediaMTX-API nicht erreichbar: {type(exc).__name__}")

    redis_cfg = config["redis"]
    redis_address = f"{redis_cfg['host']}:{redis_cfg['port']}"
    store = None
    try:
        raw = probes.redis_client(redis_cfg["host"], redis_cfg["port"])
        raw.ping()
        store = RedisStore(NamespacedRedis(raw, redis_cfg["namespace"], config["node"]["id"]))
        lines.append(f"Redis         {redis_address}  erreichbar")
    except Exception as exc:
        lines.append(f"Redis         {redis_address}  nicht erreichbar")
        hints.append(f"Redis nicht erreichbar ({type(exc).__name__}); Datenalter nicht prüfbar.")

    lines.append("")
    lines.append("Daten")
    now = probes.now()
    checks = (
        ("Streams", stream_snapshot_freshness_key(redis_cfg["key"]), None,
         max(10, 3 * config["collector"]["interval_seconds"]), "mediamtx-collector.service"),
        ("System", config["system_monitor"]["redis_key"], "timestamp",
         3 * config["system_monitor"]["interval_seconds"], "mediamtx-system.service"),
    )
    for label, key, field_name, limit, unit in checks:
        if store is None:
            lines.append(f"  {label + ':':<9} nicht prüfbar")
            continue
        try:
            value = store.read_snapshot(key)
        except Exception:
            value = None
        if isinstance(value, dict) and field_name:
            value = value.get(field_name)
        age = _age(value, now)
        if age is None:
            lines.append(f"  {label + ':':<9} unbekannt (noch keine Daten)")
            hints.append(f"Noch keine {label}-Daten in Redis; läuft {unit}?")
        elif age > limit:
            lines.append(f"  {label + ':':<9} vor {age:.1f} s (veraltet, Grenze {limit} s)")
            hints.append(f"{label}-Daten veraltet ({age:.0f} s); {unit} prüfen.")
        else:
            lines.append(f"  {label + ':':<9} vor {age:.1f} s (aktuell)")

    lines.append("")
    for hint in hints:
        lines.append(f"Hinweis: {hint}")
    lines.append("Ergebnis: OK" if not hints else f"Ergebnis: {len(hints)} Hinweis(e)")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Betriebsstatus des MediaMTX Monitor lesend anzeigen."
    )
    parser.add_argument("path", nargs="?", help="Konfigurationsdatei (Standard: Installationspfad)")
    args = parser.parse_args(argv)
    report = build_status(Path(args.path) if args.path else Path(DEFAULT_CONFIG_PATH))
    print("\n".join(report.lines))
    return 1 if report.hints else 0


if __name__ == "__main__":
    sys.exit(main())
