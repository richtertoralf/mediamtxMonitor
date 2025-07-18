# 📡 MediaMTX Stream Monitoring

Ein leichtgewichtiges Monitoring-Tool für MediaMTX-Server (vormals `rtsp-simple-server`). Zeigt aktive Streams, Zuschauerzahlen, Bitraten und SRT-Metriken übersichtlich im Browser an – ohne direkte API-Zugriffe durch Clients.

## 🎯 Ziel

- **Übersicht:** Aktive Streams und Live-Metriken auf einen Blick
- **Effizienz:** MediaMTX-API wird nur einmal zentral abgefragt
- **Sicherheit:** Clients benötigen keinen Zugang zur MediaMTX-Instanz
- **Modularität:** Einfach erweiterbar für historische Daten oder Servermetriken

## 🧱 Architektur

- **Python Collector:** fragt regelmäßig die MediaMTX-API ab
- **Redis:** speichert aktuelle (und künftig historische) Daten
- **FastAPI:** liefert JSON-API, WebSockets und statische HTML/JS-Seiten
- **Browser-Frontend:** zeigt Daten live und responsiv an

```plain
+-------------+      +------------+      +---------+      +--------------+
| MediaMTX    +----> | Collector  +----> | Redis   +<---->+  Webserver   |
| (API)       |      | (Python)   |      | Cache   |      | (FastAPI)    |
+-------------+      +------------+      +---------+      +------+-------+
                                                               |
                                                               v
                                                       +--------+--------+
                                                       |   Web Frontend  |
                                                       +-----------------+

```

### 🛠️ Wie funktioniert es?

Das Monitoring besteht aus drei Bausteinen:

✅ **Backend (Python)**  
- Fragt alle 2 Sekunden die MediaMTX-API ab (`/v3/paths/list` und `/v3/srtconns/list`).
- Verarbeitet die Daten und speichert sie in **Redis**.
- Benachrichtigt alle verbundenen Browser über WebSockets, wenn es neue Daten gibt.

✅ **Redis**  
- Speichert den aktuellen Zustand der Streams.
- Kann auch historische Daten (z. B. RTT-Verlauf) speichern, damit du später Trends analysieren kannst.

✅ **Frontend (Browser)**  
- Lädt beim Start die aktuellen Daten vom Backend.
- Verbindet sich per **WebSocket**, um automatisch aktuelle Infos zu erhalten.
- Zeigt die Daten übersichtlich in Tabellen oder Diagrammen an.

### 🏗️ Warum dieser Aufbau?

- Das Backend fragt den MediaMTX-Server nur **einmal** ab, egal wie viele Clients verbunden sind.  
  → Das entlastet den MediaMTX-Server und spart Ressourcen.
- Die Clients müssen **nicht direkt auf den MediaMTX-Server zugreifen**, sondern nur auf das Backend.  
  → Das erhöht die Sicherheit, da du die MediaMTX-API nicht öffentlich zugänglich machen musst.
- Du kannst **beliebig viele Clients** anschließen, ohne den MediaMTX-Server stärker zu belasten.
- Du kannst später leicht neue Features ergänzen, z. B. Speicherung von Langzeit-Daten oder Anzeige der Server-Auslastung (CPU, RAM, Netzwerk).

## 🚀 Erste Schritte
👉 Für Setup, Code-Struktur und geplante Erweiterungen siehe [📄 BasisBackend.md](BasisBackend.md)


### 🔧 Toolchain
- Python 3.11
- FastAPI + Uvicorn
- Redis
- HTML, CSS, Vanilla JS (optional Chart.js)

### 📂 Struktur
```plaintext
bin/
  mediamtx_collector.py     ← Datensammler (MediaMTX → Redis)
  mediamtx_api.py           ← FastAPI-Server (JSON + Web + WebSocket)
static/
  index.html                ← Web-Frontend
  style.css, app.js         ← Darstellung & WebSocket-Handling
BasisBackend.md             ← Detaillierte technische Beschreibung
README.md                   ← Dieses Dokument
```

---

## 📌 Status

✅ Live-Ansicht der aktiven Streams

🔜 Historie (Redis Streams)

🔜 Servermetriken (CPU, RAM, Netz)

---

## ⚙️ Ideen

```mermaid
graph TD
    subgraph "MediaMTX Server"
        MMT["MediaMTX Instance"]
    end

    subgraph "Monitoring Backend (Dedicated Server/VM)"
        A["Python Data Collector (APScheduler)"] --> B("Requests: MediaMTX API")
        B --> C{"Data Aggregation & Processing"}
        C --> D["Redis: Store Latest (mediamtx:streams:latest)"]
        C --> E["Redis Streams: Store History (mediamtx:history:*)"]
        D --> F["Redis: Pub/Sub (mediamtx:updates)"]

        G["Python Web Server (FastAPI/Flask)"] -- "REST API (initial data)" --> D
        G -- "WebSocket Server" --> F
        G -- "REST API (historical data)" --> E
    end

    subgraph "Clients (Web Browsers)"
        H["HTML/CSS/JS Frontend"] -- "Initial Data (HTTP GET)" --> G
        H -- "Realtime Updates (WebSocket)" --> G
        H -- "Historical Data (HTTP GET)" --> G
    end

    subgraph "Future: Agent on MediaMTX Host"
        I["Python Agent (psutil)"] --> E
    end

    style D fill:#f9f,stroke:#333,stroke-width:2px
    style E fill:#f9f,stroke:#333,stroke-width:2px
    style F fill:#f9f,stroke:#333,stroke-width:2px
```

## 📚 Dokumentation

- [README.md – Übersicht](README.md)
- [BasisBackend.md – Architektur & Einrichtung](BasisBackend.md)

