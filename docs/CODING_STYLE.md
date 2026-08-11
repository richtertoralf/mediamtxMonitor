# Coding- und Dokumentationsstandard

Dieses Dokument ist die verbindliche Stilgrundlage für neue und wesentlich
geänderte Teile des MediaMTX Monitor. Bestehender Code wird nicht allein zur
Stilangleichung großflächig geändert. Vereinheitlichungen erfolgen schrittweise
zusammen mit fachlich begründeten Änderungen.

## Allgemeine Grundsätze

- Änderungen bleiben klein, nachvollziehbar und kompatibel.
- Vorhandene Werkzeuge und Muster werden bevorzugt, sofern sie den
  Architekturregeln entsprechen.
- Keine neue Abstraktion, Abhängigkeit oder Schicht ohne konkreten Nutzen.
- I/O, Zustandszugriff und reine Transformation werden möglichst getrennt.
- Magic Strings, Protokollnamen, Pfade und Key-Schemata werden nicht global
  dupliziert.
- Neue Seiteneffekte müssen an einer klaren technischen Grenze liegen und
  testbar sein.

## Python

### Benennung

- Module, Funktionen, Methoden und Variablen: `snake_case`
- Klassen und benannte Datenmodelle: `PascalCase`
- Konstanten: `UPPER_SNAKE_CASE`
- Interne Helfer: führender Unterstrich, wenn sie nicht Teil der Modulschnittstelle
  sind
- Fachbegriffe konsistent verwenden: `node`, `stream`, `publisher`, `reader`

### Type Hints und Datenmodelle

- Neue oder wesentlich geänderte öffentliche Funktionen erhalten vollständige
  Type Hints für Parameter und Rückgabe.
- Für stabile interne Modelle sind `TypedDict` oder `dataclass` zulässig.
- Unveränderte API-Rohdaten dürfen an Adaptergrenzen als `Mapping[str, Any]`
  auftreten.
- Pydantic ist an FastAPI-Grenzen zulässig, wird aber nicht für sämtliche
  internen Modelle vorgeschrieben.
- Ein Pydantic-Modell wird nur eingeführt, wenn Validierung oder API-Schema davon
  konkret profitieren.

### Pfade und Konfiguration

- Dateipfade werden in Python mit `pathlib.Path` verarbeitet.
- Installationspfade stehen in Konfiguration, Entry Points oder
  Betriebswerkzeugen, nicht in reiner Fachlogik.
- Konfiguration wird zentral geladen und explizit an Komponenten übergeben.
- Defaults und Feldnamen werden nicht über mehrere Dienste verteilt.

### Logging

- Module verwenden `logger = logging.getLogger(__name__)`.
- `logging.basicConfig()` wird ausschließlich in ausführbaren Entry Points
  aufgerufen.
- Parameterisiertes Logging wird gegenüber vorformatierten f-Strings bevorzugt:

  ```python
  logger.warning("MediaMTX request failed for %s: %s", endpoint, exc)
  ```

- Secrets, Tokens, Streamkeys und sensible vollständige URLs werden nicht
  geloggt.
- CLI-Ausgaben und strukturierte Dienstlogs sind unterschiedliche Zwecke und
  dürfen entsprechend gestaltet werden.

### Imports und Seiteneffekte

- Imports werden in Standardbibliothek, Drittanbieter und lokale Module
  gruppiert.
- Das Importieren eines Moduls liest keine Laufzeitkonfiguration, öffnet keine
  Netzwerk- oder Redis-Verbindung und startet keinen Scheduler oder Loop.
- Dienststart, Logging-Konfiguration und technische Verdrahtung erfolgen in
  `main()`, einer App-Factory oder einem vergleichbaren Entry Point.
- Produktivcode verwendet keine `sys.path`-Manipulation als Importmechanismus.

### Konstanten, Magic Strings und Redis

- Wiederkehrende API-Endpunkte, Protokolltypen und Feldgruppen werden zentral
  benannt.
- Redis-Keys werden ausschließlich über zentrale Key-Builder erzeugt.
- Fachmodule setzen keine freien Redis-Präfixe oder -Suffixe zusammen.
- Publisher-, Reader-, Snapshot- und Messzustands-Keys bleiben unterscheidbar.
- Node-bezogener Zustand muss mit Einführung des Node-Modells eine stabile
  `node_id` enthalten.

### Funktionen, I/O und Zustand

- Eine Funktion erfüllt einen klar benennbaren Verarbeitungsschritt.
- Reine Transformationen nehmen Daten entgegen und geben Daten zurück, ohne
  Redis, HTTP, Dateisystem oder globale Variablen zu verwenden.
- I/O-Abhängigkeiten, Zeitquellen und zustandsbehaftete Stores werden soweit
  praktisch injizierbar gestaltet.
- Globaler veränderlicher Zustand ist zu vermeiden.
- Große Funktionen werden nur bei konkretem Wartungs- oder Testnutzen
  aufgeteilt, nicht nach einer starren Zeilenzahl.

### Exceptions

- Erwartete Fehler werden differenziert, beispielsweise Konfigurations-, HTTP-,
  Datenformat-, Redis- und optionale Sensorfehler.
- Keine neuen pauschalen `except Exception`-Blöcke um große
  Verarbeitungsschritte.
- Breite Fehlerbehandlung ist nur an einer bewussten Prozess- oder
  Schedulergrenze zulässig und muss ausreichend protokollieren.
