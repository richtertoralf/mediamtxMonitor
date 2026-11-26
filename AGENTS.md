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

- Neue Komponenten, Dienste, Abstraktionsschichten oder Abhängigkeiten nur einführen, wenn ein konkreter Nutzen sie rechtfertigt.
- Betriebs-, Wartungs- und Fehlersuchaufwand gehören zu den technischen Kosten. Lösungen müssen für ein kleines beziehungsweise ein Einmann-Team nachvollziehbar und wartbar bleiben.
- Nicht vorsorglich für hypothetische Anforderungen oder Skalierung bauen.

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

## Gemeinsame Regeln

Gemeinsam beschlossene Regeln der Produktfamilie. **Heute** beschreibt den
vorhandenen Stand, **Ziel** eine beschlossene, noch offene Umsetzung mit
Issue. Ein Ziel ist kein Auftrag, es nebenbei oder im Vorgriff umzusetzen.

- Zuständigkeit: Der Monitor stellt MediaMTX und, auf MediaMTX-Hosts, Redis
  bereit (Installation und globale Basiskonfiguration). Uninstall und Purge
  entfernen beide nie. Ziel: ein vorhandenes Redis nicht aktualisieren (#40).
- Monitoring liest MediaMTX über die Control API. Pfadabschnitte anderer
  Anwendungen in der MediaMTX-Konfiguration bleiben unangetastet.
- Verwaltung heute: `mediamtx-monitor --version | --status | --upgrade |
  --check-config [DATEI]`; Deinstallation mit `sudo ./uninstall.sh` in einer
  Stufe. Kein `--source`. Ziel (#33, #34): `--help`, `--check` als Alias,
  `--uninstall` erhält die Konfiguration, `--uninstall --purge` nach
  Bestätigung; Rückgabecodes 0 in Ordnung, 1 technischer Fehler, 2 ungültige
  Parameter oder Konfiguration, gestoppte Units sind kein Fehler.
- Releases: Bei einem beauftragten Release erhält der `main`-Commit einen
  unveränderlichen Tag `vX.Y.Z` und ein GitHub Release; nicht jeder Commit ist
  ein Release. Versionsquelle und Badge ändern sich im selben Commit.
  `--upgrade` darf weiterhin neue Commits des vorgesehenen Branches
  übernehmen; `--version` nennt Version und Commit.
- Oberfläche heute: gemeinsame Token-Datei, LIVE nur mit Nachweis. Ziel:
  Umschalter Hell/Dunkel.
- Zugang: Ziel ist eine Anmeldung für interaktive Oberflächen; lesende
  Schnittstellen ohne Geheimnisse und ohne Nebenwirkungen.
  Konten nach dem Standard „Lokale Benutzerkonten“; keine Sitzungs-, Rollen-
  oder Kopplungsverfahren auf Vorrat.
- Python: Unterstützt werden Ubuntu 24.04 LTS mit Python 3.12 und Ubuntu 26.04
  LTS mit Python 3.14; andere Versionen werden nicht eigens unterstützt oder
  getestet. Nichts verwenden, was erst nach 3.12 eingeführt wurde, außer
  ausdrücklich begründet. Bewährte, einfache Lösungen, möglichst wenige
  Abhängigkeiten, keine experimentellen Frameworks. Die Funktion wird für
  beide Zielplattformen nachgewiesen, vorzugsweise auf eigener Infrastruktur;
  GitHub Actions ist keine Pflicht, keine weiteren Versionsmatrizen, keine
  Mehrfachläufe nur wegen verschiedener GitHub-Ereignisse. Installer und
  Upgrader prüfen die Python-Kompatibilität und verwalten die venv; die
  System-Python-Version ersetzen sie nicht. Gilt für jede Änderung;
  Bestehendes wird nicht allein deswegen umgebaut. Heute abweichend:
  Installation zusätzlich auf Raspberry Pi OS (64 Bit) dokumentiert; Nachweis
  für Ubuntu 26.04 mit Python 3.14 steht aus.
- Tests heute: die Python-Unit-Tests und der JavaScript-Renderer-Test unter
  `tests/` (Befehl noch nicht dokumentiert). Der Prüfbefehl läuft vor dem
  Merge vollständig lokal; das Ergebnis steht im PR. Ein Nachweis für Ubuntu
  26.04 mit Python 3.14 erfolgt vor Release und Feldeinsatz.
- Neue technische Bezeichner englisch; vorhandene deutsche Bezeichner nur in
  getesteten Überarbeitungen umbenennen, keine Massenumbenennung.
- Ausgabe, Ziel: Unveränderte Eingangsdaten und wiederholte Zustandsmeldungen
  unterbrechen keine laufende Grafik oder Anzeige und bauen sie nicht neu
  auf. Vorgesehene Wechsel, Zeitsteuerungen und die Wiederherstellung nach
  einer Unterbrechung bleiben zulässig; ein Regressionstest sichert das.
- Einfachheit: die kleinste robuste Lösung, nichts auf Vorrat. Keine zweite
  Implementierung derselben Funktion und kein Sonderweg je Sportart, Marke
  oder Quelle, wo ein allgemeiner Mechanismus reicht. Vor einer größeren
  Erweiterung früh und produktübergreifend klären: fachliches Ziel,
  wiederverwendbare Mechanismen, einfachere Lösung, unvermeidbare
  Komplexität, was dadurch entfallen kann.

## Dokumentationsregel

Dokumentation ist Teil jeder Änderung und beschreibt den Stand des Branches,
auf dem sie liegt.

- Jede verbindliche Aussage hat einen Ort; andere Stellen verweisen darauf.
  Einen Inhalt erst durch einen Verweis ersetzen, wenn er am Zielort
  vollständig dokumentiert ist. Überholte Aussagen ersetzen oder entfernen;
  gültige Informationen nicht ohne fachlichen Grund entfernen.
- **Vor jedem Commit:** betroffene Dokumentation im selben Commit
  nachführen. Ist keine betroffen, entsteht keine künstliche Änderung.
- **Vor jedem Merge:** Umsetzung gegen die betroffene Dokumentation und die
  geltenden Regeln prüfen; Folgen für andere Repositories und gemeinsame
  Schnittstellen nennen; Roadmap (`docs/PRIORITAETEN.md`) und Aufgabenstatus
  auf den tatsächlichen Stand bringen.
- **Vor jedem Release:** Installation, Konfiguration, Schnittstellen,
  Bedienung und bekannte Einschränkungen gegen den Release-Stand abgleichen.
  Nichts Erledigtes steht als offen, nichts Ungeprüftes als abgenommen. Der
  Release-PR nennt, was fachlich hinzukam, und den Umfang seit dem letzten
  Release (`git diff --shortstat <letzter Tag>..HEAD`).
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

## README

Die README ist die öffentliche Einstiegsseite für Anwender, Interessenten und
Mitwirkende; Vertiefendes steht in `docs/`.

- Nutzen vor technischen Details. Gliederung und Überschriften passend zum
  Produkt wählen.
- Nur tatsächlich vorhandene Funktionen und Befehle als verfügbar
  beschreiben; Erprobtes und Geplantes getrennt kennzeichnen.
- Einen Entwicklungsstatus nur nennen, wenn er nachvollziehbar belegt ist:
  **Konzept** (keine nutzbare Implementierung), **In Entwicklung**
  (begonnen, eventuell noch nicht installierbar; nennen, was funktioniert und
  wie man es ausprobiert), **Im Praxistest** (bei mindestens einem realen
  Einsatz betreut erprobt, datierter Beleg in `docs/`), **Im Einsatz**
  (wiederholt produktiv genutzt, Beleg in `docs/`), **Archiviert**. Fehlen
  Belege, die Aussage weglassen; Installations- und Upgradeprüfungen belegen
  keinen Praxiseinsatz.
- Nur verifizierte Informationen aufnehmen: Aussagen zuerst an Code und
  Dokumentation prüfen; was sich nicht bestätigen lässt, weglassen. Fehlende
  Dokumentation ist kein Beleg für eine fehlende Funktion.
- Einschränkungen nur nennen, wenn sie nachgewiesen und für Anwender relevant
  sind; keine vermuteten Risiken, vorsorglichen Warnhinweise oder künstlich
  offenen Fragen. Lieber kürzer und sachlich richtig als ausführlich mit
  Annahmen.
- Alles Notwendige steht in diesem Repository. Nicht auf nicht öffentliche
  Repositories als notwendige Quelle verweisen.
- Der Leitgedanke von RICHTER.PROJECTS, „Möglichkeiten schaffen.“, ist
  erkennbar, in eigenen Worten passend zum Produkt.
- Natürliches, sachliches Deutsch ohne Werbe- und Füllformeln; vorhandene
  Bilder und Beispiele erhalten.

## Verifikation und Abschluss

- Der kanonische Entwicklungs-, Verifikations- und Dev-Deployment-Workflow
  steht in `devtools/README.md` und wird von dort befolgt.
- Im Abschlussbericht wahrheitsgemäß nennen, welche Aktionen und Prüfungen
  ausgeführt wurden, welche nicht ausgeführt wurden oder fehlgeschlagen sind
  und welche Risiken verbleiben.
