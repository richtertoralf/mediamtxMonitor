# MediaMTX Monitor

MediaMTX Monitor zeigt aktive MediaMTX-Streams, Publisher, Reader, Bitraten,
SRT-Metriken und Systemdaten in einem kleinen Web-Dashboard. Das Frontend bleibt
Vanilla JavaScript. Redis puffert die vom Collector gelesenen Daten, FastAPI
liefert API und Dashboard aus.

Der Monitoringumfang ist bewusst protokollspezifisch: SRT besitzt derzeit die
tiefste Transport- und Ereignisauswertung; für RTMP/RTMPS und RTSP/RTSPS stellt
der Monitor jeweils andere passende MediaMTX-Metriken dar, weitere Protokolle
werden überwiegend generisch dargestellt. Fehlende MediaMTX-Metriken werden
nicht durch externe Messungen gegen Publisher oder Reader ersetzt. Details
stehen im [MediaMTX-v1.21+-Datenmodell](docs/MEDIAMTX_V1_21_DATA.md) und in der
[Architekturdokumentation](docs/ARCHITECTURE.md).

> **Sicherheitshinweis:** Dashboard und Monitor-API besitzen keine eingebaute
> Authentifizierung und stellen auf Port 8080 unverschlüsseltes HTTP bereit.
> Dieser Port darf nicht ungeschützt aus dem öffentlichen Internet erreichbar
> sein. MediaMTX Monitor ist für die bewusste Integration durch Betreiber in
> eine von ihnen kontrollierte Server- und Netzwerkarchitektur vorgesehen,
> beispielsweise in ein internes LAN, ein Management-VLAN, ein separates
> WireGuard- beziehungsweise Managementnetz oder hinter einen Reverse Proxy mit
> HTTPS und bei Bedarf Authentifizierung. Firewall, Zugriffsschutz, TLS und
> öffentliche Erreichbarkeit liegen in der Verantwortung des Betreibers.

Der grundlegende Datenfluss ist:

```text
MediaMTX Control API → Collector → Redis → FastAPI → Browser
```

Der Collector aktualisiert den Stream-Snapshot standardmäßig ungefähr einmal
pro Sekunde. Der Browser ruft `GET /api/streams` regelmäßig per HTTP-Polling
ab; WebSockets werden nicht verwendet. Redis hält neben aktuellen Snapshots
kurzlebigen Messzustand und eine Kurzzeithistorie für Verbindungsmetriken.

![MediaMTX Monitor Dashboard](MediamtxMonitor.png)

Voraussetzung ist **MediaMTX v1.21.0 oder neuer**. Der Collector prüft die
laufende Version über `/v3/info` und meldet ältere oder nicht eindeutig
erkennbare Versionen als nicht unterstützt. Details zum erfassten Datenmodell
stehen in [docs/MEDIAMTX_V1_21_DATA.md](docs/MEDIAMTX_V1_21_DATA.md).

## Dienste

MediaMTX und der Monitor laufen auf derselben Maschine als getrennte
systemd-Dienste. Ein Fehler des Monitor-Dashboards soll den laufenden
Streamingdienst nicht beenden.

| Komponente | Betrieb |
|---|---|
| MediaMTX | unabhängiger Dienst `mediamtx.service`, systemd-Standardbenutzer `root` |
| MediaMTX-Monitor | drei Dienste unter `mediamtxmon:mediamtxmon` |

Ein Ausfall von MediaMTX beendet den Collector nicht. Der Collector meldet dann
API-Fehler und fragt weiter; ein früherer erfolgreicher Snapshot kann
währenddessen als veraltet angezeigt werden. Details zur Diagnose stehen unter
[Troubleshooting](docs/TROUBLESHOOTING.md). Umgekehrt beeinflusst ein
Monitor-Ausfall den MediaMTX-Streamingdienst auf derselben Maschine nicht.

## Unterstützte Neuinstallationen

Der Installer ist für Debian-basierte Linux-Systeme mit apt, dpkg und
systemd vorgesehen, insbesondere:

