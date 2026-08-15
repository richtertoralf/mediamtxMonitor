# Architektur des MediaMTX Monitor

Dieses Dokument beschreibt die verbindlichen Architekturgrenzen und das
schrittweise Zielbild dieses Repositories. Es ist kein Auftrag, die bestehende
Struktur auf einmal umzubauen. Änderungen müssen klein, kompatibel, testbar und
einzeln deploybar bleiben.

## Systemziel und Abgrenzung

Der MediaMTX Monitor erfasst und visualisiert Stream-, Verbindungs-, Transport-
und Systemmetriken eines MediaMTX-Nodes. Die Architektur soll später mehrere
MediaMTX-Nodes unterstützen, ohne Node, Stream, Publisher und Reader fachlich zu
vermischen.

NDI-Monitoring gehört ausdrücklich nicht in dieses Repository. Ein späterer
NDI-Monitor darf Konzepte und Gestaltungsideen übernehmen, bleibt aber ein
technisch getrenntes Projekt mit eigenem Repository und Deployment.

MediaMTX, Redis, FastAPI, FFmpeg, systemd und die Monitoring-Anwendung sind
getrennte Komponenten. Das Git-Repository ist die Source of Truth; die
Installation unter `/opt/mediamtx-monitoring-backend` ist nur der ausgerollte
Laufzeitstand.

## Architekturprinzip

Dieses Projekt verwendet eine pragmatische modulare Architektur. Eine
Abstraktion wird nur eingeführt, wenn sie ein konkretes aktuelles Problem löst
oder einen absehbaren nächsten Entwicklungsschritt ermöglicht. Unnötige
Enterprise- oder Clean-Architecture-Komplexität, leere Schichten und vorsorglich
eingeführte Frameworks sind zu vermeiden.

Bestehende funktionierende Komponenten werden bevorzugt weiterentwickelt. Ein
pauschaler Umbau nach `src/` ist nicht vorgesehen.

## Aktueller Implementierungsstand

Die Laufzeit überwacht genau eine MediaMTX-Instanz, standardmäßig auf demselben
Host. Der Collector in
`bin/mediamtx_collector.py` steuert den seriellen Polling-Loop und verwendet die
bereits extrahierten Module für Control-API-Zugriff, Normalisierung, Metriken,
Redis-Keys und Snapshot-I/O. FastAPI wird als Modul-App betrieben; die drei
Monitoring-Prozesse halten ihre Laufzeitabhängigkeiten teilweise noch in
Modulzustand. Systemerfassung und ihr Loop liegen gemeinsam in
`bin/mediamtx_systeminfo.py`.

Das aktuelle Modell kennt Streams, Publisher und Reader, aber noch keine
stabile `node_id` und kein Multi-Node-Routing. Preview verwendet im Browser den
aktuellen Host mit festem HTTP-Schema und WebRTC-Port 8889. Eine
Node-spezifische Preview-Konfiguration ist noch nicht implementiert.

Die vorhandenen Modulgrenzen sind bewusst schrittweise entstanden. Ein dünner
Collector-Entry-Point, eine FastAPI-App-Factory, vollständig injizierbare Stores
und eine getrennte `SystemMetricsSource` sind Zielbild und kein aktueller
Implementierungsstand.

## Zielarchitektur und fachliche Hauptobjekte

Die folgenden Abschnitte beschreiben die verbindlichen Grenzen, auf die bei
künftigen, fachlich begründeten Änderungen schrittweise hingearbeitet wird.
Formulierungen wie „soll“ oder „langfristig“ bezeichnen keine bereits
implementierte Funktion.

### Node

Ein Node ist eine überwachte MediaMTX-Instanz einschließlich ihres
Monitoring-Kontexts. Er besitzt langfristig eine stabile `node_id` und ordnet
Control API, Systemmetriken, Streams und Preview-Konfiguration einander zu.

### Stream

Ein Stream ist ein MediaMTX-Pfad auf genau einem Node. Der Streamname ist nur
innerhalb seines Nodes eindeutig und darf nicht allein als globale Identität
verwendet werden.

### Publisher

Ein Publisher ist die Quelle eines Streams. Er besitzt eine eigene fachliche
Rolle, Verbindungsidentität, Richtung, Verkehrsdaten und gegebenenfalls
protokollspezifische Transportmetriken.

### Reader

Ein Reader konsumiert einen Stream. Reader und Publisher dürfen gemeinsame
Hilfsstrukturen verwenden, bleiben aber fachlich getrennte Konzepte. Richtung,
Metriken, Zustands-Keys und Health-Bewertung müssen ihre jeweilige Rolle
erkennen lassen.

## Datenfluss

