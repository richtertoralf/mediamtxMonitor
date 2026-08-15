---
name: dev-deploy
description: Prüft oder deployt den Repository-Stand kontrolliert in die laufende Entwicklungsinstallation.
---

# Dev-Deployment

Das Git-Repository ist die Source of Truth. Dateien unter
`/opt/mediamtx-monitoring-backend` niemals direkt bearbeiten.

1. Lies `devtools/README.md` und prüfe die Änderung mit dem Skill
   `verify-change`.
2. `./devtools/deploy-dev.sh --dry-run` darf ohne zusätzliche Freigabe als
   rein lesender Vergleich ausgeführt werden.
3. Führe `./devtools/deploy-dev.sh` nur nach ausdrücklicher Freigabe aus. Das
   Skript verwendet `sudo`, schreibt unter `/opt` und kann Dienste neu starten.
4. Prüfe danach die laufende Anwendung beziehungsweise den Browser und berichte
   das Ergebnis.

`install.sh` ist kein Update- oder Entwicklungswerkzeug. Dateien außerhalb des
Deploy-Umfangs von `devtools/deploy-dev.sh` benötigen einen separaten,
ausdrücklich freizugebenden Installationsschritt.
