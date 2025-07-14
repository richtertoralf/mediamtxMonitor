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
```
# Systembenutzer anlegen
sudo useradd -r -s /bin/false mediamtxmon

# Optional (wenn du später eigene Logs oder cron willst):
sudo mkdir -p /var/log/mediamtxmon
sudo chown mediamtxmon:mediamtxmon /var/log/mediamtxmon

# Projektstruktur erstellen
sudo mkdir -p /opt/mediamtx-monitoring-backend/{bin,lib,static,logs} \
  && sudo touch /opt/mediamtx-monitoring-backend/bin/{mediamtx_collector.py,mediamtx_snapshot.py,mediamtx_api.py,host_metrics_agent.py} \
  && sudo touch /opt/mediamtx-monitoring-backend/lib/config.py \
  && sudo touch /opt/mediamtx-monitoring-backend/requirements.txt \
  && sudo touch /opt/mediamtx-monitoring-backend/.env

# Besitzrechte und Dateizugriffsrechte setzen
sudo chown -R mediamtxmon:mediamtxmon /opt/mediamtx-monitoring-backend
sudo chmod +x /opt/mediamtx-monitoring-backend/bin/*.py

# (Optional) virtuelle Umgebung vorbereiten
sudo -u mediamtxmon python3 -m venv /opt/mediamtx-monitoring-backend/venv
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/pip install --upgrade pip

# päter installierst du damit die Abhängigkeiten aus requirements.txt:
sudo -u mediamtxmon /opt/mediamtx-monitoring-backend/venv/bin/pip install -r /opt/mediamtx-monitoring-backend/requirements.txt

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

4️⃣ Script mediamtx_collector.py anlegen (in /opt/mediamtx-monitoring-backend/mediamtx_collector.py).


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
  