- Debian  
- Ubuntu  
- Raspberry Pi OS  

Unterstützte Architekturen:

- x86_64 mit Debian-Architektur amd64  
- aarch64 mit Debian-Architektur arm64  
- 32-Bit-ARMv6 mit Debian-Architektur armhf  
- 32-Bit-ARMv7 mit Debian-Architektur armhf  

arm64 wird vom Installer unterstützt. Dazu gehören auch aktuelle
64-Bit-Installationen von Raspberry Pi OS auf einem Raspberry Pi.

32-Bit-ARM-Systeme werden erkannt und können mit den MediaMTX-Archiven
linux_armv6 beziehungsweise linux_armv7 installiert werden. Diese Systeme
wurden jedoch nicht getestet. Der Installer gibt deshalb eine Warnung aus und
setzt die Installation anschließend fort.

Nicht Debian-basierte Linux-Distributionen werden vom Installer abgelehnt.
32-Bit-x86-Systeme mit i386-/i686-Architektur werden ebenfalls abgelehnt, da
dafür kein vorgesehenes MediaMTX-Archiv existiert.

`sudo ./install.sh` wählt automatisch zwischen Fresh-Installation und der
Wiederverwendung einer vollständig vorhandenen MediaMTX-Installation. Die
Laufzeit benötigt MediaMTX v1.21.0 oder neuer; bei einer Fresh-Installation
richtet der Installer diese MediaMTX-Installation zusammen mit Redis, FFmpeg,
Python-Venv und den Monitor-Diensten ein. Bei Wiederverwendung werden
MediaMTX-Binary, Unit und globale Konfiguration nur geprüft und nicht
verändert. Dabei müssen Control API, WebRTC und die monitor-eigene
`__preview__`-Regel bereits vorhanden und `/v3/info` erreichbar sein; andernfalls
bricht der Reuse-Pfad mit einer verständlichen Meldung vor jeder Änderung ab.

### MediaMTX-Endpoints

`api_base_url` in `config/collector.yaml` ist die Control-API-Basis für den
Collector. `webrtc_base_url` ist die vom **Browser** erreichbare HTTP(S)-Basis
für die Vorschau; leer bedeutet keine Preview-Verbindung. Die Monitor-API
liefert nur die WebRTC-Adresse an das Frontend, nicht die Control-API-Adresse.

Bei Reuse ist die browserseitige WebRTC-URL ausdrücklich erforderlich. Die API-URL
kann ebenfalls vorgegeben werden, beispielsweise:

```bash
sudo ./install.sh --mediamtx-api-url http://127.0.0.1:9998 \
  --mediamtx-webrtc-url https://media.example:9443
```

Der Betreiber wählt die effektiven Endpoints unter Berücksichtigung der vom
Dienst verwendeten Datei, `MTX_*`-Overrides, TLS und gegebenenfalls Reverse Proxy.
Ohne explizite API-URL liest der Installer mit System-PyYAML ausschließlich
`api`, `apiAddress` und `apiEncryption` aus der MediaMTX-Datei. PyYAML ist zu
diesem Zeitpunkt nicht durch die spätere Monitor-venv garantiert: Fehlt es,
endet die Ermittlung mit einem Hinweis auf `python3-yaml` oder die explizite URL.
Es werden dafür keine Pakete vor den lesenden Vorprüfungen installiert.

