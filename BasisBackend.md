# 📡 MediaMTX Stream Monitoring

## 🔎 Ziel des Projekts

Dieses Projekt bietet eine übersichtliche und ressourcenschonende Möglichkeit, die Aktivität eines MediaMTX-Servers in Echtzeit zu überwachen – mit Fokus auf:

- aktive Streams
- empfangene Datenmenge
- verbundene Zuschauer
- SRT-spezifische Metriken wie RTT, Linkkapazität und Empfangsrate

## ✅ Architekturüberblick – Basis-Backend

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

## 📁 Projektstruktur

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

## 🧑‍💻 Vorbereitung: Installation & Einrichtung
### Systemnutzer und Verzeichnisstruktur
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
### Redis-Installation
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable --now redis-server
redis-cli ping   # → PONG
```
### Python-Venv & Abhängigkeiten
```bash
sudo apt install python3-venv
sudo -u mediamtxmon python3 -m venv /opt/mediamtx-monitoring-backend/venv
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/pip install --upgrade pip
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/pip install requests redis apscheduler
```
## ✅ Schritt 1 – Daten von der mediamtx API abrufen

### 🔁 Collector-Skript
Datei: /opt/mediamtx-monitoring-backend/bin/mediamtx_collector.py  

- Fragt alle 2 Sekunden die Endpunkte `/v3/paths/list` und `/v3/srtconns/list` der MediaMTX-API ab
- Aggregiert die Informationen zu jedem Stream
- Speichert die Daten:
  - in Redis unter `mediamtx:streams:latest`
  -   - zusätzlich als JSON-Datei unter `/tmp/mediamtx_streams.json`  
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

### 🧩 Systemd-Dienst (optional)
Datei: /etc/systemd/system/mediamtx-collector.service
```ini
[Unit]
Description=MediaMTX Monitoring Collector
After=network.target

[Service]
Type=simple
User=mediamtxmon
WorkingDirectory=/opt/mediamtx-monitoring-backend
ExecStart=/opt/mediamtx-monitoring-backend/venv/bin/python /opt/mediamtx-monitoring-backend/bin/mediamtx_collector.py
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Aktivieren:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx-collector.service

```

### 📦 Abhängigkeiten (requirements.txt)
```txt
requests
redis
apscheduler

```

### 🎯 Abschluss Phase 1 – Zusammenfassung

✔️ Der Collector läuft als Dienst  
✔️ Er ist von der API entkoppelt  
✔️ Alle aktuellen Streamdaten sind in Redis verfügbar  
✔️ JSON-Export ist aktiv  


---

## ✅ Schritt 2 – REST- und WebSocket-Webserver entwickeln
🎯 Ziel: Client-Anwendungen sollen aktuelle Daten aus Redis abrufen können.

1️⃣ REST-API erstellen:

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
2️⃣ WebSocket hinzufügen:

Später kannst du FastAPI oder ein dediziertes WebSocket-Framework nutzen, um Clients in Echtzeit zu benachrichtigen.

Erst REST zum Abrufen testen – WebSocket-Teil baust du danach.

## ✅ Schritt 3 – Alles in Docker packen
🎯 Ziel: Eine portable, leicht aktualisierbare Version, die du auf deinem MediaMTX-Server oder anderen Hosts einsetzen kannst.

- Dockerfile erstellen (für dein Python-Backend).
- Optional: Redis per Docker oder eigenen Container.
- Am besten alles in einem docker-compose.yml orchestrieren:
  Redis-Container
  Python-Backend-Container
- Sobald du Docker nutzt, kannst du Portfreigaben, Volumes und Umgebungsvariablen sauber definieren.
  
