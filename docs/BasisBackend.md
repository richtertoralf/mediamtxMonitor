> **Historischer Entwurfsstand:** Dieses Dokument enthält frühere Ideen für periodisch erzeugte JPEG-Snapshots und ist keine aktuelle Installations- oder Betriebsanleitung. Aktuelle Quellen sind [README.md](../README.md) und [docs/architecture.md](architecture.md).

## 📡 MediaMTX Monitoring System
Überwachung von Streamaktivität und Systemressourcen in Echtzeit

<img width="811" height="783" alt="image" src="https://github.com/user-attachments/assets/afcf985b-a2aa-4b11-82da-b9dafdf05b72" />


### 🔎 Ziel des Projekts

Dieses Projekt bietet eine übersichtliche und ressourcenschonende Möglichkeit, die Aktivität eines MediaMTX-Servers in Echtzeit zu überwachen – mit Fokus auf:

- aktive Streams
- empfangene und gesendete Datenmenge
- verbundene Zuschauer
- SRT-spezifische Metriken wie RTT, Linkkapazität und Empfangsrate
- Systemmetriken wie CPU, RAM, Netzwerk, Load Average, Temperatur

### schnelle Installation:
Mediamtx sollte vorher z.B. installiert worden sein:
#### Installation von Mediamtx
Download der Binärdateien, z.B.:
```
# Version prüfen !
wget https://github.com/bluenviron/mediamtx/releases/download/v1.3.0/mediamtx_v1.3.0_linux_arm64v8.tar.gz
```

Entpacken:
```
tar -xzvf mediamtx_v1.3.0_linux_arm64v8.tar.gz
```

Verschieben:
```
sudo mv mediamtx /usr/local/bin/
sudo mv mediamtx.yml /usr/local/etc/
```

#### Mediamtx - Konfiguration anpassen
Das setzt voraus, das mediamtx so wie oben beschrieben installiert wurde.
```

# API aktivieren
sudo sed -i 's/^api: no$/api: yes/' /usr/local/etc/mediamtx.yml
```
#### Installtionsskript für mediamtxMonitor
```
wget https://raw.githubusercontent.com/richtertoralf/mediamtxMonitor/main/install.sh
chmod +x install.sh
```
und ausführen
```
sudo ./install.sh
```

### 🧱 Architekturüberblick

```text
+---------------------------+
|      MediaMTX-Server      |
|      (streaming API)      |
+------------+--------------+
             │
     +-------+---------------+--------------------+
     | mediamtx_collector.py | mediamtx_system.py |
     |     (Streamdaten)     |  (Systemmetriken)  |
     +------------+----------+--------------------+
                  │
         +--------▼----------+
         |      Redis        |
         | + JSON-Cache +    |
         +--------+----------+
                  │
         +--------▼----------+
         |    FastAPI-Server |
         |    + Static Files |
         +--------+----------+
                  │
         +--------▼----------+
         |    Web-Frontend   |
         +-------------------+


```

### 📁 Projektstruktur

```plaintext

/opt/mediamtx-monitoring-backend/
├── install.sh                  ← Skript zur automatischen Installation bzw. Aktualisierung
├── bin/                        ← ausführbare Python-Skripte
│   ├── mediamtx_collector.py   ← Läuft via systemd (Daten abrufen & speichern)
│   ├── mediamtx_api.py         ← FastAPI-Server für API + Static Files
│   ├── mediamtx_system.py      ← erfasst Systemmetriken (CPU, RAM, Load, Disk, Temperatur)
│   └── bitrate.py
│   ├── rtt.py                  ← Hilfsskript zur Berechnung von RTT-Werten (nur für eingehende Streams)
│   └── __init__.py             ← optional, falls bin/ als Modul genutzt wird
│   └── __pycache__/            ← automatisch generiert
│
├── config/                        
│   └── collector.yaml        	← YAML-Konfig für Datensammler (URL, Redis, Ausgabe, Takt)
│
├── lib/                        
│   └── config.py               ← zentrale Konfig (wenn du dort etwas auslagerst)
│
├── logs/                       ← 📁 vorgesehen für Log-Dateien (z. B. später per Logging-Modul)
│
├── static/
│   └── index.html              ← ✅ einfaches HTML-Dashboard, wird vom API-Server ausgeliefert
│   ├── js
│   │   ├── api.js
│   │   ├── main.js
│   │   └── renderer.js
│   ├── css
│   │   └── style.css
│
├── requirements.txt            ← 📄 Python-Abhängigkeiten (psutil, redis, apscheduler)
├── venv/                       ← 🔧 virtuelle Umgebung


```