Automatischer Bootstrap ist nur beim direkten Dienstaufruf mit genau dieser
Binary und Datei möglich. Environment-Dateien, `PassEnvironment`, abweichende
Prozessargumente oder `MTX_API`/`MTX_APIADDRESS`/`MTX_APIENCRYPTION` im laufenden
Prozess erfordern eine explizite URL. Nicht lesbare Dienst-/Prozessinformationen
führen ebenfalls zum Abbruch, nicht zum Raten. Wildcard-Bind-Adressen werden
für den lokalen Zugriff in Loopback übersetzt; TLS-Prüfung bleibt aktiv.
YAML liefert nur den erwarteten Endpoint, keinen Beweis der laufenden Version.
`--mediamtx-config DATEI` wählt bei Reuse die zu validierende Datei (Default:
`/usr/local/etc/mediamtx.yml`); deren Werte sind kein Beweis des Runtime-Zustands.
Erst `/v3/info` prüft Erreichbarkeit, Runtime-Version und Startzeit. Danach prüfen
`/v3/config/global/get` und `/v3/config/paths/list` WebRTC und Preview-Hook.
Bei Fehlern erfolgt ein Abbruch ohne Änderung der bestehenden Installation.
`--validate-conf` prüft zusätzlich die Datei. Es erfolgen keine YAML-Textprüfungen
im Reuse-Pfad und kein automatischer Neustart.

Fresh erzeugt HTTP-API auf Loopback (Default 9997) und HTTP-WebRTC auf allen
Interfaces (Default 8889). `--mediamtx-api-port` und `--mediamtx-webrtc-port`
ändern diese erzeugten Einstellungen und die Monitor-Konfiguration gemeinsam.
Die Browser-Adresse wird standardmäßig aus der ersten Host-IP gebildet;
`--mediamtx-webrtc-url` kann sie explizit setzen, etwa bei einem vorhandenen Proxy.
Der Installer richtet dafür weder TLS-Zertifikate noch einen Proxy ein.
HTTPS-URLs bei Reuse benötigen vertrauenswürdige Zertifikate; TLS-Prüfung wird
nicht umgangen. URLs dürfen keine Zugangsdaten, Query-Parameter oder Fragmente
enthalten. API-Authentisierung wird durch diese Änderung nicht eingerichtet.
Browser-Erreichbarkeit, NAT und ICE müssen weiterhin betrieblich geprüft werden.

Bei bestehenden Monitor-Installationen muss `webrtc_base_url` vor dem Einsatz
dieser Änderung gesetzt werden; es gibt keinen stillen Port-8889-Fallback.
Die Diagnosewerkzeuge unter `cli-tools/` akzeptieren `MEDIAMTX_API_URL`
(Default `http://localhost:9997`). Beispiele mit Standardports entsprechend anpassen.

## Installation

```bash
sudo ./install.sh
```

Die Fresh-Installation wurde mit MediaMTX v1.21.0 auf Ubuntu Server 24.04 LTS
amd64 getestet. Diese Version ist als getesteter Repository-Default festgelegt.
Für einen ausdrücklich gewünschten Fresh-Stand kann optional
`--mediamtx-version VERSION` angegeben werden; bei vorhandener MediaMTX-
Infrastruktur wird diese Angabe nicht angewendet.

Der Installer ermittelt:

- über /etc/os-release, ob das System Debian-basiert ist,  
- über dpkg --print-architecture die Architektur des installierten Userspace,  
- über uname -m die Maschinen- und bei 32-Bit-ARM die ARM-Version,  
- über den Benutzerparameter die zu installierende MediaMTX-Version.  

Anschließend wählt er automatisch eines der passenden MediaMTX-Archive:

- linux_amd64  
- linux_arm64  
- linux_armv6  
- linux_armv7  

Der Installer lädt Binary und vollständige `mediamtx.yml` aus demselben
offiziellen Release-Archiv und prüft dessen SHA-256-Summe. 
Er aktiviert, wenn nicht schon aktiv, API,
RTSP und WebRTC und ergänzt ausschließlich die On-Demand-Vorschauregel.  

## Installierte Komponenten und Pfade

| Inhalt | Pfad |
|---|---|
| MediaMTX-Binary | `/usr/local/bin/mediamtx` |
| MediaMTX-Konfiguration | `/usr/local/etc/mediamtx.yml` |
| Monitor | `/opt/mediamtx-monitoring-backend` |
| Monitor-Konfiguration | `/opt/mediamtx-monitoring-backend/config/collector.yaml` |
| systemd-Units | `/etc/systemd/system/mediamtx*.service` |