### Stream- und Verbindungsdaten

```text
MediaMTX Control API
        |
        v
MediaMTXClient
        |
        v
Raw MediaMTX Data
        |
        v
Normalization
        |
        v
Metric Enrichment (bitrate, RTT, protocol metrics)
        |
        v
Redis Snapshot / Redis Measurement State
        |
        +-- Redis Short History (ca. 60 s)
        |
        v
FastAPI
        |
        v
Web UI
```

### Systemmetriken (Zielbild)

```text
Host / System
        |
        v
SystemMetricsSource
        |
        v
Normalization and metric calculation
        |
        v
Redis Snapshot
        |
        v
FastAPI
        |
        v
Web UI
```

## Datenebenen

Die folgenden Ebenen sind fachlich und im Code nachvollziehbar zu trennen:

1. **Raw MediaMTX Data:** Möglichst unveränderte Antworten der MediaMTX Control
   API. Feldnamen und Struktur folgen der jeweiligen MediaMTX-Version.
2. **Normalized Monitoring Data:** Stabiler, MediaMTX-Monitor-spezifischer
   Vertrag für Node, Stream, Publisher, Reader und Medieninformationen.
3. **Metrics:** Gemessene oder berechnete Werte wie Byte-Zähler, Bitrate, RTT,
   Retransmissions und SRT-Link-Capacity. Messwerte sind noch keine Bewertung.
4. **Health Evaluation:** Nachvollziehbare Bewertung normalisierter Metriken mit
   Status, Regeln und Gründen. Sie bleibt von Erfassung und Berechnung getrennt.
5. **Presentation:** Formatierung, Sortierung und sichere Darstellung für API
   und UI, ohne MediaMTX-Rohdaten erneut zu normalisieren.

Die Web-UI darf keine Backend-Normalisierung rekonstruieren. Muss die UI native
MediaMTX-Felder interpretieren oder fachliche Fallbacks nachbauen, fehlt die
Normalisierung im Backend oder der API-Vertrag ist unvollständig.

## Komponenten und Verantwortungen

### Entry Points

Ausführbare Dienste laden validierte Konfiguration, richten Logging ein,
erzeugen Abhängigkeiten und starten Scheduler oder Loops. Sie enthalten keine
umfangreiche fachliche Normalisierung. Das Importieren eines Moduls darf keine
Netzwerkverbindung herstellen und keine Hintergrundarbeit starten.

### MediaMTXClient

Der vorgesehene `MediaMTXClient` kapselt Basis-URL, Timeouts, HTTP-Aufrufe,
API-Endpunkte und transportbezogene Fehler. Produktiver Python-Code greift nur
über diesen Client auf die MediaMTX Control API zu. Der Client liefert Rohdaten
und führt keine UI-Formatierung oder Health-Bewertung durch.

Diagnosewerkzeuge unter `cli-tools/` dürfen unabhängig davon direkt auf die
Control API zugreifen. Sie sind keine wiederverwendbare Produktivlogik.

### Configuration

Laufzeitkonfiguration wird an einer nachvollziehbaren Stelle geladen,
normalisiert und validiert. Defaults werden nicht über mehrere Dienste verteilt.
Konfiguration wird explizit an Komponenten übergeben. Installationspfade dürfen
in Entry Points, Units und Installationswerkzeugen bekannt sein, nicht jedoch in
reiner Fachlogik.

### Normalizer

Normalizer wandeln Raw MediaMTX Data in das stabile Monitoring-Modell um. Sie
sind möglichst nebenwirkungsfrei und führen weder HTTP- noch Redis-Zugriffe aus.
Allgemeine Streamdaten und protokollspezifische Felder bleiben erkennbar
getrennt.

### Metric Enrichment

Diese Komponente ergänzt normalisierte Daten um berechnete Bitraten, RTT und
protokollspezifische Metriken. Zeit und benötigter Messzustand sollen injizierbar
und testbar sein. Metrikerfassung entscheidet nicht über Health-Status.

### Redis Store

Der Redis Store kapselt Verbindung, JSON-Snapshots sowie deren Lese- und
Schreibfehler. Redis dient sowohl als aktueller Snapshot-Speicher als auch als
kurzlebiger Zustand für Delta- und Glättungsberechnungen; diese Rollen müssen in
API und Key-Namen unterscheidbar bleiben.

Pro Verbindung wird zusätzlich eine zeitlich begrenzte Kurzzeithistorie als
Redis Sorted Set geführt. Der Score ist der reale Messzeitpunkt; alte Samples
werden zeitbasiert entfernt und verwaiste Histories laufen per TTL aus. Diese
History ist kein Langzeitarchiv. Die optionalen 10-s- und 60-s-Fenster werden
aus derselben Rohhistorie berechnet.

