#!/bin/bash
set -Eeuo pipefail

readonly INSTALL_DIR="/opt/mediamtx-monitoring-backend"
readonly MEDIAMTX_BIN="/usr/local/bin/mediamtx"
readonly MEDIAMTX_CONFIG="/usr/local/etc/mediamtx.yml"
readonly SERVICE_DIR="/etc/systemd/system"
readonly SERVICE_USER="mediamtxmon"
readonly SERVICE_GROUP="mediamtxmon"

fail() {
  printf 'Fehler: %s\n' "$*" >&2
  exit 1
}

warn() {
  printf 'WARNUNG: %s\n' "$*" >&2
}

usage() {
  printf 'Verwendung: sudo ./install.sh <MediaMTX-Version>\n' >&2
  printf 'Beispiel:   sudo ./install.sh 1.2.3\n' >&2
}

if [ "$#" -ne 1 ]; then
  usage
  exit 2
fi

VERSION_INPUT=$1
if [[ ! "$VERSION_INPUT" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf 'Fehler: Ungültige MediaMTX-Version: %s\n' "$VERSION_INPUT" >&2
  usage
  exit 2
fi
readonly MEDIAMTX_VERSION="${VERSION_INPUT#v}"
printf 'Gewählte MediaMTX-Version: v%s\n' "$MEDIAMTX_VERSION"
printf 'Die automatische Ergänzung der offiziellen MediaMTX-Konfiguration wurde mit MediaMTX v1.20.0 getestet.\n'

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  fail "Root-Rechte sind erforderlich. Aufruf: sudo ./install.sh"
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

# Betriebssysteminformationen einlesen.
# /etc/os-release ist üblicherweise ein Link auf /usr/lib/os-release.
if [ -r /etc/os-release ]; then
  OS_RELEASE_FILE="/etc/os-release"
elif [ -r /usr/lib/os-release ]; then
  OS_RELEASE_FILE="/usr/lib/os-release"
else
  fail "Keine lesbare os-release-Datei gefunden."
fi

# shellcheck disable=SC1090
source "$OS_RELEASE_FILE"

readonly OS_ID="${ID:-unknown}"
readonly OS_ID_LIKE="${ID_LIKE:-}"
readonly OS_NAME="${PRETTY_NAME:-unbekannt}"

[ "$(uname -s)" = "Linux" ] || \
  fail "Nicht unterstütztes Betriebssystem: $(uname -s). Unterstützt wird nur Linux."

# Debian meldet ID=debian.
# Ubuntu und andere Debian-Abkömmlinge melden normalerweise ID_LIKE=debian.
case " $OS_ID $OS_ID_LIKE " in
  *" debian "*)
    ;;
  *)
    fail "Nicht unterstütztes Betriebssystem: $OS_NAME. Erforderlich ist ein Debian-basiertes Linux."
    ;;
esac

# Der Installer benötigt apt, dpkg und systemd.
for required_command in apt-get dpkg systemctl; do
  command -v "$required_command" >/dev/null 2>&1 || \
    fail "Erforderliches Programm fehlt: $required_command"
done

# dpkg bestimmt die Architektur des installierten Userspace.
DEB_ARCH="$(dpkg --print-architecture 2>/dev/null)" || \
  fail "Die Debian-Architektur konnte nicht ermittelt werden."

# uname unterscheidet bei 32-Bit-ARM zwischen ARMv6 und ARMv7.
MACHINE_ARCH="$(uname -m)"

