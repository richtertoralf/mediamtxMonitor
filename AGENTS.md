# Arbeitsregeln für Codex

## Projekt

Dieses Repository enthält den MediaMTX Monitor von Richter Projects.

Das System besteht aus drei getrennten Ebenen:

1. Git-Repository:
   `~/mediamtxMonitor`

2. Installierte und laufende Monitoring-Anwendung:
   `/opt/mediamtx-monitoring-backend`

3. Externe MediaMTX-Installation:
   - `/usr/local/bin/mediamtx`
   - `/usr/local/etc/mediamtx.yml`
   - `/etc/systemd/system/mediamtx.service`

Das Git-Repository ist die Source of Truth.

Codeänderungen erfolgen ausschließlich im Git-Repository.
Die Dateien unter `/opt/mediamtx-monitoring-backend` sind die laufende
Installation und werden nicht direkt bearbeitet.

## Entwicklungsworkflow

Codex arbeitet im Repository:

`~/mediamtxMonitor`

VS Code verwendet ebenfalls dieses Repository.

Für einen manuellen Integrationstest im Browser wird der aktuelle
Repository-Stand mit

`./devtools/deploy-dev.sh`

nach `/opt/mediamtx-monitoring-backend` übertragen.

Der normale Ablauf ist:

1. Bestand analysieren.
2. Änderung im Repository durchführen.
3. passende Tests ausführen.
4. `git diff` prüfen.
5. mit `deploy-dev.sh --dry-run` die deploybaren Änderungen prüfen.
6. nach ausdrücklicher Freigabe das echte Deployment mit `deploy-dev.sh`
   ausführen.
7. Änderung in der laufenden Anwendung bzw. im Browser prüfen.
8. erst danach gegebenenfalls committen.

`install.sh` ist ausschließlich für die frische Neuinstallation einer VM
gedacht. Es ist weder für Updates einer bestehenden Installation noch für den
normalen Entwicklungszyklus vorgesehen.

## Technische Leitlinien

- Bestehende Funktionen müssen erhalten bleiben.
- Das Frontend bleibt vorerst Vanilla JavaScript.
- Keine Umstellung auf React oder ein anderes Frontend-Framework.
- Keine festen IP-Adressen oder Hostnamen im Anwendungscode.
- Absolute Pfade müssen dokumentiert oder konfigurierbar sein.
- MediaMTX, Redis, FastAPI, FFmpeg und systemd sind getrennte Komponenten.
- Repository-Dateien und installierte Laufzeitdateien nicht verwechseln.
- Bestehende Architektur und vorhandene Werkzeuge bevorzugen.
- Keine unnötigen neuen Dienste, Frameworks oder Abhängigkeiten einführen.

### Verbindliche Architektur- und Coding-Dokumentation

Vor Änderungen sind die Regeln aus `docs/ARCHITECTURE.md` und
`docs/CODING_STYLE.md` zu beachten. Wenn bestehender Code noch nicht dem dort
beschriebenen Zielbild entspricht, ist das kein Auftrag für einen automatischen
Großrefactor. Änderungen bleiben klein, kompatibel, testbar und schrittweise
deploybar.

## Sicherheit und Systemgrenzen

Innerhalb von `~/mediamtxMonitor` darf Codex selbstständig:

- Dateien lesen und analysieren,
- Dateien ändern,
- vorhandene Tests und Prüfungen ausführen,
- Git-Status und Git-Diffs anzeigen.

Ohne ausdrückliche Freigabe:

- keine `sudo`-Befehle,
- keine Firewalländerungen,
- keine öffentlichen Ports oder Bindings öffnen,
- keine Änderungen unter `/usr/local` oder `/etc`,
- keine Änderungen an der MediaMTX-Installation,
- keine systemd-Units installieren oder verändern,
- keine Dateien direkt unter `/opt/mediamtx-monitoring-backend` bearbeiten,
- keine Streamkeys, Passwörter, Tokens oder andere Secrets anzeigen oder committen.

### Dev-Deployment

`devtools/deploy-dev.sh` ist der vorgesehene Weg, Änderungen aus dem
Repository in die laufende Entwicklungsinstallation zu übertragen.