Die Laufzeitauswertung bildet für native SRT-Transport-RTT p50 und p95 linear
interpoliert; die Variation ist `p95 - p50`. Bereits durch den Collector aus
nativen SRT-Gesamtzählern gebildete
Intervallereignisse werden innerhalb der Fenster summiert. Daraus entsteht in
dieser Stufe keine Health- oder Stability-Bewertung.

### Collector-Cadence und Current State

MediaMTX ist die einzige Quelle für aktuell existierende Publisher und Reader.
Der Collector liest die Path-Topologie ungefähr einmal pro Sekunde und fragt in
diesem schnellen Pfad nur die Detaillisten der dort tatsächlich referenzierten
Verbindungstypen ab. Der Current Snapshot wird nach jedem erfolgreichen
Path-Poll vollständig ersetzt. Ein separater Redis-Wert `collected_at` zum
Snapshot-Key macht den Zeitpunkt des letzten erfolgreichen Schreibens in der
API sichtbar.

Langsamer wechselnde bzw. diagnostische Daten bleiben im seriellen Collector,
werden aber seltener aktualisiert: die MediaMTX-Version alle 60 Sekunden,
Path-Forward-Ziele und die optionale JSON-Diagnosedatei alle 5 Sekunden.
Der Monitor verwendet ausschließlich Metriken, die MediaMTX beziehungsweise das
jeweilige Transportprotokoll bereitstellt. Externe ICMP-Pings werden nicht
ausgeführt. Protokolle ohne native RTT besitzen daher keine RTT-Anzeige.

MediaMTX-Connection-IDs werden als eigenständige aktuelle Connections
behandelt. Der Monitor führt keine IP-, Port- oder zeitbasierte Deduplizierung
reconnectender Reader durch. Mehrere gleichzeitig von MediaMTX gemeldete
Connections werden gleichzeitig dargestellt. Kurzzeithistorien sind strikt vom
Current State getrennt: Sie dürfen nach einem Disconnect bis zu ihrer TTL
fortbestehen, werden aber weder zur Connection-Erkennung noch zur
Snapshot-Zusammenführung verwendet.

### Redis Key Schema

Redis-Keys werden ausschließlich über zentrale Builder aufgebaut. Präfixe,
Suffixe, Rollen, TTL-Verwendung und Node-Zuordnung dürfen nicht frei über
Fachmodule verteilt werden. Zustands-Keys für Publisher und Reader bleiben
getrennt.

### System Metrics

Systemmetriken erfassen Hostdaten über eine klar begrenzte Quelle, normalisieren
sie und schreiben einen Node-bezogenen Snapshot. Erfassung, Berechnung von
Netzwerkraten, Persistenz und Dienststeuerung sollen getrennt testbar sein.

### FastAPI

FastAPI stellt Snapshots und statische Dateien bereit. Die API liest über den
zentralen Store, definiert einen stabilen Antwortvertrag und enthält keine
MediaMTX-Control-API-Abfragen oder erneute fachliche Normalisierung. Eine
App-Erzeugung soll mit injizierbaren Abhängigkeiten testbar sein.

### Web UI

Die Vanilla-JavaScript-Oberfläche ruft die Monitor-API ab, formatiert Werte und
rendert sie sicher. Sie greift nicht auf die Control API zu und interpretiert
keine MediaMTX-Rohfelder als Ersatz für Backend-Normalisierung.

### Preview

Preview bleibt ein eigener Integrationspfad aus UI, MediaMTX und FFmpeg. Die
Preview-Basis-URL und ihr Nodebezug müssen langfristig konfigurierbar sein. Die
Preview-Logik gehört weder in die Streamnormalisierung noch in die Health-
Bewertung.

### Installation und Deployment

`install.sh` ist ausschließlich für frische Installationen bestimmt.
`devtools/deploy-dev.sh` überträgt den geprüften Repository-Stand in die
Entwicklungsinstallation. Installation, Deployment, MediaMTX-Konfiguration und
systemd-Steuerung bleiben von der fachlichen Monitoring-Logik getrennt.

## Zielbild der Abhängigkeitsrichtung

```text
Entry Points
  -> Configuration
  -> MediaMTXClient / SystemMetricsSource
  -> Normalization
  -> Metric Enrichment
  -> Redis Store

FastAPI -> Redis Store
Web UI  -> FastAPI
Preview -> configured node preview endpoint
```

Abhängigkeiten zeigen von technischer Verdrahtung zu klar begrenzten
Komponenten. Normalizer, Modelle und Health-Regeln hängen nicht von Entry
Points, systemd, Installationspfaden, FastAPI oder konkreten globalen
Redis-Verbindungen ab.