case "${DEB_ARCH}:${MACHINE_ARCH}" in
  amd64:x86_64|amd64:amd64)
    MEDIAMTX_ARCH="amd64"
    ;;

  arm64:aarch64|arm64:arm64)
    MEDIAMTX_ARCH="arm64"
    ;;

  # 32-Bit-ARMv6, beispielsweise ältere Raspberry-Pi-Systeme.
  armhf:armv6l|armhf:armv6)
    MEDIAMTX_ARCH="armv6"
    warn "Ein 32-Bit-ARMv6-System wurde erkannt."
    warn "Dieses System wurde nicht getestet. Die Installation wird nicht empfohlen, aber trotzdem fortgesetzt."
    ;;

  # 32-Bit-ARMv7-Userspace.
  armhf:armv7l|armhf:armv7|armhf:armv8l)
    MEDIAMTX_ARCH="armv7"
    warn "Ein 32-Bit-ARMv7-System wurde erkannt."
    warn "Dieses System wurde nicht getestet. Die Installation wird nicht empfohlen, aber trotzdem fortgesetzt."
    ;;

  # 32-Bit-Userspace auf einem 64-Bit-ARM-Kernel.
  armhf:aarch64|armhf:arm64)
    MEDIAMTX_ARCH="armv7"
    warn "Ein 32-Bit-ARM-Userspace auf einem 64-Bit-ARM-Kernel wurde erkannt."
    warn "Dieses System wurde nicht getestet. Die Installation wird nicht empfohlen, aber trotzdem fortgesetzt."
    ;;

  i386:*|i686:*)
    fail "Ein 32-Bit-x86-System wurde erkannt. Für diese Architektur steht kein vorgesehenes MediaMTX-Archiv zur Verfügung."
    ;;

  *)
    fail "Nicht unterstützte Architektur: dpkg=$DEB_ARCH, uname=$MACHINE_ARCH."
    ;;
esac

readonly DEB_ARCH
readonly MACHINE_ARCH
readonly MEDIAMTX_ARCH

printf 'Betriebssystem: %s\n' "$OS_NAME"
printf 'Architektur: dpkg=%s, uname=%s -> MediaMTX linux_%s\n' \
  "$DEB_ARCH" "$MACHINE_ARCH" "$MEDIAMTX_ARCH"

required_sources=(
  "$SCRIPT_DIR/requirements.txt"
  "$SCRIPT_DIR/config/collector.yaml"
  "$SCRIPT_DIR/config/monitor-preview-path.yml"
  "$SCRIPT_DIR/systemd/mediamtx.service"
  "$SCRIPT_DIR/systemd/mediamtx-api.service"
  "$SCRIPT_DIR/systemd/mediamtx-collector.service"
  "$SCRIPT_DIR/systemd/mediamtx-system.service"
  "$SCRIPT_DIR/static/index.html"
)
for source_file in "${required_sources[@]}"; do
  [ -f "$source_file" ] && [ -r "$source_file" ] || fail "Erforderliche Repository-Datei fehlt: $source_file"
done

