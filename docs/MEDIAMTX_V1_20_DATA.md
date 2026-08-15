# MediaMTX-v1.20-Datenmodell

Der Monitor unterstützt MediaMTX ab v1.20.0. Grundlage ist die offizielle
[Control-API-Definition für v1.20.0](https://github.com/bluenviron/mediamtx/blob/v1.20.0/api/openapi.yaml).
Der Collector fragt `/v3/info` beim ersten Erfassungszyklus und danach
periodisch erneut ab. Das Intervall wird mit
`collector.version_refresh_seconds` konfiguriert und beträgt standardmäßig
60 Sekunden. Zwischen diesen Abfragen verwendet er die zuletzt erfolgreich
erkannte Version. Bei einer älteren oder unlesbaren Version werden keine
weiteren v1.20-Abfragen ausgeführt und die bisherige Redis-Messung wird nicht
überschrieben.

## Paths und Zuordnung

`/v3/paths/list` liefert die Zuordnung von Source und Readern zu ihren
protokollspezifischen IDs. Der Collector übernimmt `tracks2` vollständig und
erzeugt daraus zusätzlich die bisher von der Oberfläche erwartete kompakte
Codec-Liste `tracks`. Außerdem erfasst er `inboundBytes`, `outboundBytes` und
`inboundFramesInError`; die geprüfte Version steht als `mediamtxVersion` im
Path-Modell. Die deprecated Felder `tracks`, `bytesReceived` und
`bytesSent` des Path-Objekts werden nicht mehr gelesen.

Die Details werden über folgende Listen aufgelöst:

| Protokoll | Path-Typ | Control-API | Bereits erfasste v1.20-Daten |
|---|---|---|---|
| SRT | `srtConn` | `/v3/srtconns/list` | vollständiges Detailobjekt, native Empfangs-/Senderate, Transport-RTT, native SRT-Zähler |
| RTMP | `rtmpConn` | `/v3/rtmpconns/list` | vollständiges Detailobjekt, `inboundBytes`, `outboundBytes`, verworfene Ausgangsframes |
| RTMPS | `rtmpsConn` | `/v3/rtmpsconns/list` | wie RTMP, getrennt nach sicherem Listener |
| RTSP | `rtspSession` | `/v3/rtspsessions/list` | Session, Bytes sowie RTP-/RTCP-Zähler, Verlust, Fehler und Jitter |
| RTSPS | `rtspsSession` | `/v3/rtspssessions/list` | wie RTSP, getrennt nach sicherem Listener |
| WebRTC / WHIP | `webRTCSession` | `/v3/webrtcsessions/list` | Session, Bytes, RTP-/RTCP-Zähler, Verlust, Jitter, ICE-Kandidaten und verworfene Ausgangsframes |
| HLS Reader | `hlsSession` | `/v3/hlssessions/list` | Reader-Session, Remote-Adresse, User-Agent, CDN-Kennung und `outboundBytes` |
| MoQ | `moqSession` | `/v3/moqsessions/list` | Session, Zustand, Version, Transport, Remote-Adresse sowie ein-/ausgehende Bytes |

RTSP- und RTSPS-Health-Daten stammen ausdrücklich aus den Session-Endpunkten.
Die zusätzlich möglichen Reader-Typen `rtspConn` und `rtspsConn` werden über
ihre Connection-Listen aufgelöst. Deren Verbindungsobjekte dienen jedoch nicht
als Ersatz für die RTP-Health-Zähler der Session-Objekte.

## Raten, RTT und Forwarding

Bitraten werden weiterhin aus Byte-Deltas und Messzeit-Deltas berechnet und in
Redis geglättet. Bei SRT haben `mbpsReceiveRate` und `mbpsSendRate` Vorrang vor
dieser Berechnung. Die SRT-Transportzähler `bytesReceived` und `bytesSent`
bleiben dabei SRT-spezifische Felder und sind nicht mit den gleichnamigen,
deprecated Feldern anderer API-Objekte zu verwechseln.

Die von MediaMTX v1.20.0 gelieferten Felder `packetsReceivedRetrans`,
`packetsReceivedLoss`, `packetsReceivedDrop`, `packetsReceivedBelated`,
`packetsReceivedUndecrypt`, `packetsRetrans`, `packetsSendLoss` und
`packetsSendDrop` sind Gesamtzähler der jeweiligen SRT-Verbindung. Der Monitor
bildet daraus bereits reset-sichere Ereignisdeltas je Collector-Intervall. Die
Kurzzeithistorie speichert diese normalisierten Intervallwerte und summiert sie
für 10-s- und 60-s-Fenster; sie bildet nicht erneut Counter-Deltas.

Nur SRT liefert derzeit mit `msRTT` eine echte Transport-RTT für die
Hauptanzeige. Die bestehende ICMP-Messung für andere Publisher bleibt erhalten,
wird im internen Source-Modell jedoch separat als `icmp_rtt_ms` gespeichert.
SRT wird zusätzlich als `transport_rtt_ms` normalisiert.

Die Weboberfläche stellt für SRT das Verhältnis von aktueller Transport-RTT zur
konfigurierten SRT-/TSBPD-Latenz dar. Der angezeigte Prozentwert ist
`RTT / SRT-Latenz × 100`; Tooltip und barrierefreies Label nennen zusätzlich
den inversen RTT-Multiplikator `SRT-Latenz / RTT`. Die Farbgebung bewertet nur
die Dimensionierung dieser Latenzreserve: ab `4 × RTT` grün, ab `3 × RTT` bis
unter `4 × RTT` gelb und unter `3 × RTT` rot. Sie ist keine Aussage über die
allgemeine Verbindungs- oder Stream-Gesundheit; Loss, Drop, Belated,
Retransmissionen sowie RTT-Trend und -Volatilität bleiben davon getrennte
Messwerte für eine spätere umfassende Bewertung.

Für jeden Path fragt der Collector `/v3/paths/forward/list?path=<name>` ab und
stellt die nativen Ziele unverändert als `forwardDestinations` bereit. Dazu
gehören Konfiguration, Protokoll, Zustand, Erstellzeit, letzter Fehler und
`outboundBytes`. Eine eigene UI für diese Daten ist in diesem Schritt nicht
vorgesehen.
