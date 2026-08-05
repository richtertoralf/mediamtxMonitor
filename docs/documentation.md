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
│
├── logs/                       ← Logs (optional)
├── requirements.txt            ← Python-Abhängigkeiten
└── venv/                       ← Virtuelle Umgebung

```


## API-Endpunkte (REST)

Basis: `http://<server>:8080`

| Endpoint                | Beschreibung                            | Beispielausgabe                                      |
| ----------------------- | --------------------------------------- | ---------------------------------------------------- |
| `/api/streams`   | Aktuelle Streams aus Redis              | JSON-Liste mit Name, Quelle, Zuschauer, SRT-Metriken |
| `/api/system`    | Aktuelle Systemmetriken                 | JSON mit CPU, RAM, Netz, Temperatur                  |

### Beispiel – `GET /api/streams`
Antwort (gekürzt):

```json
{
  "streams": [
    {
      "name": "testpattern-basic",
      "source": { "type": "srtConn", "details": { "msRTT": 0.55, "mbpsReceiveRate": 16.73, "mbpsLinkCapacity": 98.18 } },
      "tracks": ["H264", "MPEG-4 Audio"],
      "bytesReceived": 339475545689,
      "bytesSent": 339815173364,
      "readers": []
    }
    // ...
  ],
  "snapshot_refresh_ms": 2000,
  "streamlist_refresh_ms": 5000,
  "systeminfo": {
    "host": "debianMediamtx01",
    "timestamp": 1756905517.1592934,
    "cpu_percent": 18.8,
    "memory": { "total": 2062737408, "used": 361574400, "percent": 25.1 },
    "loadavg": [0.63, 0.42, 0.35],
    "net_mbit_rx": 21.02,
    "net_mbit_tx": 0.18
  }
}
```

`snapshot_refresh_ms` ist ein Legacy-/Kompatibilitätsfeld. Das aktuelle Frontend verwendet es nicht; seine Entfernung ist für eine spätere API-Bereinigung vorgesehen.

### Beispiel – GET /api/system:

```json
{
  "host": "debianMediamtx01",
  "timestamp": 1756905517.1592934,
  "cpu_percent": 18.8,
  "memory": { "total": 2062737408, "used": 361574400, "percent": 25.1 },
  "swap": { "total": 1022357504, "used": 0, "percent": 0.0 },
  "disk": { "total": 32626225152, "used": 3564396544, "percent": 11.5 },
  "loadavg": [0.63, 0.42, 0.35],
  "net_io": { "bytes_recv": 486096582713, "bytes_sent": 4784003131 },
  "net_mbit_rx": 21.02,
  "net_mbit_tx": 0.18,
  "temperature": {},
  "temperature_celsius": null
}

```
### Nützliche CLI-Tests

```bash
# komplette Payload
curl -s http://localhost:8080/api/streams | jq

# nur Streamnamen (jq)
curl -s http://localhost:8080/api/streams | jq -r '.streams[].name'

# RTT pro Stream (falls SRT-Details vorhanden)
curl -s http://localhost:8080/api/streams | jq -r '.streams[] | "\(.name)\t\(.source.details.msRTT // "-")"'

# CPU und Netz (aus systeminfo)
curl -s http://localhost:8080/api/streams | jq '{cpu: .systeminfo.cpu_percent, rx_mbit: .systeminfo.net_mbit_rx, tx_mbit: .systeminfo.net_mbit_tx}'

```

## Redis-Struktur

| Key                         | Inhalt                                  | Beispiel         |
| --------------------------- | --------------------------------------- | ---------------- |
| `mediamtx:streams:latest`   | JSON-Array mit aktiven Streams          | siehe oben       |
| `mediamtx:system:latest`    | JSON-Objekt mit Systemdaten             | siehe oben       |
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
-   On-Demand-WebRTC-Videovorschau

### Datenweg der Videovorschau

```text
Browser → MediaMTX WebRTC → __preview__/<stream> → On-Demand-FFmpeg
        → lokaler RTSP-Originalstream → verkleinerter Vorschaustream zurück zu MediaMTX
```

Der Browser fragt die MediaMTX-Control-API nicht direkt ab; Monitoringdaten gelangen über Collector, Redis und FastAPI zum Browser. Nur für die Videovorschau greift der Browser direkt auf MediaMTX WebRTC zu. Beim Abruf von `__preview__/<stream>` startet FFmpeg on demand, liest das Original lokal per RTSP und erzeugt H.264 mit 192×108 Pixeln, 10 fps und ohne Audio. Nach Ende der Nutzung endet der Prozess automatisch. Periodische JPEG-Dateien und eine lokale Bildablage gehören nicht zum aktuellen System.

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