for source_glob in "$SCRIPT_DIR"/bin/*.py "$SCRIPT_DIR"/static/css/*.css "$SCRIPT_DIR"/static/js/*.js; do
  [ -f "$source_glob" ] || fail "Erforderliche Repository-Datei fehlt: $source_glob"
done

existing_targets=(
  "$INSTALL_DIR"
  "$MEDIAMTX_BIN"
  "$MEDIAMTX_CONFIG"
  "$SERVICE_DIR/mediamtx.service"
  "$SERVICE_DIR/mediamtx-api.service"
  "$SERVICE_DIR/mediamtx-collector.service"
  "$SERVICE_DIR/mediamtx-system.service"
)
for target in "${existing_targets[@]}"; do
  [ ! -e "$target" ] || fail "Ziel existiert bereits; es wird nichts überschrieben: $target"
done

if command -v mediamtx >/dev/null 2>&1; then
  fail "Eine MediaMTX-Installation ist bereits im PATH vorhanden; es wird nichts verändert."
fi
if getent passwd "$SERVICE_USER" >/dev/null 2>&1 || getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
  fail "Benutzer oder Gruppe $SERVICE_USER existiert bereits; dieser Installer ist nur für frische Installationen."
fi

printf 'Installiere MediaMTX Monitor auf %s (%s/%s -> linux_%s).\n' \
  "$OS_NAME" "$DEB_ARCH" "$MACHINE_ARCH" "$MEDIAMTX_ARCH"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  coreutils \
  curl \
  ffmpeg \
  hostname \
  passwd \
  python3 \
  python3-venv \
  redis-server \
  tar \
  util-linux

TEMP_DIR=$(mktemp -d)
trap 'rm -rf -- "$TEMP_DIR"' EXIT

ARCHIVE="mediamtx_v${MEDIAMTX_VERSION}_linux_${MEDIAMTX_ARCH}.tar.gz"
RELEASE_BASE="https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}"

printf 'Lade MediaMTX v%s für linux_%s herunter.\n' "$MEDIAMTX_VERSION" "$MEDIAMTX_ARCH"
curl --fail --location --proto '=https' --tlsv1.2 \
  --output "$TEMP_DIR/$ARCHIVE" \
  "$RELEASE_BASE/$ARCHIVE" || \
  fail "Release v$MEDIAMTX_VERSION oder Architekturarchiv $ARCHIVE wurde nicht gefunden."
curl --fail --location --proto '=https' --tlsv1.2 \
  --output "$TEMP_DIR/checksums.sha256" \
  "$RELEASE_BASE/checksums.sha256" || \
  fail "Die offizielle Prüfsummendatei für Release v$MEDIAMTX_VERSION wurde nicht gefunden."

EXPECTED_CHECKSUM=$(awk -v archive="$ARCHIVE" '
  $2 == archive || $2 == "*" archive { print; found++ }
  END { if (found != 1) exit 1 }
' "$TEMP_DIR/checksums.sha256") || fail "Keine eindeutige offizielle SHA-256-Prüfsumme für $ARCHIVE gefunden."
(
  cd "$TEMP_DIR"
  printf '%s\n' "$EXPECTED_CHECKSUM" | sha256sum --check --status -
) || fail "SHA-256-Prüfung für $ARCHIVE fehlgeschlagen."
printf 'SHA-256-Prüfung erfolgreich.\n'

install -d -m 0755 "$TEMP_DIR/extract"
tar -xzf "$TEMP_DIR/$ARCHIVE" -C "$TEMP_DIR/extract" mediamtx mediamtx.yml || \
  fail "Das geprüfte Release-Archiv enthält nicht die erwarteten Dateien mediamtx und mediamtx.yml."
[ -x "$TEMP_DIR/extract/mediamtx" ] || fail "Das MediaMTX-Archiv enthält kein ausführbares Binary."
[ -f "$TEMP_DIR/extract/mediamtx.yml" ] && [ -r "$TEMP_DIR/extract/mediamtx.yml" ] || \
  fail "Das MediaMTX-Archiv enthält keine lesbare mediamtx.yml."

python3 - \
  "$TEMP_DIR/extract/mediamtx.yml" \
  "$SCRIPT_DIR/config/monitor-preview-path.yml" \
  "$TEMP_DIR/mediamtx.yml" <<'PY' || \
  fail "Die gewählte MediaMTX-Version konnte nicht sicher automatisch ergänzt werden."
from pathlib import Path
import re
import sys

source_path = Path(sys.argv[1])
preview_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])

text = source_path.read_text(encoding="utf-8")
preview = preview_path.read_text(encoding="utf-8").rstrip("\n")

if re.search(r"(?m)^paths\s*:", preview) or "all_others:" in preview:
    raise SystemExit("Der Preview-Ausschnitt darf weder paths: noch all_others: enthalten.")
if "__preview__" not in preview:
    raise SystemExit("Der Preview-Ausschnitt enthält keine __preview__-Regel.")

for key in ("api", "rtsp", "webrtc"):
    matches = list(re.finditer(rf"(?m)^{key}\s*:[^\n]*$", text))
    if len(matches) != 1:
        raise SystemExit(f"Erwartet wurde genau ein globaler Parameter {key}, gefunden: {len(matches)}")
    match = matches[0]
    line = match.group(0)
    comment = ""
    if "#" in line:
        comment = " " + line.split("#", 1)[1].strip()
        comment = " #" + comment.lstrip()
    text = text[:match.start()] + f"{key}: true{comment}" + text[match.end():]

paths_matches = list(re.finditer(r"(?m)^paths\s*:[^\n]*$", text))
all_others_matches = list(re.finditer(r"(?m)^  all_others\s*:[^\n]*$", text))
preview_matches = list(re.finditer(r"__preview__", text))
if len(paths_matches) != 1:
    raise SystemExit(f"Erwartet wurde genau ein Abschnitt paths:, gefunden: {len(paths_matches)}")
if len(all_others_matches) != 1:
    raise SystemExit(f"Erwartet wurde genau ein Eintrag all_others:, gefunden: {len(all_others_matches)}")
if preview_matches:
    raise SystemExit("Die offizielle Konfiguration enthält bereits eine __preview__-Regel.")

insert_at = all_others_matches[0].start()
text = text[:insert_at] + preview + "\n\n" + text[insert_at:]

for key in ("api", "rtsp", "webrtc"):
    if len(re.findall(rf"(?m)^{key}: true(?:\s*(?:#.*)?)?$", text)) != 1:
        raise SystemExit(f"Der ergänzte Parameter {key} ist nicht eindeutig true.")
if len(re.findall(r"(?m)^paths\s*:[^\n]*$", text)) != 1:
    raise SystemExit("Die ergänzte Konfiguration enthält nicht genau einen Abschnitt paths:.")
if len(re.findall(r"(?m)^  all_others\s*:[^\n]*$", text)) != 1:
    raise SystemExit("Die ergänzte Konfiguration enthält nicht genau einen Eintrag all_others:.")
if len(re.findall(r"__preview__", text)) != 1:
    raise SystemExit("Die ergänzte Konfiguration enthält nicht genau eine __preview__-Regel.")

output_path.write_text(text, encoding="utf-8")
PY

groupadd --system "$SERVICE_GROUP"
useradd \
  --system \
  --gid "$SERVICE_GROUP" \
  --no-create-home \
  --home-dir "$INSTALL_DIR" \
  --shell /usr/sbin/nologin \
  "$SERVICE_USER"

install -d -m 0755 /usr/local/bin /usr/local/etc
install -o root -g root -m 0755 "$TEMP_DIR/extract/mediamtx" "$MEDIAMTX_BIN"
install -o root -g root -m 0644 "$TEMP_DIR/mediamtx.yml" "$MEDIAMTX_CONFIG"

install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0755 "$INSTALL_DIR"
install -d -m 0755 \
  "$INSTALL_DIR/bin" \
  "$INSTALL_DIR/config" \
  "$INSTALL_DIR/static" \
  "$INSTALL_DIR/static/css" \
  "$INSTALL_DIR/static/js"
install -m 0644 "$SCRIPT_DIR"/bin/*.py "$INSTALL_DIR/bin/"
install -m 0644 "$SCRIPT_DIR/config/collector.yaml" "$INSTALL_DIR/config/collector.yaml"
install -m 0644 "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"
install -m 0644 "$SCRIPT_DIR/static/index.html" "$INSTALL_DIR/static/index.html"
install -m 0644 "$SCRIPT_DIR"/static/css/*.css "$INSTALL_DIR/static/css/"
install -m 0644 "$SCRIPT_DIR"/static/js/*.js "$INSTALL_DIR/static/js/"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"

runuser -u "$SERVICE_USER" -- env HOME="$INSTALL_DIR" python3 -m venv "$INSTALL_DIR/venv"
runuser -u "$SERVICE_USER" -- env HOME="$INSTALL_DIR" "$INSTALL_DIR/venv/bin/python" -m pip install \
  --disable-pip-version-check \
  -r "$INSTALL_DIR/requirements.txt"

for unit in mediamtx.service mediamtx-api.service mediamtx-collector.service mediamtx-system.service; do
  install -m 0644 "$SCRIPT_DIR/systemd/$unit" "$SERVICE_DIR/$unit"
done

systemctl daemon-reload
systemctl enable --now redis-server.service
systemctl enable --now mediamtx.service
systemctl enable --now \
  mediamtx-api.service \
  mediamtx-collector.service \
  mediamtx-system.service

services=(
  redis-server.service
  mediamtx.service
  mediamtx-api.service
  mediamtx-collector.service
  mediamtx-system.service
)
for service in "${services[@]}"; do
  if systemctl is-active --quiet "$service"; then
    printf 'Dienst aktiv: %s\n' "$service"
  else
    fail "Dienst ist nach der Installation nicht aktiv: $service"
  fi
done

MONITOR_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -n "$MONITOR_IP" ] || MONITOR_IP="127.0.0.1"

printf '\nInstallation abgeschlossen.\n'
printf 'Betriebssystem: %s\n' "$OS_NAME"
printf 'Architektur: dpkg=%s, uname=%s, MediaMTX=linux_%s\n' \
  "$DEB_ARCH" "$MACHINE_ARCH" "$MEDIAMTX_ARCH"
printf 'MediaMTX: v%s\n' "$MEDIAMTX_VERSION"
printf 'Monitor: http://%s:8080/\n' "$MONITOR_IP"