Der reine Vergleich mit `./devtools/deploy-dev.sh --dry-run` darf ohne
zusätzliche Freigabe ausgeführt werden und verändert keine Dateien.

Das echte Deployment mit `./devtools/deploy-dev.sh` darf nur nach
ausdrücklicher Freigabe ausgeführt werden, da es:

- Dateien unter `/opt/mediamtx-monitoring-backend` aktualisiert,
- `sudo` verwendet,
- bei Backend- oder Konfigurationsänderungen Monitoring-Dienste neu startet.

Direkte Änderungen unter `/opt` anstelle dieses Deployments sind nicht zulässig.

### Installations- und MediaMTX-Konfiguration

`config/monitor-preview-path.yml` ist keine Laufzeitdatei der Monitoring-Anwendung
unter `/opt`.

Sie wird von `install.sh` verwendet, um aus der MediaMTX-Standardkonfiguration
die installierte `/usr/local/etc/mediamtx.yml` zu erzeugen.

`devtools/deploy-dev.sh` deployt deshalb nur:

- `bin/`
- `static/`
- `config/collector.yaml`

Änderungen an `requirements.txt`, `config/monitor-preview-path.yml`, `systemd/`,
`install.sh` oder `uninstall.sh` werden nicht über `deploy-dev.sh` ausgerollt.
Sie müssen separat geprüft und ausdrücklich installiert werden.

Insbesondere erfordern Änderungen an `requirements.txt` eine separate,
ausdrücklich freizugebende Aktualisierung der Python-vEnv unter
`/opt/mediamtx-monitoring-backend/venv`.

## Git

- Bestehende Änderungen des Benutzers nicht überschreiben oder zurücksetzen.
- Keine Branches ohne konkreten Grund anlegen oder wechseln.
- Keine Commits ohne ausdrücklichen Auftrag.
- Kein Push ohne ausdrücklichen Auftrag.
- Vor einem Commit immer `git status` und `git diff` prüfen.
- Keine generierten Dateien, Secrets oder unbeabsichtigten Änderungen committen.

## Arbeitsweise

- Immer zuerst den relevanten Bestand und die Zusammenhänge analysieren.
- Einfache Änderungen direkt durchführen.
- Bei größeren oder nicht-trivialen Änderungen kurz den geplanten Weg nennen
  und anschließend arbeiten.
- Für normale Änderungen innerhalb des Repositories nicht auf zusätzliche
  Freigabe warten.
- Änderungen klein, praktisch und nachvollziehbar halten.
- Immer die einfachste ausreichend robuste Lösung bevorzugen.
- Keine Architektur für hypothetische zukünftige Anforderungen bauen.
- Keine unnötigen Abstraktionen oder Generalisierungen einführen.
- Frameworks vermeiden, wenn die Aufgabe mit vorhandenen Bordmitteln
  übersichtlich lösbar ist.
- Neue Runtime-Abhängigkeiten nur einführen, wenn sie einen klaren praktischen
  Vorteil bringen.
- Bestehende Dateien nicht ohne Not vollständig neu schreiben.
- Kommentare nur dort ergänzen, wo sie den Grund für eine nicht offensichtliche
  Lösung erklären.

## Tests

Nach Änderungen die zur betroffenen Komponente passenden vorhandenen Tests
oder Prüfungen ausführen.

Vorhandene Test- und Lint-Konfigurationen verwenden.

Falls kein automatischer Test vorhanden ist:

- Python-Code mindestens auf Syntaxfehler prüfen,
- JavaScript nach Möglichkeit auf Syntaxfehler prüfen,
- die unmittelbar betroffene Funktion soweit möglich lokal prüfen.

Fehlgeschlagene oder nicht mögliche Tests ausdrücklich nennen.

Tests niemals nur deshalb verändern oder abschwächen, damit sie erfolgreich
durchlaufen.

## Abschluss einer Änderung

Kurz zusammenfassen:

- was geändert wurde,
- welche Dateien betroffen sind,
- welche Tests ausgeführt wurden,
- ob ein Dev-Deployment durchgeführt wurde,
- welche offenen Punkte oder Risiken bestehen.

Dokumentation erst nach verifizierten Codeänderungen aktualisieren.
