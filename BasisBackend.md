# Basis-Backend

```text
+---------------------------+
|      MediaMTX-Server      |
|      (streaming API)      |
+------------+--------------+
             │
             │  Abfrage der API (alle 2s)
+------------▼--------------+
|          Backend          |
|  (Python-Skript + Redis)  |
|  - Holt MediaMTX-Daten    |
|  - Aggregiert & speichert |
|  - Stellt REST/WebSocket  |
|    für Clients bereit     |
+------------+--------------+
             │
             │  Clients rufen REST-API ab
             │  oder verbinden sich per WebSocket
+------------▼--------------+
|          Clients          |
|  (Browser-Dashboard mit   |
|   HTML/JS Frontend)       |
|  - Zeigen aktuelle Daten  |
|  - Empfangen Updates in   |
|    Echtzeit               |
+---------------------------+

```
```
/opt/mediamtx-monitoring-backend/
├── bin/                        # Nur ausführbare Hauptskripte
│   ├── mediamtx_collector.py   # Dauerhafte Sammlung und Redis-Speicherung
│   ├── mediamtx_snapshot.py    # Einmalige Abfrage & Dump → wie ein „Snapshot“
│   ├── mediamtx_api.py         # REST/WebSocket Backend (Phase 2)
│   └── host_metrics_agent.py   # (zukünftig) Systemmetriken wie CPU/RAM
├── lib/                        # Hilfsfunktionen, Module
│   └── config.py
├── static/                     # (für später: Web-Frontend, HTML/CSS/JS)
├── logs/                       # (optional, Logs von Dienst/Daemon)
├── requirements.txt
└── .env                        # Umgebungsvariablen (nicht öffentlich)

```

## 🎯 Ziel dieser Phase:
Ein Python-Skript, das alle 2 Sekunden die MediaMTX-API abfragt, die Daten verarbeitet und in Redis speichert.  
1️⃣ Skript und Redis Direkt testen →  
2️⃣ REST/WebSocket entwickeln →  
3️⃣ das Backend in Docker packen. -> Fertig :-)


## ✅ Schritt 1 – Alles ohne Docker testen
### Installation als System-User

1️⃣ System-User anlegen und Redis auf der mediamtx-VM installieren:
```bash
sudo useradd -r -s /bin/false mediamtxmon

```

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable --now redis-server
redis-cli ping

```

2️⃣ Verzeichnis vorbereiten:
```bash
sudo mkdir -p /opt/mediamtx-monitoring-backend
sudo chown mediamtxmon:mediamtxmon /opt/mediamtx-monitoring-backend
cd /opt/mediamtx-monitoring-backend

```
3️⃣ Venv installieren (als root oder mediamtxmon per sudo):
```bash
sudo -u mediamtxmon python3 -m venv venv
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/pip install requests redis apscheduler

```

4️⃣ Dein Script collector.py anlegen (z. B. per Editor in /opt/mediamtx-monitoring-backend/mediamtx_collector.py).
```python
#!/usr/bin/env python3

import requests
import redis
import json
import sys
from apscheduler.schedulers.background import BackgroundScheduler
import time

MEDIA_MTX_API_URL = "http://localhost:9997"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_KEY = "mediamtx:streams:latest"

# Redis-Client aufsetzen
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def fetch_and_store():
    try:
        paths = requests.get(f"{MEDIA_MTX_API_URL}/v3/paths/list").json()
        srtconns = requests.get(f"{MEDIA_MTX_API_URL}/v3/srtconns/list").json()

        aggregated = []

        for path in paths.get("items", []):
            name = path.get("name")
            source_type = path.get("source", {}).get("type", "unknown")
            bytes_received = path.get("bytesReceived", 0)
            readers = len(path.get("readers", []))

            entry = {
                "name": name,
                "sourceType": source_type,
                "bytesReceived": bytes_received,
                "readers": readers,
            }

            if source_type == "srtConn":
                srt_data = next((s for s in srtconns.get("items", []) if s.get("path") == name), None)
                if srt_data:
                    entry.update({
                        "rtt": srt_data.get("msRTT"),
                        "recvRateMbps": srt_data.get("mbpsReceiveRate"),
                        "linkCapacityMbps": srt_data.get("mbpsLinkCapacity"),
                    })
            aggregated.append(entry)

        # Speichere als JSON-String in Redis
        r.set(REDIS_KEY, json.dumps(aggregated))
        print(f"✅ Daten aktualisiert und in Redis gespeichert ({len(aggregated)} Einträge)")

    except Exception as e:
        print(f"❌ Fehler beim Abrufen oder Speichern: {e}", file=sys.stderr)

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_and_store, 'interval', seconds=2)
    scheduler.start()

    print("🔄 Data Collector läuft... (Drücke STRG+C zum Beenden)")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("\n🛑 Data Collector gestoppt.")

```

### ✅ Systemd-Service anlegen
So läuft der Collector später sauber und automatisch:

/etc/systemd/system/mediamtx-collector.service
```ini
[Unit]
Description=MediaMTX Monitoring Collector
After=network.target

[Service]
Type=simple
User=mediamtxmon
WorkingDirectory=/opt/mediamtx-monitoring-backend
ExecStart=/opt/mediamtx-monitoring-backend/venv/bin/python /opt/mediamtx-monitoring-backend/collector.py
EnvironmentFile=/etc/mediamtx-monitoring.env
Restart=always

[Install]
WantedBy=multi-user.target

```
Dann:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx-collector.service

```
### ✅ Ergebnis:

>Dein Collector läuft als eigener User, sicher isoliert.
>Keine unordentlichen `venvs` im Home oder Arbeitsverzeichnis.
>Saubere Struktur in `/opt`, wie es sich für produktive Linux-Setups gehört.

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
  