- Optionale Metriken dürfen gezielt ausfallen, ohne unbemerkt fachliche Fehler zu
  verschlucken.

## Kommentare und Docstrings

Relevante neue Source-Dateien erhalten einen kurzen Dateikopf nach folgendem
Muster:

```python
"""
MediaMTX Monitor - <component>.

<short purpose>

Responsibilities:
- ...

Does not:
- ...
"""
```

Der Abschnitt `Does not` ist optional, wenn die Modulgrenze bereits eindeutig
ist. Der Dateikopf bleibt kurz und ersetzt keine Architektur- oder API-
Dokumentation.

Weitere Regeln:

- Code-Docstrings sind vorzugsweise Englisch; Projektdokumentation darf Deutsch
  bleiben.
- Kommentare erklären das Warum, Protokollbesonderheiten oder externe
  Einschränkungen.
- Offensichtlicher Code wird nicht kommentiert.
- Nicht offensichtliche öffentliche Funktionen erhalten kurze Docstrings.
- Workarounds nennen Ursache und, wenn möglich, betroffene externe Version.
- Komplexe SRT-, RTSP-, WebRTC- oder MediaMTX-Eigenheiten werden an der
  zuständigen Adaptergrenze dokumentiert.
- Große dekorative Kommentarblöcke sind kein Ersatz für Modulstruktur und
  benannte Funktionen.
- Veraltete Kommentare werden zusammen mit der betroffenen Änderung korrigiert.

Diese Vorgaben lösen keine Massenänderung bestehender Dateien aus. Dateiköpfe,
Docstrings und Kommentare werden vereinheitlicht, wenn die jeweilige Datei im
Rahmen einer begründeten Änderung bearbeitet wird.

## JavaScript

- Externe Daten aus API, MediaMTX oder Streammetadaten werden nicht ungeprüft in
  `innerHTML` eingesetzt.
- Reiner Text wird bevorzugt über `textContent` gesetzt.
- Attribute und URLs werden über geeignete DOM-APIs gesetzt und validiert bzw.
  korrekt kodiert.
- HTML-Strings sind nur für vollständig kontrollierte statische Fragmente oder
  nach sicherer Behandlung dynamischer Werte zulässig.
- Renderer formatieren und präsentieren das normalisierte API-Modell. Sie bauen
  keine Backend-Normalisierung und keine MediaMTX-Feldfallbacks neu auf.
- Gemeinsam benötigte Formatierung wird nicht zwischen Renderern dupliziert.
- DOM-Zugriff, Datenformatierung und fachliche Auswahl bleiben soweit praktisch
  getrennt testbar.
- Das Frontend bleibt Vanilla JavaScript, solange kein konkreter und freigegebener
  Grund für ein Framework besteht.

## Shell

Neue Bash-Skripte beginnen grundsätzlich mit:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

Bei bewusst benötigtem `ERR`-Trap-Verhalten ist `set -Eeuo pipefail` zulässig.
Bestehende Skripte werden bei ihrer schrittweisen Bearbeitung angeglichen.

Zusätzliche Regeln:

- Variablenexpansion wird gequotet, sofern nicht ausdrücklich Wortaufteilung
  beabsichtigt ist.
- Konstante Werte werden nach Möglichkeit mit `readonly` markiert.
- `printf` wird für vorhersagbare Ausgabe gegenüber `echo` bevorzugt.
- Benötigte externe Programme und Quelldateien werden vor Änderungen geprüft.
- Fehler werden mit verständlicher Meldung und passendem Exit Code behandelt.
- Temporäre Verzeichnisse und Dateien werden sicher, beispielsweise mit
  `mktemp`, erzeugt und über einen Trap entfernt.
- Destruktive Ziele werden vor der Operation explizit validiert und besonders
  abgesichert; ein Dry-Run oder eine Bestätigung ist bei hohem Risiko zu
  bevorzugen.
- Installations-, Deployment- und Diagnosewerkzeuge bleiben getrennt.
- `install.sh` bleibt der frischen Installation vorbehalten;
  `devtools/deploy-dev.sh` bleibt der vorgesehene Entwicklungs-Deploymentweg.
- Shell-Skripte werden mindestens mit `bash -n` und, soweit verfügbar, mit
  `shellcheck` geprüft.

## Tests

- Refactorings erhalten das bestehende Verhalten, sofern eine funktionale
  Änderung nicht ausdrücklich Teil des Auftrags ist.
- Architekturgrenzen werden nach Möglichkeit durch Unit-Tests abgesichert.
- Reine Transformationen werden ohne Redis-, HTTP-, Dateisystem- oder
  Schedulerabhängigkeit getestet.
- I/O-Abhängigkeiten werden injizierbar gestaltet und in Tests durch kleine
  Fakes oder gezielte Mocks ersetzt.
- Tests sollen öffentliche Verträge und fachliches Verhalten prüfen, nicht
  unnötig interne Implementierungsdetails festschreiben.
- Jeder Refactoring-Schritt muss einzeln testbar und deploybar bleiben.
- Tests werden nicht abgeschwächt oder entfernt, nur um eine Änderung erfolgreich
  erscheinen zu lassen.
- Nach Änderungen werden die zur betroffenen Komponente passenden vorhandenen
  Tests und Syntaxprüfungen ausgeführt. Nicht mögliche Prüfungen werden im
  Abschlussbericht genannt.

