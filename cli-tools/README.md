# cli-tools

Diagnosewerkzeuge, die direkt gegen die MediaMTX-API sprechen (`curl` + `jq`),
unabhängig vom Monitor-Stack (Collector, Redis, FastAPI, Web-Dashboard).

Das ist bewusst so: Die Skripte funktionieren auch dann noch, wenn der
Monitor-Stack selbst gestört ist oder gerade nicht läuft. Sie dienen als
Fallback-Diagnose ("lebt die MediaMTX-API überhaupt und liefert sie
plausible Daten?") und für schnellen SSH-only-Zugriff ohne Browser
(ursprünglich für die Nutzung z. B. via Termux auf dem Smartphone gedacht).

Für den laufenden Betrieb mit Historie, Aggregation und grafischer Aufbereitung
ist das Web-Dashboard des Monitors die primäre Oberfläche; diese Skripte
ersetzen es nicht, sondern ergänzen es für den Fall, dass der Stack selbst
die Fehlerursache ist.

| Skript | Zweck |
| --- | --- |
| `mediamtx_paths.sh` | Aktive Streams, hochkant/kompakt (Smartphone/Termux via SSH) |
| `showActivePaths_table.sh` | Aktive Streams als Tabelle |
| `srt-data_table.sh` | Live-Refresh (2s) aktiver SRT-Publish-Verbindungen mit `msRTT`, Recv-Rate, Link-Capacity |
