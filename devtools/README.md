# 🛠️ devtools – Hilfsskripte für Entwicklung und Deployment

Dieses Verzeichnis enthält Werkzeuge zur Synchronisation von Entwicklungsdateien mit dem produktiven Testverzeichnis von `mediamtx-monitoring-backend`.

Die Entwicklung erfolgt lokal in Visual Studio Code im Verzeichnis:

`$HOME/scripts/mediamtxmon`.

Die produktive Testumgebung liegt hingegen unter:

```
/opt/mediamtx-monitoring-backend/
```


Da auf `/opt/...` in der Regel nur mit `sudo` oder unter einem dedizierten Systemnutzer (z. B. `mediamtxmon`) geschrieben werden darf, ist ein direktes Arbeiten dort nicht praktikabel. Stattdessen dienen diese Skripte dem geregelten Holen und Zurückspielen von bearbeiteten Dateien.

---

## 📁 Dateien in diesem Verzeichnis

| Datei               | Beschreibung |
|---------------------|--------------|
| `filemap.sh`        | Zentrale Datei-Ziel-Zuordnung. Enthält eine Assoziativliste, die jeder bearbeiteten Datei ihr Zielverzeichnis im Produktivsystem zuweist. Wird von `fetch.sh` und `deploy.sh` verwendet. |
| `fetch.sh`          | Kopiert ausgewählte oder alle Dateien **aus** dem Produktivsystem nach `$HOME/scripts/mediamtxmon`, um sie lokal zu bearbeiten. |
| `deploy.sh`         | Spielt bearbeitete Dateien **zurück** ins Produktivsystem und setzt dabei Besitzer- und Ausführungsrechte korrekt. |
| `generate_filemap.sh` | Erstellt `filemap.sh` automatisch anhand des aktuellen Inhalts des Produktivverzeichnisses – unter Berücksichtigung von `.filemapignore`. |
| `.filemapignore`    | Enthält Muster (ähnlich `.gitignore`) für Dateien und Verzeichnisse, die beim Erzeugen der `filemap.sh` ausgeschlossen werden sollen. |

---

## ⚙️ Verwendung

1. In dieses Verzeichnis wechseln:

   ```bash
   cd ~/scripts/mediamtxmon/devtools


## ⚙️ Verwendung

1. In dieses Verzeichnis wechseln:

   ```bash
   cd ~/scripts/mediamtxmon/devtools
   ```

2. Datei-Zuordnung automatisch erzeugen (optional, ersetzt manuelles Pflegen von filemap.sh):

```
./generate_filemap.sh
```


3. Dateien aus dem Produktivsystem holen:
   ```
   ./fetch.sh           # Interaktive Auswahl
   ./fetch.sh --all     # Alle in filemap.sh gelisteten Dateien holen
   ```

3. Dateien ins Produktivsystem zurückspielen:
   ```
   ./deploy.sh          # Interaktive Auswahl
   ```

## 🔐 Rechte und Benutzer
Die Dateien im Produktivsystem gehören dem Nutzer mediamtxmon.

deploy.sh übernimmt daher automatisch:

- Kopieren mit sudo
- Setzen des Besitzers mit chown
- Setzen der Ausführbarkeit bei .py-Dateien mit chmod +x

📌 Hinweise
filemap.sh bildet die Grundlage für beide Skripte. Sie kann manuell gepflegt oder mit generate_filemap.sh automatisch erzeugt werden.

.filemapignore funktioniert ähnlich wie .gitignore und erlaubt das Ausschließen unerwünschter Dateien und Verzeichnisse.

Das Setup ist besonders nützlich bei eingeschränkten Rechten auf /opt/..., z. B. in Multi-User- oder Produktivumgebungen.

Die Skripte sind modular aufgebaut und können bei Bedarf um Funktionen wie Logging, Dry-Run oder Dateivergleich erweitert werden.

## 🧪 Beispielhafte Zielstruktur im Produktivsystem
```
/opt/mediamtx-monitoring-backend/
├── bin/            ← Python-Skripte
│   ├── mediamtx_collector.py
│   └── mediamtx_api.py
├── config/         ← YAML-Konfigurationen
│   └── collector.yaml
├── static/         ← Web-Assets (HTML, CSS, JS, Bilder)
│   ├── index.html
│   ├── js/
│   └── css/
└── venv/           ← (ausgeschlossen)

```
