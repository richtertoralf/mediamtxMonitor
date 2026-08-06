# MediaMTX Monitor

MediaMTX Monitor zeigt aktive MediaMTX-Streams, Publisher, Reader, Bitraten,
SRT-Metriken und Systemdaten in einem kleinen Web-Dashboard. Das Frontend bleibt
Vanilla JavaScript. Redis puffert die vom Collector gelesenen Daten, FastAPI
liefert API und Dashboard aus.

## Dienste

MediaMTX und der Monitor laufen auf derselben Maschine als getrennte
systemd-Dienste. Ein Fehler des Monitor-Dashboards soll den laufenden
Streamingdienst nicht beenden.

| Komponente | Betrieb |
|---|---|
| MediaMTX | unabhängiger Dienst `mediamtx.service`, systemd-Standardbenutzer `root` |
| MediaMTX-Monitor | drei Dienste unter `mediamtxmon:mediamtxmon` |

Ein Ausfall von MediaMTX beendet den Collector nicht. Der Collector meldet dann
API-Fehler und fragt weiter. Umgekehrt beeinflusst ein Monitor-Ausfall den
MediaMTX-Streamingdienst auf derselben Maschine nicht.

## Unterstützte Neuinstallationen

- Ubuntu Server 24.04 LTS
- `x86_64` / `amd64`
- `aarch64` / `arm64`
- Raspberry Pi 4 mit 64-Bit-Ubuntu Server

Der Installer unterstützt nur frische Systeme. Existierende oder angepasste
Installationen werden nicht überschrieben oder aktualisiert.

## Installation

```bash
sudo ./install.sh 1.20.0
```

MediaMTX v1.20.0 wurde auf der bestehenden Entwicklungsinstallation erfolgreich
mit dem Monitor getestet. Der vollständige Neuinstaller wird anschließend auf
einer frischen Ubuntu-24.04-VM geprüft. Die gewünschte MediaMTX-Version wird vom
Benutzer gewählt; ein optionales führendes `v` ist erlaubt. Der Installer sucht
nicht automatisch nach der neuesten Version.

Der Installer lädt Binary und vollständige `mediamtx.yml` aus demselben
offiziellen Release-Archiv und prüft dessen SHA-256-Summe. Er aktiviert API,
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

## Dienste und Benutzer

| Dienst | Benutzer | Aufgabe |
|---|---|---|
| `mediamtx.service` | root (kein `User=` in der Unit) | Streamingserver |
| `mediamtx-api.service` | `mediamtxmon` | Dashboard und Monitor-API |
| `mediamtx-collector.service` | `mediamtxmon` | MediaMTX-Control-API abfragen |
| `mediamtx-system.service` | `mediamtxmon` | Systemmetriken erfassen |
| `redis-server.service` | Distributionseinstellung | Zwischenspeicher |

## Ports

Für die mit MediaMTX v1.20.0 getestete Konfiguration:

| Port | Funktion |
|---:|---|
| 8554 | RTSP |
| 1935 | RTMP |
| 8888 | HLS |
| 8889 | WebRTC und Monitor-Vorschau |
| 8890 | SRT |
| 9997 | MediaMTX-Control-API |
| 8080 | Dashboard und Monitor-API |
| 6379 | Redis, lokal |

Die vollständige MediaMTX-Konfiguration stammt aus der gewählten Version; deren
Werte bleiben mit Ausnahme der dokumentierten Monitor-Anpassungen maßgeblich.

## Kurzer Funktionstest

```bash
systemctl is-active mediamtx mediamtx-api mediamtx-collector mediamtx-system
curl -fsS http://127.0.0.1:9997/v3/paths/list | python3 -m json.tool
curl -fsS http://127.0.0.1:8080/api/streams | python3 -m json.tool
```

Dashboard: `http://<server-ip>:8080/`

Weitere Prüfungen und Fehlerbilder stehen in
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