MediaMTX Konfigurationsdatei:
```bash
/usr/local/etc/mediamtx.yml
```
API muss aktiviert sein!

### 🧑‍💻 Vorbereitung

#### Systemnutzer und Verzeichnisstruktur

```bash
sudo useradd -r -s /bin/false mediamtxmon
```
```bash
sudo mkdir -p /opt/mediamtx-monitoring-backend/{bin,lib,static,logs} \
  && sudo touch /opt/mediamtx-monitoring-backend/bin/{mediamtx_collector.py,mediamtx_api.py,host_metrics_agent.py} \
  && sudo touch /opt/mediamtx-monitoring-backend/lib/config.py \
  && sudo touch /opt/mediamtx-monitoring-backend/requirements.txt \
  && sudo touch /opt/mediamtx-monitoring-backend/.env
```
```bash
sudo chown -R mediamtxmon:mediamtxmon /opt/mediamtx-monitoring-backend
```

#### Redis-Installation

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable --now redis-server
redis-cli ping   # → PONG
```

#### Python-Venv & Abhängigkeiten

```bash
sudo apt install python3-venv
sudo -u mediamtxmon python3 -m venv /opt/mediamtx-monitoring-backend/venv
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/pip install --upgrade pip
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/pip install requests psutil redis apscheduler
```

---

### 🚀 Schritt 1: Collector einrichten

#### 🔁 Collector-Skript
Datei: /opt/mediamtx-monitoring-backend/bin/mediamtx_collector.py 
[mediamtx_collector.py](mediamtx_collector.py)

- Fragt alle 2 Sekunden die Endpunkte `/v3/paths/list` und `/v3/srtconns/list` der MediaMTX-API ab
- Aggregiert die Informationen zu jedem Stream
- Speichert die Daten:
  - in Redis unter `mediamtx:streams:latest`
  - zusätzlich als JSON-Datei unter `/tmp/mediamtx_streams.json`
- Kann alternativ einmalig gestartet werden mit `--once`


#### Testaufruf
```bash
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/python /opt/mediamtx-monitoring-backend/bin/mediamtx_collector.py --once
```
gibt aus, z.B.:
```txt
2025-07-16 21:17:42,820 [INFO] ✅ 1 Einträge in Redis gespeichert.
2025-07-16 21:17:42,820 [INFO] 💾 JSON-Datei gespeichert: /tmp/mediamtx_streams.json
```

#### Beispielausgabe in Redis:

`redis-cli get mediamtx:streams:latest | jq`

```json
[
  {
    "name": "testpattern-sport",
    "sourceType": "srtConn",
    "tracks": ["H264", "MPEG-4 Audio"],
    "bytesReceived": 3413148,
    "readers": 1,
    "rtt": 0.36,
    "recvRateMbps": 1.94,
    "linkCapacityMbps": 1808.58
  }
]

```

#### Dauerbetrieb via systemd

🔧 Collector – /etc/systemd/system/mediamtx-collector.service  
ruft [mediamtx_collector.py](mediamtx_collector.py) auf.

```ini
[Unit]
Description=Mediamtx Monitoring Collector
After=network.target redis.service

[Service]
User=mediamtxmon
WorkingDirectory=/opt/mediamtx-monitoring-backend
ExecStart=/opt/mediamtx-monitoring-backend/venv/bin/python3 bin/mediamtx_collector.py
Restart=always

[Install]
WantedBy=multi-user.target

```
🌐 Webserver – /etc/systemd/system/mediamtx-api.service  
ruft [mediamtx_api.py](mediamtx_api.py) auf.

```ini
[Unit]
Description=Mediamtx Monitoring API (FastAPI)
After=network.target

[Service]
User=mediamtxmon
WorkingDirectory=/opt/mediamtx-monitoring-backend
ExecStart=/opt/mediamtx-monitoring-backend/venv/bin/uvicorn bin.mediamtx_api:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target

```
#### 🛠️ System-Monitor
Datei: /opt/mediamtx-monitoring-backend/bin/mediamtx_system.py

- Erfasst Systemmetriken im Sekundentakt
- Speichert:
  - in Redis unter `mediamtx:system:latest`
  - zusätzlich als JSON-Datei unter `/tmp/mediamtx_system.json`
- Unterstützt Temperaturüberwachung (sofern vom System unterstützt)

#### Dauerbetrieb via systemd

```ini
[Unit]
Description=Mediamtx System Monitor
After=network.target redis.service

