#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TARGET="/opt/mediamtx-monitoring-backend"

SERVICE_API="mediamtx-api"
SERVICE_COLLECTOR="mediamtx-collector"
SERVICE_SYSTEM="mediamtx-system"

DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
elif [[ $# -gt 0 ]]; then
    echo "Verwendung:"
    echo "  $0"
    echo "  $0 --dry-run"
    exit 2
fi


# ------------------------------------------------------------
# Voraussetzungen
# ------------------------------------------------------------

if [[ ! -d "${TARGET}" ]]; then
    echo "Fehler: Entwicklungsinstallation nicht gefunden:"
    echo "  ${TARGET}"
    echo
    echo "Zuerst install.sh ausführen."
    exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
    echo "Fehler: rsync ist nicht installiert."
    echo "Einmalig installieren mit:"
    echo "  sudo apt install rsync"
    exit 1
fi

for path in \
    "${REPO_DIR}/bin" \
    "${REPO_DIR}/static" \
    "${REPO_DIR}/config/collector.yaml" \
    "${REPO_DIR}/VERSION"
do
    [[ -e "${path}" ]] || {
        echo "Fehler: Repository-Datei fehlt:"
        echo "  ${path}"
        exit 1
    }
done


# ------------------------------------------------------------
# Vergleich
# ------------------------------------------------------------

compare_dir() {
    local source="$1"
    local destination="$2"

    rsync \
        -rlcni \
        --delete \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        "${source}/" \
        "${destination}/"
}

compare_file() {
    local source="$1"
    local destination="$2"

    if [[ ! -f "${destination}" ]]; then
        echo ">f+++++++++ $(basename "${source}")"
    elif ! cmp -s "${source}" "${destination}"; then
        echo ">fc........ $(basename "${source}")"
    fi
}


BIN_CHANGES="$(
    compare_dir \
        "${REPO_DIR}/bin" \
        "${TARGET}/bin"
)"

STATIC_CHANGES="$(
    compare_dir \
        "${REPO_DIR}/static" \
        "${TARGET}/static"
)"

CONFIG_CHANGES="$(
    compare_file \
        "${REPO_DIR}/config/collector.yaml" \
        "${TARGET}/config/collector.yaml"
)"

VERSION_CHANGES="$(
    compare_file \
        "${REPO_DIR}/VERSION" \
        "${TARGET}/VERSION"
)"


if [[ -z "${BIN_CHANGES}" &&
      -z "${STATIC_CHANGES}" &&
      -z "${CONFIG_CHANGES}" &&
      -z "${VERSION_CHANGES}" ]]; then

    echo "Keine deploybaren Änderungen gefunden."
    exit 0
fi

echo
echo "Änderungen für Dev-Deployment:"
echo

if [[ -n "${BIN_CHANGES}" ]]; then
    echo "--- bin/"
    printf '%s\n' "${BIN_CHANGES}"
    echo
fi

if [[ -n "${CONFIG_CHANGES}" ]]; then
    echo "--- config/collector.yaml"
    printf '%s\n' "${CONFIG_CHANGES}"
    echo
fi

if [[ -n "${VERSION_CHANGES}" ]]; then
    echo "--- VERSION"
    printf '%s\n' "${VERSION_CHANGES}"
    echo
fi

if [[ -n "${STATIC_CHANGES}" ]]; then
    echo "--- static/"
    printf '%s\n' "${STATIC_CHANGES}"
    echo
fi


if (( DRY_RUN )); then
    echo "Dry-Run: Es wurden keine Dateien verändert."
    exit 0
fi


# ------------------------------------------------------------
# Deployment
# ------------------------------------------------------------

echo "Übertrage Repository-Stand nach ${TARGET} ..."

sudo rsync \
    -rlc \
    --delete \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --chown=mediamtxmon:mediamtxmon \
    "${REPO_DIR}/bin/" \
    "${TARGET}/bin/"

sudo rsync \
    -rlc \
    --delete \
    --chown=mediamtxmon:mediamtxmon \
    "${REPO_DIR}/static/" \
    "${TARGET}/static/"

if [[ -n "${CONFIG_CHANGES}" ]]; then
    sudo install \
        -o mediamtxmon \
        -g mediamtxmon \
        -m 0644 \
        "${REPO_DIR}/config/collector.yaml" \
        "${TARGET}/config/collector.yaml"
fi

if [[ -n "${VERSION_CHANGES}" ]]; then
    sudo install \
        -o mediamtxmon \
        -g mediamtxmon \
        -m 0644 \
        "${REPO_DIR}/VERSION" \
        "${TARGET}/VERSION"
fi


# ------------------------------------------------------------
# Dienste
# ------------------------------------------------------------

if [[ -n "${BIN_CHANGES}" || -n "${CONFIG_CHANGES}" ]]; then
    echo
    echo "Backend oder collector.yaml geändert."
    echo "Starte Monitoring-Dienste neu ..."

    sudo systemctl restart \
        "${SERVICE_API}" \
        "${SERVICE_COLLECTOR}" \
        "${SERVICE_SYSTEM}"

    echo
    echo "Dienststatus:"

    systemctl is-active \
        "${SERVICE_API}" \
        "${SERVICE_COLLECTOR}" \
        "${SERVICE_SYSTEM}"
else
    echo
    echo "Kein Backend und keine collector.yaml geändert."
    echo "Kein Service-Neustart erforderlich."
fi

echo
echo "Dev-Deployment abgeschlossen."
echo "Browser neu laden und Änderung prüfen."
