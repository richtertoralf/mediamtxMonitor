## 📡 MediaMTX Stream Monitoring

### 🔎 Ziel des Projekts

Dieses Projekt bietet eine übersichtliche und ressourcenschonende Möglichkeit, die Aktivität eines MediaMTX-Servers in Echtzeit zu überwachen – mit Fokus auf:

- aktive Streams
- empfangene Datenmenge
- verbundene Zuschauer
- SRT-spezifische Metriken wie RTT, Linkkapazität und Empfangsrate

### 🧱 Architekturüberblick

```text
+---------------------------+
|      MediaMTX-Server      |
|      (streaming API)      |
+------------+--------------+
             │  API-Abfrage alle 2 Sekunden
+------------▼--------------+
|          Backend          |
|  (Python + Redis)         |
|  - Holt MediaMTX-Daten    |
|  - Aggregiert & speichert |
|  - Schreibt JSON-Datei    |
+------------+--------------+
             │
             │ (in Phase 2: REST & WebSocket)
+------------▼--------------+
|         Clients           |
|  (z. B. Browser-Frontend) |
|  - Lesen Redis-Daten      |
|  - Empfangen Live-Updates |
+---------------------------+

```

### 📁 Projektstruktur

```
/opt/mediamtx-monitoring-backend/
├── bin/
│   ├── mediamtx_collector.py     ← läuft im Intervall oder einmalig (--once)
│   ├── mediamtx_snapshot.py      ← manuelle Dump-Variante (optional)
│   ├── mediamtx_api.py           ← REST/WebSocket API (Phase 2)
│   └── host_metrics_agent.py     ← Host-Metriken (Phase 4, geplant)
├── lib/
│   └── config.py                 ← zentrale Konfiguration (optional)
├── static/                       ← später: HTML/JS Frontend
├── logs/                         ← eigene Log-Dateien (optional)
├── requirements.txt              ← Python-Abhängigkeiten
└── .env                          ← Umgebungsvariablen

```

### 🧑‍💻 Vorbereitung

#### Systemnutzer und Verzeichnisstruktur

```bash
sudo useradd -r -s /bin/false mediamtxmon
```
```bash
sudo mkdir -p /opt/mediamtx-monitoring-backend/{bin,lib,static,logs} \
  && sudo touch /opt/mediamtx-monitoring-backend/bin/{mediamtx_collector.py,mediamtx_snapshot.py,mediamtx_api.py,host_metrics_agent.py} \
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
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/pip install requests redis apscheduler
```

---

### 🚀 Schritt 1: Collector einrichten

#### 🔁 Collector-Skript
Datei: /opt/mediamtx-monitoring-backend/bin/mediamtx_collector.py  

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

📌 Aktivieren & starten:

```bash
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx-collector.service
sudo systemctl enable --now mediamtx-api.service

```
#### Test

Nach Einrichtung der systemd-Dienste:

```bash
sudo systemctl status mediamtx-collector.service
sudo systemctl status mediamtx-api.service
curl http://localhost:8080/api/streams
```

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
  
