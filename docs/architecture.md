# 🏗️ Architecture – MediaMTX Monitor

Dieses Dokument beschreibt den Aufbau, die Designentscheidungen und die Erweiterbarkeit des MediaMTX Monitor.  
Es richtet sich an Entwickler und Beitragende.

---

## 🔎 Überblick

Der MediaMTX Monitor besteht aus vier Kernkomponenten:

1. **Collector (Python)**  
   - Fragt in kurzen Intervallen (Standard: 2s) die MediaMTX-API ab  
   - Aggregiert Stream-Daten (Zuschauer, Bitrate, SRT-Metriken)  
   - Speichert Ergebnisse in Redis

2. **Redis (In-Memory DB)**  
   - Zentrale Datendrehscheibe (aktuelle Werte, Historie, Pub/Sub)  
   - Entlastet MediaMTX: nur *eine* API-Abfrage, egal wie viele Clients

3. **Webserver (FastAPI)**  
   - Stellt REST-API und optional WebSockets bereit  
   - Liefert das statische Web-Frontend aus  
   - Abstraktionsebene: Clients greifen für Monitoringdaten nicht direkt auf die MediaMTX-Control-API zu

4. **Web-Frontend (HTML/JS)**  
   - Holt Initialdaten über REST  
   - Hält Verbindung per Polling (5s) oder künftig WebSocket  
   - Stellt Monitoringdaten und eine On-Demand-WebRTC-Videovorschau dar
   - Greift für die Vorschau direkt auf MediaMTX WebRTC zu

---

## 📊 Datenfluss

```text
+-------------+      +------------+      +---------+      +--------------+
|  MediaMTX   +----> | Collector  +----> |  Redis  +<---->+   FastAPI    |
|   (API)     |      |  (Python)  |      | Cache   |      |   Webserver  |
+-------------+      +------------+      +---------+      +------+-------+
                                                               |
                                                               v
                                                       +---------------+
                                                       |   Frontend    |
                                                       +---------------+
```

Die Videovorschau verwendet einen getrennten Datenweg:

```text
Browser → MediaMTX WebRTC → __preview__/<stream> → On-Demand-FFmpeg
        → lokaler RTSP-Originalstream → verkleinerter H.264-Vorschaustream zurück zu MediaMTX
```

Der Abruf von `__preview__/<stream>` startet FFmpeg bei Bedarf. FFmpeg liest den Originalstream lokal per RTSP und erzeugt H.264 mit 192×108 Pixeln, 10 fps und ohne Audio. Nach Ende der Nutzung endet der Prozess automatisch. Periodische JPEG-Dateien werden nicht erzeugt.

## Designentscheidungen

1. Warum Redis?

Extrem schnell für häufige kleine Writes/Reads

Ermöglicht mehrere Datentypen: Key/Value, Streams (Historie), Pub/Sub (WebSockets)

Einfach zu deployen (apt install, Docker, Cloud-Ready)

2. Warum FastAPI?

Asynchron → geeignet für WebSockets

Automatische API-Dokumentation (Swagger, OpenAPI)

Einfach erweiterbar für Authentifizierung, CORS, Rate-Limiting

3. Warum Trennung Collector ↔ Webserver?

Collector kann unabhängig laufen und Daten sammeln

Webserver bleibt leichtgewichtig (nur Auslieferung von Daten)

Skalierbarkeit: mehrere Webserver können auf dieselbe Redis-Instanz zugreifen

4. Warum keine direkten MediaMTX-API-Zugriffe vom Browser?

Monitoringdaten: Die MediaMTX-Control-API wird ausschließlich vom Collector abgefragt. Der direkte WebRTC-Zugriff dient nur der Videovorschau.

Effizienz: nur eine API-Abfrage → kein Overload bei vielen Clients

Flexibilität: Backend kann Daten normalisieren/ergänzen

## Module & Erweiterungen

Collector

Holt /v3/paths/list und /v3/srtconns/list

Aggregiert Bytes, Leser, RTT, Bandbreite

Speichert JSON unter mediamtx:streams:latest

Systeminfo-Agent

Nutzt psutil (CPU, RAM, Load, Netz, Temp)

Schreibt JSON nach mediamtx:system:latest

Videovorschau

MediaMTX startet FFmpeg für `__preview__/<stream>` on demand.

FFmpeg liest das Original lokal per RTSP und publiziert die verkleinerte H.264-Vorschau zurück zu MediaMTX.

Der Prozess endet nach Ende der Nutzung automatisch; eine Bildablage oder ein eigener Redis-Key ist nicht beteiligt.

## Skalierungsszenarien

Single Node (Default)

Collector, Redis, FastAPI, Frontend auf einem Server

Getrenntes Backend & Frontend

Redis auf dediziertem Host

Mehrere FastAPI-Server greifen auf Redis zu

Cluster-Setup

Mehrere MediaMTX-Server → ein zentraler Monitor-Server

Collector fragt APIs aller Server ab (konfigurierbar in collector.yaml)

Cloud-native (Docker/Kubernetes)

Redis + FastAPI + Collector je als Container

Ingress für Web-Dashboard

Optional Helm-Chart für K8s

## Zukünftige Erweiterungen

WebSockets über Redis Pub/Sub → echte Push-Updates ins Frontend

Historie in Redis Streams → Diagramme (z. B. RTT-Verlauf)

Prometheus Exporter → Integration in Grafana/Alertmanager

Multi-Server-Support → zentrale Überwachung mehrerer MediaMTX-Instanzen

Auth Layer → optional Login/Token für API & Dashboard

Docker Compose → docker-compose up für Schnellstart

Alerts → Slack, E-Mail oder Webhooks bei Problemen

## Fazit

Architektur ist leichtgewichtig, modular, skalierbar

MediaMTX wird entlastet, da API nur einmal zentral abgefragt wird

Redis als Puffer ermöglicht Echtzeit + Historie + Skalierung

FastAPI ist flexibel erweiterbar (REST, WebSocket, Auth)

Frontend bewusst minimalistisch (HTML/JS) → keine externe Abhängigkeit
