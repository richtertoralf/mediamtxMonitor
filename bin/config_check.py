"""
MediaMTX Monitor - read-only configuration check.

Reports the configuration file, the effective values with their origin, and
the services that read them. Unknown keys are named as warnings; duplicate
keys, wrong section types and invalid values are errors.

Does not:
- Write files or Redis, start or restart services, or contact MediaMTX.
- Change the runtime fallbacks of the services.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import yaml

try:
    from .monitoring_config import (
        API_DEFAULTS,
        BITRATE_DEFAULTS,
        COLLECTOR_DEFAULTS,
        DEFAULT_CONFIG_PATH,
        FRONTEND_DEFAULTS,
        LOGGING_DEFAULTS,
        MONITORING_DEFAULTS,
        NODE_DEFAULTS,
        REDIS_DEFAULTS,
        SYSTEM_MONITOR_DEFAULTS,
        normalize_preview_base_url,
        resolve_api_config,
        resolve_bitrate_config,
        resolve_collector_config,
        resolve_frontend_config,
        resolve_logging_config,
        resolve_node_config,
        resolve_redis_config,
        resolve_system_monitor_config,
    )
except ImportError:
    from monitoring_config import (
        API_DEFAULTS,
        BITRATE_DEFAULTS,
        COLLECTOR_DEFAULTS,
        DEFAULT_CONFIG_PATH,
        FRONTEND_DEFAULTS,
        LOGGING_DEFAULTS,
        MONITORING_DEFAULTS,
        NODE_DEFAULTS,
        REDIS_DEFAULTS,
        SYSTEM_MONITOR_DEFAULTS,
        normalize_preview_base_url,
        resolve_api_config,
        resolve_bitrate_config,
        resolve_collector_config,
        resolve_frontend_config,
        resolve_logging_config,
        resolve_node_config,
        resolve_redis_config,
        resolve_system_monitor_config,
    )


UNITS = {
    "collector": "mediamtx-collector.service",
    "system": "mediamtx-system.service",
    "api": "mediamtx-api.service",
}

TOP_LEVEL_VALUES: Dict[str, Tuple[Any, Tuple[str, ...]]] = {
    "api_base_url": (MONITORING_DEFAULTS["api_base_url"], ("collector", "api")),
    "webrtc_base_url": ("", ("api",)),
}

SECTIONS: Dict[str, Tuple[Mapping[str, Any], Callable[..., Any], Tuple[str, ...]]] = {
    "redis": (REDIS_DEFAULTS, resolve_redis_config, ("collector", "system", "api")),
    "node": (NODE_DEFAULTS, resolve_node_config, ("collector", "system", "api")),
    "collector": (COLLECTOR_DEFAULTS, resolve_collector_config, ("collector",)),
    "bitrate": (BITRATE_DEFAULTS, resolve_bitrate_config, ("collector",)),
    # The API reads system_monitor.redis_key to serve the system snapshot.
    "system_monitor": (
        SYSTEM_MONITOR_DEFAULTS, resolve_system_monitor_config, ("system", "api"),
    ),
    "api_server": (API_DEFAULTS, resolve_api_config, ("api",)),
    "logging": (LOGGING_DEFAULTS, resolve_logging_config, ("api",)),
    "frontend": (FRONTEND_DEFAULTS, resolve_frontend_config, ("api",)),
}

NULLABLE = {("bitrate", "smooth_alpha")}
PORTS = {("redis", "port"), ("api_server", "listen_port")}
LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
SENSITIVE_MARKERS = ("pass", "token", "secret", "credential")


class _DuplicateKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that records keys defined twice in one mapping."""

    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        self.duplicates: List[str] = []

    def construct_mapping(self, node: Any, deep: bool = False) -> Any:
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                self.duplicates.append(
                    f"Doppelter Schlüssel {key!r} in Zeile {key_node.start_mark.line + 1}; "
                    "YAML verwendet stillschweigend den letzten Wert."
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def mask(key: str, value: Any) -> Any:
    """Hide credential-like values and userinfo in URLs."""
    if any(marker in key.lower() for marker in SENSITIVE_MARKERS):
        return "***"
    if isinstance(value, str) and "@" in value and "://" in value:
        parts = urlsplit(value)
        if parts.username or parts.password:
            host = parts.hostname or ""
            netloc = f"***@{host}" + (f":{parts.port}" if parts.port else "")
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return value


def _kind_error(section: str, key: str, value: Any, default: Any) -> Optional[str]:
    name = f"{section}.{key}"
    if value is None and (section, key) in NULLABLE:
        return None
    if isinstance(default, bool):
        ok = isinstance(value, bool)
        expected = "true oder false"
    elif isinstance(default, int):
        ok = isinstance(value, int) and not isinstance(value, bool)
        expected = "eine ganze Zahl"
    elif isinstance(default, float):
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        expected = "eine Zahl"
    elif isinstance(default, list):
        ok = isinstance(value, list) and all(isinstance(item, str) for item in value)
        expected = "eine Liste von Zeichenketten"
    else:
        ok = isinstance(value, str)
        expected = "eine Zeichenkette"
    if not ok:
        return f"{name} muss {expected} sein, gefunden: {json.dumps(value, ensure_ascii=False)}."
    if (section, key) in PORTS and not 1 <= value <= 65535:
        return f"{name} muss ein Port zwischen 1 und 65535 sein."
    if key.endswith(("_seconds", "_ms")) or key == "ttl":
        if value <= 0:
            return f"{name} muss größer als 0 sein."
    if (section, key) == ("bitrate", "smooth_alpha") and not 0 < value <= 1:
        return f"{name} muss größer als 0 und höchstens 1 sein."
    if (section, key) == ("bitrate", "min_dt") and value < 0:
        return f"{name} darf nicht negativ sein."
    if (section, key) == ("logging", "level") and value.upper() not in LOG_LEVELS:
        return f"{name} muss einer von {', '.join(sorted(LOG_LEVELS))} sein."
    return None


def check_config(path: Path, explicit: bool) -> Tuple[List[str], int]:
    """Return report lines and the exit code (0 without errors, else 1)."""
    origin = "ausdrücklich angegeben" if explicit else "Standardpfad"
    lines = [f"Konfigurationsdatei: {path} ({origin})"]
    errors: List[str] = []
    warnings: List[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        lines.append(f"Fehler: Datei fehlt oder ist nicht lesbar: {exc.strerror or exc}")
        lines.append(
            "Ohne lesbare Datei starten mediamtx-collector und mediamtx-system nicht; "
            "mediamtx-api verwendet nach einer Warnung alle Defaults."
        )
        lines.append("Ergebnis: 1 Fehler")
        return lines, 1

    loader = _DuplicateKeyLoader(text)
    try:
        raw = loader.get_single_data() or {}
    except yaml.YAMLError as exc:
        lines.append(f"Fehler: Kein gültiges YAML: {exc}")
        lines.append("Ergebnis: 1 Fehler")
        return lines, 1
    finally:
        loader.dispose()
    errors.extend(loader.duplicates)
    if not isinstance(raw, Mapping):
        lines.append("Fehler: Die Konfiguration muss ein YAML-Mapping sein.")
        lines.append("Ergebnis: 1 Fehler")
        return lines, 1

    for key in raw:
        if key not in TOP_LEVEL_VALUES and key not in SECTIONS:
            warnings.append(f"Unbekannter Schlüssel {key!r} wird ignoriert.")

    lines.append("")
    for key, (default, services) in TOP_LEVEL_VALUES.items():
        present = key in raw
        value = raw.get(key, default)
        if present and not isinstance(value, str):
            errors.append(f"{key} muss eine Zeichenkette sein.")
        elif key == "webrtc_base_url":
            try:
                value = normalize_preview_base_url(value)
            except ValueError as exc:
                errors.append(str(exc))
        shown = json.dumps(mask(key, value), ensure_ascii=False)
        source = "Datei" if present else "Default"
        lines.append(f"{key} = {shown}  ({source}; {_units(services)})")

    for section, (defaults, resolver, services) in SECTIONS.items():
        block = raw.get(section)
        lines.append("")
        lines.append(f"[{section}] – gelesen von {_units(services)}")
        if section in raw and block is not None and not isinstance(block, Mapping):
            consequence = (
                "die Dienste starten damit nicht" if section == "node"
                else "die Dienste verwenden stattdessen stillschweigend alle Defaults"
            )
            errors.append(f"Abschnitt {section} muss ein Mapping sein; {consequence}.")
            block = {}
        block = block or {}
        for key in block:
            if key not in defaults:
                warnings.append(f"Unbekannter Schlüssel {section}.{key} wird ignoriert.")
        section_errors = [
            message
            for key, value in block.items()
            if key in defaults
            for message in [_kind_error(section, key, value, defaults[key])]
            if message
        ]
        errors.extend(section_errors)
        try:
            effective = resolver({section: block}) if not section_errors else None
        except (TypeError, ValueError) as exc:
            errors.append(f"{section}: {exc}")
            effective = None
        for key in defaults:
            source = "Datei" if key in block else "Default"
            value = effective.get(key) if effective is not None else block.get(key, defaults[key])
            shown = json.dumps(mask(key, value), ensure_ascii=False)
            lines.append(f"  {key} = {shown}  ({source})")

    lines.append("")
    for warning in warnings:
        lines.append(f"Warnung: {warning}")
    for error in errors:
        lines.append(f"Fehler: {error}")
    lines.append(f"Ergebnis: {len(errors)} Fehler, {len(warnings)} Warnungen")
    return lines, 1 if errors else 0


def _units(services: Tuple[str, ...]) -> str:
    return ", ".join(UNITS[service] for service in services)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="MediaMTX-Monitor-Konfiguration lesend prüfen."
    )
    parser.add_argument("path", nargs="?", help="Konfigurationsdatei (Standard: Installationspfad)")
    parser.add_argument(
        "--standard", action="store_true",
        help="PATH ist der Standardpfad der Installation, nicht ausdrücklich gewählt",
    )
    args = parser.parse_args(argv)
    path = Path(args.path) if args.path else Path(DEFAULT_CONFIG_PATH)
    lines, code = check_config(path, explicit=bool(args.path) and not args.standard)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
