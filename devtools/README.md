# devtools – Dev-Deployment

Dieses Verzeichnis enthält Hilfsskripte für die Entwicklung des MediaMTX Monitor.

## verify.sh

Der gemeinsame mechanische Prüfpfad für lokale Änderungen ist:

```bash
./devtools/verify.sh
```

Die Verifikation führt kein Deployment aus. Der Deployment-Vergleich und das
echte Deployment bleiben davon getrennte Schritte.

Für die JavaScript-Renderer-Tests benötigt `verify.sh` das Kommando `node` und
damit eine lokale Node.js-Installation. Die Tests verwenden `node` direkt;
`npm` ist dafür nicht erforderlich. Node.js ist keine Laufzeitabhängigkeit des
produktiven MediaMTX Monitor: Eine normale Produktionsinstallation verwendet
die ausgelieferten statischen Frontend-Dateien und benötigt dafür kein Node.js.

## Prinzip

Entwicklung und Versionskontrolle erfolgen im Git-Repository:

```text
~/mediamtxMonitor
```

Die laufende Entwicklungsinstallation liegt unter:

```text
/opt/mediamtx-monitoring-backend
```

Das Git-Repository ist die **Source of Truth**. Dateien unter `/opt` werden nicht direkt bearbeitet.

```text
Codex / VS Code
      ↓
~/mediamtxMonitor
      ↓
deploy-dev.sh
      ↓
/opt/mediamtx-monitoring-backend
      ↓
Browser
```

## deploy-dev.sh

Änderungen zunächst nur anzeigen:

```bash
./devtools/deploy-dev.sh --dry-run
```

Dieser reine Vergleich verändert keine Dateien und darf ohne zusätzliche
Freigabe ausgeführt werden.

Änderungen nach ausdrücklicher Freigabe deployen:

```bash
./devtools/deploy-dev.sh
```

Übertragen werden:

```text
bin/                  → /opt/mediamtx-monitoring-backend/bin/
static/               → /opt/mediamtx-monitoring-backend/static/
config/collector.yaml → /opt/mediamtx-monitoring-backend/config/collector.yaml
VERSION               → /opt/mediamtx-monitoring-backend/VERSION
systemd/mediamtx-api.service       → /etc/systemd/system/mediamtx-api.service
systemd/mediamtx-collector.service → /etc/systemd/system/mediamtx-collector.service
systemd/mediamtx-system.service    → /etc/systemd/system/mediamtx-system.service
```

`__pycache__/` und `*.pyc` werden ignoriert.

Die drei projekt-eigenen Monitor-Units werden nur bei inhaltlichen Abweichungen
installiert. Danach lädt das Skript systemd genau einmal neu. Bei Änderungen an
Backend, `collector.yaml` oder einer Monitor-Unit werden die Monitoring-Dienste
neu gestartet. Bei reinen Frontend-Änderungen genügt anschließend ein
Browser-Reload. `mediamtx.service` und die MediaMTX-Konfiguration werden vom
Dev-Deployment nicht verwaltet.

## Nicht Teil des Dev-Deployments

Diese Dateien werden bewusst nicht über `deploy-dev.sh` ausgerollt:

```text
config/monitor-preview-path.yml
requirements.txt
install.sh
uninstall.sh
```

`config/monitor-preview-path.yml` wird nur von `install.sh` verwendet, um die MediaMTX-Konfiguration unter `/usr/local/etc/mediamtx.yml` zu erzeugen.

Änderungen an `requirements.txt` erfordern eine separate, ausdrücklich
freizugebende Aktualisierung der Python-vEnv unter
`/opt/mediamtx-monitoring-backend/venv`.

## Frische Neuinstallation einer Dev-VM

`install.sh` ist ausschließlich für eine frische VM vorgesehen. Das Skript ist
nicht zum Aktualisieren einer bestehenden Installation gedacht und bricht ab,
wenn relevante Installationsziele bereits vorhanden sind.

```bash
git clone <repository> ~/mediamtxMonitor
cd ~/mediamtxMonitor
sudo ./install.sh 1.20.0
```

Danach sollte:

```bash
./devtools/deploy-dev.sh --dry-run
```

melden:

```text
Keine deploybaren Änderungen gefunden.
```

## Aktueller Inhalt

```text
devtools/
├── README.md
├── deploy-dev.sh
└── verify.sh
```
