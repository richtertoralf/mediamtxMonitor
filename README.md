# 📡 MediaMTX Monitor

Ein leichtgewichtiges Monitoring-Tool für [MediaMTX](https://github.com/bluenviron/mediamtx).  
Zeigt aktive Streams, Zuschauerzahlen, Bitraten und Systemmetriken live im Browser – ohne direkte API-Zugriffe durch Clients.

<img width="600" alt="MediaMTX Monitor Screenshot" src="docs/MediaMTX_Monitor_Screenshot.png" />

## ✨ Features
- Übersicht aktive Streams & Zuschauer
- SRT-Metriken (RTT, Linkkapazität, Empfangsrate)
- Systemmetriken (CPU, RAM, Netz, Temperatur)
- Einfaches Web-Dashboard und JSON-API

## 🚀 Schnellstart
1. MediaMTX installieren und API aktivieren  
2. [Installation ausführen](docs/installation.md)  
3. Dashboard im Browser öffnen → `http://<server>:8080/`

## 📚 Weitere Infos
- [📄 installation.md](docs/installation.md) – Schritt-für-Schritt Einrichtung
- [📖 documentation.md](docs/documentation.md) – Details für Anwender & Entwickler
- [🏗️ architecture.md](docs/architecture.md) – Architektur & Designüberblick

## Live-Dashboard & Snapshots

Das Monitoring stellt den aktuellen Zustand des MediaMTX-Servers live im Browser dar:

Systemzustand: CPU, Load, RAM, Netzwerk, Temperatur

Aktive Streams inkl.:

Publisher-Typ (SRT / RTMP)

RTT, Bitrate, empfangene Daten

Aktive Reader (Zuschauer / Weiterleitungen)

Automatisch erzeugte Snapshots der Videostreams zur visuellen Identifikation

Die Snapshots werden serverseitig erzeugt und ermöglichen es,
Streams schnell zuzuordnen (z. B. Testpattern, OBS-Feeds, Kameras),
ohne einen Player öffnen zu müssen.

Gedacht ist das Dashboard für:

Remote-Produktionen

Debugging von SRT-Verbindungen

Kontrolle von Test- und Dauerstreams

Betrieb ohne GUI auf dem MediaMTX-Server selbst
