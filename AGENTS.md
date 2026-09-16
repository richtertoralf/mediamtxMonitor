# Arbeitsregeln für Coding-Agenten

Diese Datei ist die einzige allgemeine Arbeitsanweisung für Coding-Agenten in
diesem Repository. Fachliche und technische Projektregeln stehen in der
Projektdokumentation und werden hier nicht wiederholt.

## Projekt und Navigation

Dieses Repository enthält den MediaMTX Monitor von Richter Projects. Das
Git-Repository ist die Source of Truth.

Die jeweils zuständige Grundlage vor einer Änderung lesen:

- `README.md`: Überblick, Repository-Landkarte, Installation und Betrieb
- `docs/ARCHITECTURE.md`: verbindliche Architekturgrenzen, Datenfluss und
  fachliche Invarianten; vor Änderungen an Architektur, Datenfluss oder
  Metriksemantik zwingend lesen
- `docs/CODING_STYLE.md`: Coding- und Dokumentationskonventionen
- `docs/MEDIAMTX_V1_21_DATA.md`: tatsächlich verfügbare MediaMTX-Rohdaten
- `docs/TROUBLESHOOTING.md`: Betrieb und Fehlersuche
- `devtools/README.md`: Entwicklungs-, Verifikations- und
  Dev-Deployment-Workflow

## Arbeitsweise

- Vor einer Änderung die fachlich zuständige Dokumentation lesen und ihre
  Vorgaben einhalten.
- Änderungen klein, nachvollziehbar, kompatibel und einzeln prüfbar halten.
- Bestehende Struktur, Muster und Abstraktionen bevorzugen; keine neue Schicht,
  Abhängigkeit oder Framework ohne konkreten, begründeten Nutzen.
- Bestehende Benutzeränderungen und Secrets schützen.
- Unklarheiten und erkannte Folgeaufgaben benennen, statt sie nebenbei
  umzusetzen.

## Auftragsgrenze

- Nur den erteilten Auftrag umsetzen; größere Verbesserungen als Folgeauftrag
  dokumentieren.
- Im Repository dürfen Dateien analysiert und geändert sowie Tests, Git-Diffs
  und die Verifikation ausgeführt werden.
- Ohne ausdrückliche Freigabe nicht: `sudo` verwenden, Dateien außerhalb des
  Repositories ändern, Systemdienste oder externe Komponenten anpassen, ein
  Deployment ausführen, Abhängigkeiten installieren sowie committen, pushen
  oder den Branch wechseln.
- Ohne ausdrücklichen Auftrag verwenden Tests und Prüfungen Fakes oder
  temporäre Ressourcen und verändern keine laufende Umgebung. Ausdrücklich
  beauftragte Integrations- oder Runtime-Tests bleiben davon unberührt.

## Dokumentationsregel

- Unnötige Duplikation zwischen Dokumentations- und Instruktionsquellen
  vermeiden. Technische Wahrheit kann je nach Sachverhalt auch in Code, Tests
  oder Konfiguration liegen.
- Geändertes Verhalten, geänderte Verträge und geänderte Workflows werden in
  der zuständigen bestehenden Datei nachgeführt, nicht in dieser Datei
  dupliziert.
- Keine agentenspezifischen Kopien von Projekt-, Verifikations- oder
  Deploymentregeln und keine agentenspezifischen Skill- oder
  Instruktionsverzeichnisse anlegen.
- `CLAUDE.md` verweist ausschließlich auf diese Datei.

## Verifikation und Abschluss

- Der kanonische Entwicklungs-, Verifikations- und Dev-Deployment-Workflow
  steht in `devtools/README.md` und wird von dort befolgt.
- Im Abschlussbericht wahrheitsgemäß nennen, welche Aktionen und Prüfungen
  ausgeführt wurden, welche nicht ausgeführt wurden oder fehlgeschlagen sind
  und welche Risiken verbleiben.