[Service]
User=mediamtxmon
WorkingDirectory=/opt/mediamtx-monitoring-backend
ExecStart=/opt/mediamtx-monitoring-backend/venv/bin/python3 bin/mediamtx_system.py
Restart=always

[Install]
WantedBy=multi-user.target
```

📌 Aktivieren & starten:

```bash
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx-collector.service
sudo systemctl enable --now mediamtx-api.service
sudo systemctl enable --now mediamtx-system.service


```
#### Test

Nach Einrichtung der systemd-Dienste:

```bash
sudo systemctl status mediamtx-collector.service
sudo systemctl status mediamtx-api.service
curl http://localhost:8080/api/streams
redis-cli get mediamtx:system:latest | jq

```

#### 🖥️ Web-Dashboard (HTML-Frontend)
Zusätzlich zur API wird automatisch ein einfaches Web-Frontend ausgeliefert:  
📄 Datei: [/opt/mediamtx-monitoring-backend/static/index.html](index.html)  

Zugriff im Browser: `http://<dein-server>:8080/`

Die Seite zeigt:

- Name, Quelle und Leserzahl jedes Streams
- RTT, Empfangsrate und empfangene Bytes bei SRT-Quellen
- Farbliche Warnung bei ungewöhnlichen Werten (z. B. 0 Leser)
- Das Dashboard ruft alle 5 Sekunden die API /api/streams auf.

ℹ️ Die Seite nutzt kein Framework und läuft direkt im Browser – keine weitere Einrichtung nötig.


#### 🎯 Abschluss Phase 1 – Zusammenfassung
✅ Der Collector läuft dauerhaft als Dienst unter einem eigenen Systemnutzer (mediamtxmon)  
✅ Die MediaMTX-API wird alle 2 Sekunden abgefragt – effizient und ressourcenschonend  
✅ Alle aktuellen Streamdaten werden in Redis gespeichert (mediamtx:streams:latest)  
✅ Zusätzlich wird eine JSON-Datei unter /tmp/mediamtx_streams.json erzeugt  
✅ Der Collector ist von der MediaMTX-API entkoppelt – kein direkter API-Zugriff durch Clients nötig  
✅ Die Projektstruktur ist systemkonform aufgebaut (/opt/…)  
✅ Die virtuelle Umgebung (venv) ist sauber getrennt – keine Python-Abhängigkeiten im Home-Verzeichnis  

---

### 🚀 Schritt 2 – REST-API & WebSocket

🎯 Ziel: Clients sollen über eine REST-API aktuelle Monitoring-Daten abrufen können. In einem späteren Schritt folgt die Erweiterung um WebSocket für Echtzeit-Updates.

1️⃣ REST-API mit FastAPI

Beispiel: mediamtx_api.py

z. B. mit FastAPI in einem eigenen Skript:
```python
from fastapi import FastAPI
import redis, json

app = FastAPI()
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

@app.get("/api/streams/latest")
def get_latest():
    data = r.get("mediamtx:streams:latest")
    return json.loads(data) if data else {"error": "no data"}

```

Server starten:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000

```
👉 Die API ist dann erreichbar unter: http://<host>:8000/api/streams/latest


2️⃣ WebSocket (später hinzufügen)

Für die WebSocket-Kommunikation kannst du später:

FastAPI (@app.websocket(...)) oder

ein separates WebSocket-Framework

nutzen, um Clients bei neuen Daten über Redis Pub/Sub automatisch zu benachrichtigen.

🛠 Empfehlung: Zuerst die REST-API stabil einsetzen und testen, dann den WebSocket-Teil ergänzen.

---

### 🚀 Schritt 3: Dockerisierung (optional)

🎯 Ziel: Eine portable, leicht aktualisierbare Version, die du auf deinem MediaMTX-Server oder anderen Hosts einsetzen kannst.

- Dockerfile erstellen (für dein Python-Backend).
- Optional: Redis per Docker oder eigenen Container.
- Am besten alles in einem docker-compose.yml orchestrieren:
  Redis-Container
  Python-Backend-Container
- Sobald du Docker nutzt, kannst du Portfreigaben, Volumes und Umgebungsvariablen sauber definieren.
  
## 📚 Dokumentation

- [README.md – Übersicht](README.md)
- [BasisBackend.md – Architektur & Einrichtung](BasisBackend.md)
