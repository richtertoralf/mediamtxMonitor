# Arbeitsregeln für Codex

## Projekt

Dieses Repository enthält den MediaMTX Monitor von Richter Projects.

Das Gesamtsystem besteht aus drei getrennten Ebenen:

1. Git-Repository:
   ~/src/mediamtxMonitor

2. Installierte Monitoring-Anwendung:
   /opt/mediamtx-monitoring-backend

3. Externe MediaMTX-Installation:
   /usr/local/bin/mediamtx
   /usr/local/etc/mediamtx.yml
   /etc/systemd/system/mediamtx.service

## Technische Leitlinien

- Bestehende Funktionen müssen erhalten bleiben.
- Das Frontend bleibt vorerst Vanilla JavaScript.
- Keine Umstellung auf React.
- Keine festen IP-Adressen oder Hostnamen im Anwendungscode.
- Produktions- und Entwicklungsbetrieb müssen klar getrennt werden.
- Absolute Pfade müssen dokumentiert oder konfigurierbar sein.
- MediaMTX, Redis, FastAPI, FFmpeg und systemd sind getrennte Komponenten.
- Repository-Dateien und installierte Laufzeitdateien dürfen nicht verwechselt werden.

## Sicherheit

- Keine sudo-Befehle ohne ausdrückliche Freigabe.
- Keine Firewalländerungen.
- Keine öffentlichen Ports öffnen.
- Keine Änderungen unter /opt, /usr/local oder /etc ohne ausdrückliche Freigabe.
- Keine Streamkeys, Passwörter oder Tokens anzeigen oder committen.

## Arbeitsweise

- Zuerst Bestand und Zusammenhänge analysieren.
- Vor Änderungen einen konkreten Plan vorlegen.
- Änderungen klein und nachvollziehbar halten.
- Nach jeder Änderung passende Tests ausführen.
- Dokumentation erst nach verifizierten Codeänderungen aktualisieren.
- Keine bestehenden Dateien ungefragt vollständig neu schreiben.
