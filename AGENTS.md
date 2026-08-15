# Arbeitsregeln für Coding-Agenten

## Projekt und verbindliche Dokumente

Dieses Repository enthält den MediaMTX Monitor von Richter Projects. Es erfasst
und visualisiert Stream-, Connection-, Transport- und Systemmetriken eines
MediaMTX-Nodes.

Vor Änderungen die jeweils relevanten Grundlagen lesen:

- `docs/ARCHITECTURE.md`: Systemarchitektur, Datenfluss, fachliche
  Interpretation und Invarianten; vor Änderungen an Metriksemantik, Datenfluss
  oder Architektur zwingend lesen.
- `docs/CODING_STYLE.md`: Coding- und Dokumentationskonventionen.
- `docs/MEDIAMTX_V1_20_DATA.md`: von MediaMTX v1.20 tatsächlich bereitgestellte
  Rohdaten, Felder und Metriken.
- `.agents/skills/verify-change/SKILL.md`: fachliche Änderungsprüfung und
  gemeinsamer mechanischer Prüfpfad.
- `.agents/skills/dev-deploy/SKILL.md`: getrennt freizugebender Dev-Deployment-
  Workflow.

## Repository-Landkarte

- `bin/`: Python-Backend, Collector, API und Systemerfassung
- `static/`: Vanilla-JavaScript-Dashboard und CSS
- `tests/`: Python-Unittests und JavaScript-Renderer-Tests
- `config/`: Laufzeitkonfiguration und Installationsausschnitt
- `systemd/`: Service-Units
- `cli-tools/`: Diagnosewerkzeuge
- `docs/`: Architektur-, Coding-, Daten- und Betriebsdokumentation
- `devtools/`: Verifikation und kontrolliertes Dev-Deployment

Das Git-Repository ist die Source of Truth. Die laufende Installation unter
`/opt/mediamtx-monitoring-backend` und die externe MediaMTX-Installation unter
`/usr/local` beziehungsweise `/etc` sind davon getrennt und werden nicht direkt
bearbeitet.

## Unverletzbare Architekturregeln

- MediaMTX ist die fachliche Grenze für Stream-, Connection- und
  Transportmonitoring. Metriken stammen ausschließlich aus Daten, die MediaMTX
  selbst über seine APIs beziehungsweise seine protokollspezifischen
  Statistiken bereitstellt, oder aus klar definierten Ableitungen dieser
  MediaMTX-Daten.
- Der Monitor führt keine unabhängigen Messungen gegen Publisher, Reader oder
  andere Feldgeräte durch, um fehlende MediaMTX-Metriken zu ersetzen oder zu
  ergänzen.
- Protokollspezifische Unterschiede sind beabsichtigt. Fehlende native
  Protokollmetriken bleiben fehlend; keine Ersatzmetriken aus fachlich
  unabhängigen Messquellen erfinden.
- Externer ICMP-Ping gehört nicht zum Stream-Monitoring. SRT-`msRTT`
  beziehungsweise `transport_rtt_ms` ist eine protokollnative, von MediaMTX
  bereitgestellte Transportmetrik, kein generischer Netzwerk-Ping.
- Bestehende Architektur und Abstraktionen bevorzugen. Keine neue Struktur,
  Schicht, Abhängigkeit oder Framework einführen, wenn der Bestand ausreicht;
  kein pauschaler Umbau nach `src/`.
- MediaMTX, Redis, FastAPI, FFmpeg, systemd und Monitoring-Anwendung bleiben
  getrennte Komponenten. Dashboard und Monitor-API bleiben read-only.
- Das Frontend bleibt Vanilla JavaScript. Bestehende Funktionen und Verträge
  bleiben erhalten.

Details und Begründungen sind verbindlich in `docs/ARCHITECTURE.md` beschrieben
und werden hier nicht dupliziert.

## Sicherheit und Freigaben

Im Repository dürfen Dateien analysiert und geändert sowie Tests, Git-Diffs und
`./devtools/verify.sh` ausgeführt werden. Bestehende Benutzeränderungen und
Secrets sind zu schützen.

Ohne ausdrückliche Freigabe gelten insbesondere:

- kein `sudo`, keine Firewall-, Port-, `/usr/local`-, `/etc`-, MediaMTX- oder
  systemd-Änderung;
- keine direkte Änderung unter `/opt/mediamtx-monitoring-backend`;
- kein echtes `./devtools/deploy-dev.sh` und keine separate Installation von
  Abhängigkeiten oder nicht deploybaren Konfigurationsdateien;
- kein Commit, Push oder Branchwechsel.

`./devtools/deploy-dev.sh --dry-run` ist ein erlaubter, rein lesender Vergleich.
`install.sh` dient ausschließlich einer frischen VM-Installation und nicht dem
Entwicklungsworkflow.

## Änderungsabschluss

Für jede Änderung den Skill `verify-change` verwenden. Er trennt die fachliche
Diff-Prüfung von den mechanischen Prüfungen in `./devtools/verify.sh`. Nicht
ausgeführte oder fehlgeschlagene Prüfungen und ein nicht erfolgtes Deployment im
Abschlussbericht transparent nennen.
