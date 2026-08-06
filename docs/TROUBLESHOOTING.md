# Troubleshooting

Die folgenden Prüfungen verändern keine Konfiguration. Befehle mit `sudo` sind
nur für Status und Logs vorgesehen.

## Dienststatus

```bash
systemctl is-active mediamtx
systemctl is-active redis-server
systemctl is-active mediamtx-api
systemctl is-active mediamtx-collector
systemctl is-active mediamtx-system
```

MediaMTX und Monitor laufen auf derselben Maschine als getrennte systemd-Dienste:
`mediamtx.service` ist der Streamingserver, die drei Monitor-Dienste laufen als
`mediamtxmon`. Ein MediaMTX-Ausfall darf den Collector nicht beenden; dessen Daten
bleiben währenddessen leer oder veraltet. Ein Monitor-Ausfall unterbricht
vorhandene MediaMTX-Streams auf dieser Maschine nicht.

## Journal-Logs

```bash
sudo journalctl -u mediamtx -n 100 --no-pager
sudo journalctl -u mediamtx-api -n 100 --no-pager
sudo journalctl -u mediamtx-collector -n 100 --no-pager
sudo journalctl -u mediamtx-system -n 100 --no-pager
sudo journalctl -u redis-server -n 100 --no-pager
```

Live verfolgen:

```bash
sudo journalctl -u mediamtx-collector -f
```

## Offene Ports

```bash
sudo ss -lntup | grep -E ':8554|:1935|:8888|:8889|:8890|:9997|:8080|:6379'
```

Bei MediaMTX v1.20.0 wurden RTSP 8554, RTMP 1935, HLS 8888, WebRTC
8889, SRT 8890 und Control API 9997 bestätigt. Port 8080 gehört zum Monitor.

## Control API

```bash
curl -fsS http://127.0.0.1:9997/v3/paths/list | python3 -m json.tool
```

Ein Verbindungsfehler betrifft MediaMTX oder dessen Konfiguration. Der Collector
kann trotzdem aktiv bleiben und den Verbindungsversuch wiederholen.

## Redis

```bash
redis-cli -h 127.0.0.1 -p 6379 PING
```

Erwartet wird `PONG`. Bei Redis-Ausfall können die drei Monitor-Dienste aufgrund
ihrer erforderlichen Redis-Abhängigkeit ausfallen; MediaMTX bleibt unabhängig.

## Monitor-API

```bash
curl -fsS http://127.0.0.1:8080/api/streams | python3 -m json.tool
```

Eine leere Streamliste bei erreichbarer API kann bedeuten, dass MediaMTX nicht
läuft, die Control API nicht erreichbar ist oder aktuell kein Stream publiziert.

## RTSP-Teststream

Dieser Test erzeugt lokal ein synthetisches Bild. Mit `Ctrl-C` beenden:

```bash
ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=25 \
  -c:v libx264 -tune zerolatency -f rtsp \
  rtsp://127.0.0.1:8554/rtsp-test
```

Danach muss `rtsp-test` in `/v3/paths/list` erscheinen.

## SRT-Test

Dieser lokale Test wird ebenfalls mit `Ctrl-C` beendet:

```bash
ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=25 \
  -c:v libx264 -f mpegts \
  'srt://127.0.0.1:8890?streamid=publish:srt-test'
```

Danach muss `srt-test` in `/v3/paths/list` erscheinen. Bei einem externen
Encoder müssen Zielport und MediaMTX-Stream-ID entsprechend gesetzt sein.

## Vorschaufehler

Die Vorschau verwendet WebRTC auf Port 8889. Beim Öffnen erzeugt MediaMTX den
Pfad `__preview__/<stream>` und startet FFmpeg on demand. Prüfen:

```bash
sudo ss -lntup | grep ':8889'
command -v ffmpeg
ffmpeg -hide_banner -encoders 2>/dev/null | grep libx264
sudo journalctl -u mediamtx -n 100 --no-pager
```

Der Originalstream muss per lokalem RTSP erreichbar sein. Firewall-, NAT- oder
ICE-Probleme können die Browser-Vorschau verhindern, obwohl die Control API läuft.

## `auto.crt: permission denied`

Dieser Fehler weist in diesem Projekt auf eine falsche MediaMTX-Unit hin, die
`User=mediamtxmon` oder eine andere eingeschränkte Identität enthält. Die
getestete `mediamtx.service` enthält kein `User=` und kein `Group=`; MediaMTX
läuft damit als systemd-Standardbenutzer root. Die Monitor-Dienste bleiben davon
getrennt und laufen weiterhin als `mediamtxmon`.
