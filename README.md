# 📡 MediaMTX Stream & Server Monitoring

## Projektübersicht

Dieses Projekt bietet eine umfassende Monitoring-Lösung für MediaMTX-Server, die sowohl Echtzeit-Stream-Metriken (Pfade, SRT-Verbindungen, RTT, Bandbreite) als auch zukünftig Server-Ressourcennutzung (CPU, RAM, Netzwerk I/O) erfasst. Ziel ist es, Administratoren einen klaren und aktuellen Überblick über den Zustand ihrer MediaMTX-Instanzen zu geben, ohne den MediaMTX-Server selbst unnötig zu belasten.

Die Lösung besteht aus einem robusten Backend, das Daten sammelt und persistent speichert, sowie einem schlanken Web-Frontend für die Visualisierung in Echtzeit und die Analyse historischer Trends.

## Kernfunktionen

* **Echtzeit-Stream-Metriken:** Überwachung von `paths`, `bytesReceived`, `readers`, `sourceType`, sowie spezifischen SRT-Metriken wie `msRTT`, `mbpsReceiveRate`, `mbpsLinkCapacity`.
* **Historische Datenhaltung:** Speicherung relevanter Metriken in einer performanten Datenbank (Redis Streams) für Langzeitanalyse und Trendvisualisierung (z.B. RTT-Schwankungen, Bandbreitennutzung).
* **Minimaler Impact auf MediaMTX:** Die gesamte Aggregations- und Verarbeitungslogik findet auf einem dedizierten Backend-Server statt, um den MediaMTX-Server so wenig wie möglich zu belasten.
* **Echtzeit-Updates:** Push-Benachrichtigungen an die Web-Clients mittels WebSockets sorgen für eine sofortige Aktualisierung der angezeigten Daten.
* **Zukünftige Erweiterungen:** Integration von allgemeinen Server-Metriken (CPU-Last, Speichernutzung, Netzwerk-Bandbreite) direkt vom MediaMTX-Host.

## Architektur

Die Lösung ist modular aufgebaut und gliedert sich in folgende Hauptkomponenten:

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
    style F fill:#f9f,stroke:#333,stroke-width:2px333,stroke-width:2px
```
