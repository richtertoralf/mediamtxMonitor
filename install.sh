#!/bin/bash
set -e

echo "📦 Installation des MediaMTX Monitoring Systems startet..."

INSTALL_DIR="/opt/mediamtx-monitoring-backend"
REPO_URL="https://github.com/snowgameslive/mediamtx-monitoring-backend.git"
PYTHON_BIN="python3"
USER="mediamtxmon"
VENV_DIR="$INSTALL_DIR/venv"

# 🔧 Voraussetzung: Python 3 + Pip + Redis
echo "🔍 Prüfe Voraussetzungen..."
apt update && apt install -y ffmpeg python3 python3-venv python3-pip redis-server git

# 👤 Systemnutzer erstellen (falls noch nicht vorhanden)
if ! id "$USER" &>/dev/null; then
  echo "👤 Erstelle Systemnutzer $USER..."
  useradd --system --no-create-home --shell /usr/sbin/nologin "$USER"
fi

# 📁 Klonen oder Aktualisieren des Repos
if [ ! -d "$INSTALL_DIR" ]; then
  echo "📁 Klone Git-Repo nach $INSTALL_DIR..."
  git clone "$REPO_URL" "$INSTALL_DIR"
else
  echo "🔁 Aktualisiere bestehendes Repository..."
  cd "$INSTALL_DIR"
  git pull
fi

# 🐍 Python-Venv einrichten
echo "🐍 Erzeuge virtuelle Python-Umgebung..."
cd "$INSTALL_DIR"
$PYTHON_BIN -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# 🔐 Besitzer anpassen
chown -R "$USER":"$USER" "$INSTALL_DIR"

# 🔧 systemd-Dienste installieren
echo "🛠️ Installiere systemd-Dienste..."

SERVICE_DIR="/etc/systemd/system"

install_service() {
  local name=$1
  local exec=$2
  echo "📄 Schreibe Dienst $name..."
  cat <<EOF > "$SERVICE_DIR/$name.service"
[Unit]
Description=$name
After=network.target

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $exec
Restart=always

[Install]
WantedBy=multi-user.target
EOF
}

install_service "mediamtx-api" "bin/mediamtx_api.py"
install_service "mediamtx-collector" "bin/mediamtx_collector.py"
install_service "mediamtx-snapshots" "bin/mediamtx_snapshots.py"
install_service "mediamtx-systeminfo" "bin/mediamtx_systeminfo.py"

# 🔄 Dienste aktivieren und starten
systemctl daemon-reexec
systemctl daemon-reload
systemctl enable --now mediamtx-api.service
systemctl enable --now mediamtx-collector.service
systemctl enable --now mediamtx-snapshots.service
systemctl enable --now mediamtx-systeminfo.service

echo "✅ Installation abgeschlossen."
echo "🌐 Web-Dashboard erreichbar unter: http://<SERVER-IP>:8080"