Zusätzlich installiert der Installer FFmpeg, Redis und eine Python-Venv mit den
Monitor-Abhängigkeiten.

## Version und Upgrade

Die installierte Monitor-Version und ein Produktions-Upgrade werden über das
mitinstallierte Kommando verwaltet:

```bash
mediamtx-monitor --version
sudo mediamtx-monitor --upgrade
```

Das Upgrade aktualisiert Programmcode, Python-Abhängigkeiten im bestehenden
venv, die CLI, die Versionsdatei und die drei systemd-Units der
Monitoring-Dienste. Die lokale `config/collector.yaml` bleibt absichtlich
unverändert: Sie ist die betreiberspezifische Laufzeitkonfiguration und gehört
dem Betreiber. Dieses Kompatibilitätsprinzip orientiert sich am Umgang von
MediaMTX mit der lokalen `mediamtx.yml`: Ein Upgrade ersetzt die vorhandene
lokale Konfiguration nicht durch die Konfigurationsvorlage einer neuen Version.

Neue optionale Monitor-Einstellungen müssen deshalb mit rückwärtskompatiblen
Standardwerten eingeführt werden. Bewusst gesetzter technischer Ausgangspunkt
des unterstützten MediaMTX-Daten- und Konfigurationsmodells ist MediaMTX
v1.21.0. Eine automatische Migration oder Ersetzung der `collector.yaml` ist
im Rahmen dieses Betreiber- und Kompatibilitätsprinzips nicht vorgesehen. Für
eine Erstinstallation ist weiterhin `install.sh` zu verwenden.

Das gilt auch für `redis.namespace` und `node.id`: Alte lokale Konfigurationen
bleiben beim Upgrade unverändert und erhalten zur Laufzeit automatisch die
Defaults `mediamtx-monitor:` beziehungsweise `local`. Die Vorlage für neue
Installationen enthält beide Werte explizit.
Die zwei bekannten alten Snapshot-Werte `mediamtx:streams:latest` und
`mediamtx:system:latest` werden bei der Konfigurationsauflösung ausschließlich
in ihre neuen fachlichen Namen übersetzt; alte Redis-Keys werden weder gelesen
noch migriert.

## Redis-Namespace und Node-ID

Der Monitor verwendet weiterhin Redis DB 0. Sie darf gemeinsam mit anderen
Anwendungen genutzt werden, weil die Zustände durch Anwendungs-Namespaces
getrennt sind:

```text
Redis DB 0
├── gfx:*                                  GFX Engine
└── mediamtx-monitor:node:<node-id>:*      MediaMTX Monitor
```

`redis.namespace` legt den zentralen Anwendungs-Namespace fest und ist
standardmäßig `mediamtx-monitor:`. `node.id` identifiziert die überwachte
MediaMTX-Instanz; der Single-Node-Default ist `local`. Eine abweichende stabile
ID wie `node-a` erzeugt beispielsweise
`mediamtx-monitor:node:node-a:streams:latest`. Fachmodule erzeugen nur den Teil
ab `streams:latest`; der vollständige Prefix wird zentral beim Redis-Zugriff
ergänzt.

Der Namespace wird getrimmt und intern auf genau einen abschließenden
Doppelpunkt normalisiert. `node.id` wird ebenfalls getrimmt und muss dem Muster
`[A-Za-z0-9._-]+` entsprechen. Fehlende Werte verwenden die Defaults; explizit
leere oder ungültige Werte sind Konfigurationsfehler und verhindern den
Dienststart.

## Dienste und Benutzer

| Dienst | Benutzer | Aufgabe |
|---|---|---|
| `mediamtx.service` | root (kein `User=` in der Unit) | Streamingserver |
| `mediamtx-api.service` | `mediamtxmon` | Dashboard und Monitor-API |
| `mediamtx-collector.service` | `mediamtxmon` | MediaMTX-Control-API abfragen |
| `mediamtx-system.service` | `mediamtxmon` | Systemmetriken erfassen |
| `redis-server.service` | Distributionseinstellung | Zwischenspeicher |

