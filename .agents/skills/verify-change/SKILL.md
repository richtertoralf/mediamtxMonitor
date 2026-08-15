---
name: verify-change
description: Prüft Repository-Änderungen fachlich und führt den gemeinsamen mechanischen Prüfpfad aus.
---

# Änderung verifizieren

Dieser Skill bewertet eine Änderung fachlich. Die mechanischen Prüfkommandos
sind in `./devtools/verify.sh` zentralisiert.

1. Lies den vollständigen relevanten Diff und ordne jede Änderung ihrem Zweck
   zu. Prüfe, dass keine unbeabsichtigten Produkt-, Konfigurations- oder
   Deploymentänderungen enthalten sind.
2. Prüfe die verbindlichen Invarianten aus `docs/ARCHITECTURE.md`. Lies das
   Dokument vor Änderungen an Metriksemantik, Datenfluss oder Architektur.
3. Verfolge bei neuen oder geänderten Stream-, Connection- oder
   Transportmetriken die Datenquelle bis zu den Daten, die MediaMTX selbst über
   seine APIs beziehungsweise protokollspezifischen Statistiken bereitstellt,
   oder bis zu einer klar definierten Ableitung dieser MediaMTX-Daten. Erfinde
   für nicht vorhandene Protokollmetriken keine Ersatzmessung und akzeptiere
   keine unabhängigen Messungen gegen Publisher, Reader oder andere Feldgeräte.
4. Prüfe bei Redis-Änderungen Producer und Consumer gemeinsam, einschließlich
   Key-Schema, TTL, Snapshot-/Messzustand und Connection-Lifecycle.
5. Prüfe bei Änderungen an API-, Snapshot- oder Frontend-Verträgen Backend und
   Renderer gemeinsam. Berücksichtige Regressionen, Reconnects, Disconnects
   und die Trennung von Current State und History.
6. Führe `./devtools/verify.sh` aus.
7. Prüfe danach den vollständigen `git diff` sowie `git status --short`.
8. Nenne nicht ausgeführte, übersprungene oder fehlgeschlagene Prüfungen und
   verbleibende Risiken transparent. Ein erfolgreicher mechanischer Lauf
   ersetzt nicht die fachliche Bewertung.

Dieser Skill führt kein Deployment, keinen Commit und keinen Push aus.
