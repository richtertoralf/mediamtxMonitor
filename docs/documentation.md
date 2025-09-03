# Documentation – MediaMTX Monitor

Dies ist die erweiterte Dokumentation für Anwender, die mehr Details möchten, sowie für Entwickler.  
Sie beschreibt die Projektstruktur, API-Endpunkte, Redis-Keys und das Datenmodell des MediaMTX Monitor.

---

## Projektstruktur

Standardpfad: `/opt/mediamtx-monitoring-backend`

```plaintext
/opt/mediamtx-monitoring-backend/
├── bin/                        ← ausführbare Python-Skripte
│   ├── mediamtx_collector.py   ← Fragt MediaMTX-API ab, speichert Daten in Redis
│   ├── mediamtx_api.py         ← FastAPI-Server (REST-API + Dashboard)
│   ├── mediamtx_snapshots.py   ← Erstellt Snapshots von Streams (optional)
│   ├── mediamtx_system.py      ← Erfasst Systemmetriken (CPU, RAM, Load, Temp)
│   └── ...
│
├── config/
│   └── collector.yaml          ← Konfig für Collector (MediaMTX-URL, Redis, Intervalle)
│
├── lib/                        ← Hilfsfunktionen / Module
│   └── config.py
│
├── static/                     ← Web-Frontend
│   ├── index.html              ← Dashboard
│   ├── js/                     ← API-Aufrufe, Renderer, Frontend-Logik
│   ├── css/                    ← Layout & Styles
│   └── snapshots/              ← Bilder von Streams (falls aktiviert)
│
├── logs/                       ← Logs (optional)
├── requirements.txt            ← Python-Abhängigkeiten
└── venv/                       ← Virtuelle Umgebung

## API-Endpunkte (REST)

| Endpoint                | Beschreibung                            | Beispielausgabe                                      |
| ----------------------- | --------------------------------------- | ---------------------------------------------------- |
| `/api/streams/latest`   | Aktuelle Streams aus Redis              | JSON-Liste mit Name, Quelle, Zuschauer, SRT-Metriken |
| `/api/system/latest`    | Aktuelle Systemmetriken                 | JSON mit CPU, RAM, Netz, Temperatur                  |
| `/api/snapshots/latest` | (optional) Letzte Snapshots der Streams | Dateipfade / Base64                                  |

### Beispiel – Streams:
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
### Beispiel – System:
```json
{
  "cpu_percent": 12.3,
  "ram_used_mb": 842,
  "ram_total_mb": 3936,
  "net_in_mbps": 5.1,
  "net_out_mbps": 4.7,
  "load_avg": [0.12, 0.08, 0.02],
  "temperature_c": 47.5
}

```

## Redis-Struktur

| Key                         | Inhalt                                  | Beispiel         |
| --------------------------- | --------------------------------------- | ---------------- |
| `mediamtx:streams:latest`   | JSON-Array mit aktiven Streams          | siehe oben       |
| `mediamtx:system:latest`    | JSON-Objekt mit Systemdaten             | siehe oben       |
| `mediamtx:snapshots:<name>` | (optional) Bilddaten                    | Base64 oder Pfad |
| `mediamtx:history:*`        | (optional) Zeitreihen für Langzeitdaten | Redis Streams    |

>Vorteil:
>Redis hält immer die letzten Werte im Speicher. Clients müssen nicht direkt auf die MediaMTX-API zugreifen, sondern lesen nur Redis-Daten über das Backend.

## Datenmodell

**Streams (JSON)**

- name: Name des Streams (Pfad in MediaMTX)
- sourceType: Quelle (publisher, srtConn, …)
- tracks: Audio-/Videoformate
- bytesReceived: Empfangene Bytes seit Verbindungsstart
- readers: Anzahl der verbundenen Clients
- rtt: Round-Trip-Time (ms)
- recvRateMbps: Empfangsrate (Mbit/s)
- linkCapacityMbps: Theoretische Bandbreite (Mbit/s, SRT)

**System (JSON)**

- cpu_percent: CPU-Auslastung in %
- ram_used_mb / ram_total_mb: Speicherverbrauch
- net_in_mbps / net_out_mbps: Netzwerk-Throughput
- load_avg: Load Average (1/5/15 min)
- temperature_c: Temperatur (sofern unterstützt)

## Web-Frontend

- Erreichbar unter http://<server>:8080/
- HTML + Vanilla JS, keine Frameworks
- Holt Initialdaten über REST (/api/...)
- Aktualisierung via Polling (5s) oder WebSocket (zukünftig)
- Darstellung:
-   Streams (Name, Quelle, Leserzahl, SRT-Metriken)
-   Systemmetriken (CPU, RAM, Netz, Temperatur)
-   Snapshots (falls aktiviert)

## Erweiterungsmöglichkeiten

- WebSockets (statt Polling) für Echtzeit-Updates über Redis Pub/Sub
- Langzeit-Historie mit Redis Streams (z. B. RTT-Verlauf, Bandbreite)
- Prometheus Exporter für Integration in bestehendes Monitoring
- Docker-Support (docker-compose mit Redis + Monitor)
- Mehrere MediaMTX-Server parallel überwachen (Cluster)
- Alerts (z. B. bei X Zuschauern oder hoher RTT)

## Status

✅ Aktuelle Streams & Zuschauer im Browser

✅ SRT-Metriken (RTT, Linkkapazität, Empfangsrate)

✅ Systemmetriken (CPU, RAM, Netz, Temperatur)

✅ JSON-API & Web-Dashboard

🔜 WebSockets für Echtzeit

🔜 Historie & Diagramme

🔜 Docker-Support