Die mitgelieferte `mediamtx.service` enthält bewusst kein `User=` und folgt
damit der [offiziellen systemd-Anleitung von MediaMTX](https://mediamtx.org/docs/features/start-on-boot),
deren Vorlage ebenfalls kein `User=` enthält. Ohne diese Angabe läuft der
Dienst unter systemd standardmäßig als root; MediaMTX Monitor trifft damit
keine von MediaMTX abweichende Entscheidung über den Dienstbenutzer. Betreiber
können MediaMTX eigenverantwortlich unter einem eingeschränkten Benutzer
betreiben. Dabei müssen sie selbst alle benötigten Rechte berücksichtigen,
unter anderem für Konfiguration, automatisch erzeugte oder verwendete
Zertifikate, Aufzeichnungen, Logs, Hooks sowie weitere von der jeweiligen
MediaMTX-Konfiguration verwendete Dateien und Verzeichnisse.

Die Deinstallation der Monitor-Anwendung entfernt ausschließlich deren
eigene Ressourcen. `mediamtx.service`, das MediaMTX-Binary und die globale
`mediamtx.yml` bleiben erhalten; eine Entfernung gemeinsamer Infrastruktur ist
eine separate Betreiberoperation.

## Ports

Für die mit MediaMTX v1.21.0 getestete Konfiguration:

| Port | Funktion |
|---:|---|
| 8554 | RTSP |
| 1935 | RTMP |
| 8888 | HLS |
| 8889 | WebRTC und Monitor-Vorschau |
| 8890 | SRT |
| 9997 | MediaMTX-Control-API |
| 8080/TCP | Dashboard und Monitor-API; HTTP ohne integrierte Authentifizierung, nicht ungeschützt öffentlich freigeben |
| 6379/TCP | Redis; nur lokal beziehungsweise in einem geschützten Backend-Netz erreichbar machen |

Die vollständige MediaMTX-Konfiguration stammt aus der gewählten Version; deren
Werte bleiben mit Ausnahme der dokumentierten Monitor-Anpassungen maßgeblich.

## Kurzer Funktionstest

```bash
systemctl is-active mediamtx mediamtx-api mediamtx-collector mediamtx-system
curl -fsS http://127.0.0.1:9997/v3/info | python3 -m json.tool
curl -fsS http://127.0.0.1:9997/v3/paths/list | python3 -m json.tool
curl -fsS http://127.0.0.1:8080/api/streams | python3 -m json.tool
```

Dashboard: `http://<server-ip>:8080/`

## Entwicklung und Tests

Die wichtigsten Bereiche des Repositories sind:

| Pfad | Inhalt |
|---|---|
| `bin/` | Collector, API, Systemerfassung und Backend-Hilfsmodule |
| `static/` | Vanilla-JavaScript-Dashboard und CSS |
| `config/` | Laufzeitkonfiguration und Installationsausschnitt für Preview |
| `systemd/` | Units für MediaMTX und die Monitoring-Dienste |
| `tests/` | Python-Unit-Tests und JavaScript-Renderer-Test |
| `devtools/` | kontrolliertes Deployment in die Entwicklungsinstallation |

Gemeinsamer lokaler Prüfpfad:

```bash
./devtools/verify.sh
```

## Dokumentation

- [Architektur und schrittweises Zielbild](docs/ARCHITECTURE.md)
- [Coding- und Dokumentationsstandard](docs/CODING_STYLE.md)
- [MediaMTX-v1.21+-Datenmodell](docs/MEDIAMTX_V1_21_DATA.md)
- [Betrieb und Troubleshooting](docs/TROUBLESHOOTING.md)
- [Entwicklungs-Deployment](devtools/README.md)

## Lizenz

MediaMTX Monitor steht unter der [MIT-Lizenz](LICENSE).
