#!/bin/bash

# Konfiguration
SERVICE_USER="mediamtxmon"
INSTALL_DIR="/opt/mediamtx-monitoring-backend"
VENV_DIR="$INSTALL_DIR/venv"

echo "🔍 Prüfe Python-Version..."
PYTHON=$(command -v python3)
PYTHON_VERSION=$($PYTHON --version | awk '{print $2}')
VENV_PKG="python${PYTHON_VERSION%.*}-venv"

echo "✅ Gefundene Python-Version: $PYTHON_VERSION"
echo "📦 Installiere venv-Modul ($VENV_PKG)..."
sudo apt-get update -qq
sudo apt-get install -y "$VENV_PKG"

# Benutzer anlegen, falls noch nicht vorhanden
if id "$SERVICE_USER" &>/dev/null; then
  echo "✅ Benutzer $SERVICE_USER existiert bereits."
else
  echo "➕ Erstelle Systembenutzer $SERVICE_USER..."
  sudo useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
fi

# Verzeichnis vorbereiten
echo "📁 Setze Besitzrechte für $INSTALL_DIR → $SERVICE_USER"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"

# Virtuelle Umgebung erstellen
if [ ! -d "$VENV_DIR" ]; then
  echo "🐍 Erstelle virtuelle Python-Umgebung..."
  $PYTHON -m venv "$VENV_DIR"
  sudo chown -R "$USER:$USER" "$VENV_DIR"
fi

# Aktivieren & Pakete installieren
echo "📦 Installiere Python-Abhängigkeiten..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$INSTALL_DIR/requirements.txt"
deactivate
