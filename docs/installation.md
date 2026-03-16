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
- Systemd-Dienste
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
Danach Reboot des Computers, da aktuell im Skript `install.sh` der neustart der Dienste nicht implementiert ist.

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

---

## 📡 Network & Bonding Optimization (S.A.NE + MediaMTX)

Um einen stabilen Betrieb von **6 parallelen HD-Streams** über eine gebündelte Internetanbindung (z. B. 2x LTE + 1x DSL via Bondix S.A.NE) zu gewährleisten, müssen die UDP-Puffergrößen des Linux-Kernels sowohl auf dem **Relay-Server** als auch auf dem **Streaming-Server** massiv erhöht werden.

### Warum das wichtig ist
Standardmäßig reserviert Linux nur ca. 208 KB für UDP-Empfangspuffer. Bei Jitter (typisch für LTE/DSL-Mix) müssen Pakete im RAM zwischengespeichert werden, um die korrekte Reihenfolge wiederherzustellen (Re-Ordering). Ein zu kleiner Puffer führt bei Netzwerk-Bursts sofort zu **Paketverlusten (UDP Drops)**, was sich in Bild-Artefakten oder Stream-Abbrüchen äußert.



### 1. Kernel-Tuning (Sysctl)
Die folgenden Werte erhöhen den Puffer auf **16 MB**, um Schwankungen im Millisekundenbereich sicher abzufangen:

```bash
# Temporär anwenden
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.rmem_default=16777216
sudo sysctl -w net.core.wmem_max=16777216
sudo sysctl -w net.core.wmem_default=16777216

# Permanent speichern (/etc/sysctl.conf)
echo "net.core.rmem_max=16777216" | sudo tee -a /etc/sysctl.conf
echo "net.core.rmem_default=16777216" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max=16777216" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_default=16777216" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 2. MediaMTX Konfiguration
Zusätzlich muss MediaMTX angewiesen werden, diese Puffer für RTSP/UDP-Ingests auch tatsächlich anzufordern. In der mediamtx.yml:
```yaml
# In den globalen Einstellungen oder unter pathDefaults
rtspUDPReadBufferSize: 16777216
```

### 3. Monitoring & Validierung
Ob die Einstellungen aktiv sind, lässt sich mit ss (Socket Statistics) prüfen. Der Wert rb (Receive Buffer) sollte nach einem Dienst-Neustart bei ca. 33.554.432 (16MB x 2 Kernel-Overhead) liegen:

```bash
# Prüfen des aktiven Sockets (Beispiel Port 44343 für Bondix oder 8000 für MediaMTX)
sudo ss -unlmp | grep <PORT>
```
Achte darauf, dass der Counter d (Drops) am Ende der Zeile auf 0 bleibt.