## Multi-Node-Zielbild

Die aktuelle Laufzeit darf zunächst einen Node überwachen. Neue Strukturen
müssen folgende spätere Erweiterung ermöglichen, ohne sie vorzeitig vollständig
zu implementieren:

- Jeder Node besitzt eine stabile `node_id`.
- Jeder Stream ist explizit einem Node zugeordnet.
- Redis-State-Keys enthalten die Node-ID.
- Preview-Konfiguration und Preview-Endpunkt sind Node-bezogen.
- Ein Stream wird nicht allein über seinen Namen identifiziert; mindestens
  `node_id` und Streamname bilden die Identität.
- Publisher- und Reader-Zustände bleiben auch über Nodes hinweg kollisionsfrei.

## Schrittweises Zielbild der Dateistruktur

Die folgende Struktur zeigt mögliche Modulgrenzen. Neue Dateien werden erst
angelegt, wenn die entsprechende Logik tatsächlich aus bestehendem Code
extrahiert wird. Kleine Module dürfen zusammenbleiben, wenn eine Trennung keinen
praktischen Nutzen bringt.

```text
bin/
├── __init__.py
├── mediamtx_api.py              # dünner API-Entry-Point
├── mediamtx_collector.py        # dünner Collector-Entry-Point
├── mediamtx_systeminfo.py       # dünner System-Entry-Point
├── monitoring_config.py         # zentrale Laufzeitkonfiguration
├── mediamtx_client.py           # Control-API-Adapter, bei Extraktion
├── mediamtx_model.py            # fachliche Modelle und reine Helfer
├── stream_normalizer.py         # Raw -> normalized, bei Extraktion
├── redis_store.py               # Snapshot-I/O, bei Extraktion
├── redis_keys.py                # zentrales Key-Schema, falls separat sinnvoll
├── bitrate.py                   # Bitratenmetrik
├── connection_history.py        # 60-s-History und Fensterstatistiken
├── srt_health.py                # SRT-Metriken; Bewertung später getrennt
├── health.py                    # erst bei konkreter Health-Bewertung
└── system_metrics.py            # testbare Host-Erfassung, bei Extraktion

static/js/
├── api.js
├── main.js
├── renderer.js
├── systeminfo.js
├── formatters.js                # erst bei tatsächlicher gemeinsamer Nutzung
└── preview.js                   # erst bei tatsächlicher Extraktion
```

Es gibt keinen pauschalen `src/`-Umbau. Bestehende Pfade und Entry Points werden
nur in kleinen Migrationsschritten verändert. Jeder Schritt muss das bisherige
Verhalten erhalten, passende Tests besitzen und separat deploybar sein.

## Verbindliche Architekturregeln

1. NDI-Monitoring bleibt außerhalb dieses Repositories.
2. Entry Points konfigurieren und verdrahten Komponenten; sie enthalten keine
   umfangreiche Fachlogik.
3. Nur `MediaMTXClient` greift aus produktivem Python-Code direkt auf die
   MediaMTX Control API zu.
4. Diagnose-CLI-Werkzeuge dürfen die Control API direkt abfragen, bleiben aber
   von Produktivmodulen getrennt.
5. Redis-Zugriff und Redis-Key-Aufbau werden zentralisiert.
6. Jeder Node-bezogene Redis-State-Key enthält langfristig eine stabile
   `node_id`.
7. Node, Stream, Publisher und Reader bleiben eigenständige fachliche Konzepte.
8. Raw MediaMTX Data wird vor der API-Ausgabe in ein stabiles Monitoring-Modell
   normalisiert.
9. Protokollspezifische Interpretation bleibt von allgemeinen Streamdaten
   getrennt.
10. Health-Bewertung bleibt von Messwerterfassung und Metrikberechnung getrennt.
11. Die UI rendert und formatiert; sie rekonstruiert keine Backend-
    Normalisierung.
12. Mit Einführung des Multi-Node-Modells werden Preview-Endpunkte
    konfigurierbar und einem Node zugeordnet.
13. Konfiguration soll schrittweise zentral geladen, validiert und explizit
    übergeben werden.
14. Modulimporte erzeugen keine Netzwerkverbindungen, Scheduler oder Loops.
15. Installation und Deployment bleiben außerhalb der fachlichen Monitoring-
    Logik.
16. MediaMTX allein bestimmt den aktuellen Connection-Bestand; History erzeugt
    oder verlängert keinen Current State.
17. Reconnectende Reader werden nicht anhand von Adresse, Port oder Zeitfenster
    dedupliziert.
