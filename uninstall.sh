#!/bin/bash
set -Eeuo pipefail

readonly INSTALL_DIR="/opt/mediamtx-monitoring-backend"
readonly MEDIAMTX_BIN="/usr/local/bin/mediamtx"
readonly MEDIAMTX_CONFIG="/usr/local/etc/mediamtx.yml"
readonly SERVICE_DIR="/etc/systemd/system"
readonly SERVICE_USER="mediamtxmon"
readonly SERVICE_GROUP="mediamtxmon"

SERVICES=(
  mediamtx.service
  mediamtx-api.service
  mediamtx-collector.service
  mediamtx-system.service
)

# Root-Rechte prüfen.
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  printf 'Fehler: Root-Rechte sind erforderlich. Aufruf: sudo ./uninstall.sh\n' >&2
  exit 1
fi

printf 'Deinstalliere MediaMTX Monitor.\n\n'

printf 'WARNUNG:\n'
printf 'Dieses Skript entfernt auch MediaMTX selbst sowie die komplette\n'
printf 'MediaMTX-Konfiguration unter:\n'
printf '  %s\n' "$MEDIAMTX_CONFIG"
printf 'Eine dort vorhandene individuelle oder manuell angepasste\n'
printf 'MediaMTX-Konfiguration wird dabei unwiderruflich gelöscht.\n\n'

# Dienste stoppen und deaktivieren.
for service in "${SERVICES[@]}"; do
  if systemctl list-unit-files "$service" --no-legend 2>/dev/null | grep -q .; then
    printf 'Stoppe und deaktiviere: %s\n' "$service"
    systemctl disable --now "$service" 2>/dev/null || true
  fi
done

# systemd-Unit-Dateien entfernen.
for service in "${SERVICES[@]}"; do
  if [ -e "$SERVICE_DIR/$service" ] || [ -L "$SERVICE_DIR/$service" ]; then
    printf 'Entferne Unit-Datei: %s\n' "$SERVICE_DIR/$service"
    rm -f -- "$SERVICE_DIR/$service"
  fi
done

# Eventuell verbliebene Enable-Symlinks entfernen.
for service in "${SERVICES[@]}"; do
  find "$SERVICE_DIR" \
    -type l \
    -name "$service" \
    -delete 2>/dev/null || true
done

# systemd aktualisieren.
systemctl daemon-reload
systemctl reset-failed

# MediaMTX-Binary entfernen.
if [ -e "$MEDIAMTX_BIN" ] || [ -L "$MEDIAMTX_BIN" ]; then
  printf 'Entferne MediaMTX: %s\n' "$MEDIAMTX_BIN"
  rm -f -- "$MEDIAMTX_BIN"
fi

# MediaMTX-Konfiguration entfernen.
if [ -e "$MEDIAMTX_CONFIG" ] || [ -L "$MEDIAMTX_CONFIG" ]; then
  printf 'Entferne MediaMTX-Konfiguration: %s\n' "$MEDIAMTX_CONFIG"
  rm -f -- "$MEDIAMTX_CONFIG"
fi

# Monitoring-Backend einschließlich Python-Venv entfernen.
if [ -d "$INSTALL_DIR" ]; then
  printf 'Entferne Monitoring-Installation: %s\n' "$INSTALL_DIR"
  rm -rf -- "$INSTALL_DIR"
fi

# Service-Benutzer entfernen.
if getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
  printf 'Entferne Benutzer: %s\n' "$SERVICE_USER"
  userdel "$SERVICE_USER"
fi

# Service-Gruppe entfernen.
if getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
  printf 'Entferne Gruppe: %s\n' "$SERVICE_GROUP"
  groupdel "$SERVICE_GROUP"
fi

printf '\nDeinstallation abgeschlossen.\n'
printf 'MediaMTX einschließlich der MediaMTX-Konfiguration wurde entfernt.\n'
printf 'Systempakete wie Redis, FFmpeg und Python wurden nicht entfernt.\n'
