#!/bin/bash
set -Eeuo pipefail

readonly INSTALL_DIR="/opt/mediamtx-monitoring-backend"
readonly MONITOR_CLI="/usr/local/bin/mediamtx-monitor"
readonly SERVICE_DIR="/etc/systemd/system"
readonly SERVICE_USER="mediamtxmon"
readonly SERVICE_GROUP="mediamtxmon"
readonly LEGACY_PROGRAM_FILE="$INSTALL_DIR/bin/mediamtx_systeminfo.py"

SERVICES=(
  mediamtx-api.service
  mediamtx-collector.service
  mediamtx-system.service
  mediamtx-systeminfo.service
)

# Root-Rechte prüfen.
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  printf 'Fehler: Root-Rechte sind erforderlich. Aufruf: sudo ./uninstall.sh\n' >&2
  exit 1
fi

printf 'Deinstalliere MediaMTX Monitor.\n\n'

printf 'Shared Infrastructure bleibt erhalten:\n'
printf '  MediaMTX-Unit, Binary und Konfiguration werden nicht entfernt.\n\n'

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

# Bekannte Legacy-Datei alter Monitor-Installationen gezielt entfernen.
if [ -e "$LEGACY_PROGRAM_FILE" ] || [ -L "$LEGACY_PROGRAM_FILE" ]; then
  printf 'Entferne Legacy-Programmdatei: %s\n' "$LEGACY_PROGRAM_FILE"
  rm -f -- "$LEGACY_PROGRAM_FILE"
fi

# Monitor-Kommando entfernen.
if [ -e "$MONITOR_CLI" ] || [ -L "$MONITOR_CLI" ]; then
  printf 'Entferne Monitor-Kommando: %s\n' "$MONITOR_CLI"
  rm -f -- "$MONITOR_CLI"
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
printf 'MediaMTX einschließlich Unit, Binary und Konfiguration blieb erhalten.\n'
printf 'Systempakete wie Redis, FFmpeg und Python wurden nicht entfernt.\n'
