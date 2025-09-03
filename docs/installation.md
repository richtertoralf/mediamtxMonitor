# 🚀 Installation – MediaMTX Monitor

Diese Anleitung zeigt die schnelle Einrichtung des MediaMTX Monitor auf einem Linux-Server (Ubuntu/Debian/Raspberry Pi OS).  
Ergebnis: Ein Web-Dashboard unter `http://<server>:8080/`, das Streams und Systemmetriken live anzeigt.

---

## Voraussetzungen
- **MediaMTX** installiert (siehe unten)
- API von MediaMTX aktiviert (`api: yes` in `mediamtx.yml`)
- Linux-Server mit Python ≥ 3.9
- Internetzugang zum Download des Installationsskripts

---

## Schritt-für-Schritt

### 1. MediaMTX installieren
```bash
# Version vorher prüfen!
wget https://github.com/bluenviron/mediamtx/releases/download/v1.14.0/mediamtx_v1.14.0_linux_amd64.tar.gz
tar -xzvf mediamtx_v1.14.0_linux_amd64.tar.gz
sudo mv mediamtx /usr/local/bin/
sudo mv mediamtx.yml /usr/local/etc/

# API aktivieren
sudo sed -i 's/^api: no$/api: yes/' /usr/local/etc/mediamtx.yml
```

### 2. MediaMTX Monitor installieren
```bash
wget https://raw.githubusercontent.com/richtertoralf/mediamtxMonitor/main/install.sh
chmod +x install.sh
sudo ./install.sh
```
Das Skript richtet automatisch ein:

- Redis
- Virtuelle Python-Umgebung
- Alle benötigten Pakete
- Systemd-Dienste für Collector & API
- Projektverzeichnis unter /opt/mediamtx-monitoring-backend

## Test
### 1. Status prüfen:
```bash
sudo systemctl status mediamtx-collector.service
sudo systemctl status mediamtx-api.service
sudo systemctl status mediamtx-snapshots.service
sudo systemctl status mediamtx-system.service
```

### 2. Browser öffnen:

`👉 http://<server>:8080/`

### 3. API testen:
```
curl http://localhost:8080/api/streams
```

## Update
erneut ausführen:
```bash
wget https://raw.githubusercontent.com/richtertoralf/mediamtxMonitor/main/install.sh
chmod +x install.sh
sudo ./install.sh
```

## Deinstallation
```bash
# Dienste stoppen
sudo systemctl disable --now mediamtx-collector.service
sudo systemctl disable --now mediamtx-api.service
sudo systemctl disable --now mediamtx-snapshots.service
sudo systemctl disable --now mediamtx-system.service

# Verzeichnis löschen
sudo rm -rf /opt/mediamtx-monitoring-backend
```
---
👉 Für Details zu Architektur, API-Endpunkten und Projektstruktur siehe documentation.md

