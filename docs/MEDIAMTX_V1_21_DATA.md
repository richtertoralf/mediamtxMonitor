# MediaMTX-v1.21+-Datenmodell

Der Monitor unterstützt MediaMTX ab v1.21.0. Grundlage ist die offizielle
[Control-API-Definition für v1.21.0](https://github.com/bluenviron/mediamtx/blob/v1.21.0/api/openapi.yaml).
Der Collector fragt `/v3/info` in jedem Erfassungszyklus direkt ab. `version`
und `started` sind die einzige Quelle für die beobachteten Servermetadaten und
werden unabhängig von vorhandenen Streams als Redis-Sidecars gespeichert. Bei
einer älteren oder unlesbaren Version werden keine Streamdaten übernommen.

Für Stream-, Verbindungs- und Transportmonitoring verarbeitet der Monitor
ausschließlich Daten, die MediaMTX selbst über seine APIs beziehungsweise seine
protokollspezifischen Statistiken bereitstellt, oder klar definierte Ableitungen
dieser MediaMTX-Daten. Er führt keine unabhängigen Direktmessungen gegen
Publisher, Reader, Encoder oder andere Feldgeräte aus. Die fachlichen
Begründungen dieser Grenze stehen in `docs/ARCHITECTURE.md`.

## MediaMTX-Datenoberflächen

MediaMTX v1.21.0 stellt mehrere voneinander getrennte Diagnose- und
Telemetrieoberflächen bereit:

- **Control API:** Sie ist mit `api` separat zu aktivieren, standardmäßig
  deaktiviert und unter `apiAddress: :9997` konfiguriert. Der
  mediamtxMonitor benötigt diese Schnittstelle und verwendet sie ausschließlich
  lesend für die unten beschriebenen Stream-, Connection- und Transportdaten.
  Die Control API selbst besitzt darüber hinaus auch schreibende Operationen.
- **Metrics:** Der ebenfalls standardmäßig deaktivierte Schalter `metrics`
  aktiviert unter `metricsAddress: :9998` einen separaten
  Prometheus-kompatiblen Endpunkt. Er enthält teilweise dieselben oder
  zusätzliche protokollspezifische MediaMTX-Telemetriedaten. Der aktuelle
  mediamtxMonitor konsumiert ihn nicht; der folgende aktuelle Datenfluss basiert
  auf der Control API.
- **pprof:** `pprof` ist standardmäßig deaktiviert; `pprofAddress` ist
  standardmäßig `:9999`. Der Endpunkt dient der Prozess- und
  Performance-Diagnose und wird vom mediamtxMonitor nicht als Stream- oder
  Connection-Metrikquelle verwendet.
- **Logging:** MediaMTX-Logs dienen der Betriebs- und Fehlerdiagnose. Der
  aktuelle Monitor parst sie nicht als primäre Stream- oder
  Transportmetrikquelle.

Parameter wie `writeQueueSize`, `udpReadBufferSize` und `udpMaxPayloadSize`
sind MediaMTX-Konfiguration und keine vom Monitor erfassten Transportmetriken.

## Paths und Zuordnung

`/v3/paths/list` liefert die Zuordnung von Source und Readern zu ihren
protokollspezifischen IDs. Der Collector übernimmt `tracks2` vollständig und
erzeugt daraus zusätzlich die bisher von der Oberfläche erwartete kompakte
Codec-Liste `tracks`. Außerdem erfasst er `inboundBytes`, `outboundBytes` und
`inboundFramesInError`; die geprüfte Version steht als `mediamtxVersion` im
Path-Modell. Die deprecated Felder `tracks`, `bytesReceived` und
`bytesSent` des Path-Objekts werden nicht mehr gelesen. Für den Preview-Entscheid
ist `available` maßgeblich; `online` bleibt ein davon getrennter Zustand. Das
deprecated Feld `ready` wird nicht verwendet.

Die Details werden über folgende Listen aufgelöst:

| Protokoll | Path-Typ | Control-API | Bereits erfasste v1.21+-Daten |
|---|---|---|---|
| SRT | `srtConn` | `/v3/srt/conns/list` | vollständiges Detailobjekt, native Empfangs-/Senderate, Transport-RTT, native SRT-Zähler |
| RTMP | `rtmpConn` | `/v3/rtmp/conns/list` | vollständiges Detailobjekt, unter anderem `state`, `path`, `remoteAddr`, `userAgent`, `inboundBytes`, `outboundBytes` und `outboundFramesDiscarded` |
| RTMPS | `rtmpsConn` | `/v3/rtmps/conns/list` | wie RTMP, getrennt nach sicherem Listener |
| RTSP | `rtspSession` | `/v3/rtsp/sessions/list` | Session, Bytes sowie RTP-/RTCP-Zähler, Verlust, Fehler und Jitter |
| RTSPS | `rtspsSession` | `/v3/rtsps/sessions/list` | wie RTSP, getrennt nach sicherem Listener |
| WebRTC / WHIP | `webRTCSession` | `/v3/webrtc/sessions/list` | Session, Bytes, RTP-/RTCP-Zähler, Verlust, Jitter, ICE-Kandidaten, PeerConnection-Status und verworfene Ausgangsframes |
| HLS Reader | `hlsSession` | `/v3/hls/sessions/list` | Reader-Session, Remote-Adresse, User-Agent, CDN-Kennung und `outboundBytes` |
| MoQ | `moqSession` | `/v3/moq/sessions/list` | Session, Zustand, Version, Transport, Remote-Adresse sowie ein-/ausgehende Bytes |

Die Detailobjekte werden im normalisierten Snapshot unter `details` übernommen.
Das bedeutet nicht automatisch, dass der Browser jedes enthaltene Feld bereits
protokollspezifisch darstellt.

Das WebRTC-Sessionobjekt enthält im v1.21.0-Schema insbesondere
`inboundRTPPackets`, `inboundRTPPacketsJitter`, `inboundRTPPacketsLost`,
`inboundRTCPPackets`, `outboundRTPPackets`, `outboundRTCPPackets`,
`outboundFramesDiscarded`, `localCandidate`, `remoteCandidate`, `state` und
`peerConnectionEstablished`. Diese Rohdetails können im Snapshot vorhanden
sein; das aktuelle Dashboard wertet WebRTC trotzdem überwiegend nur generisch
aus und visualisiert die tieferen Felder nicht vollständig.

Neben den vom Monitor verwendeten HLS-Sessions stellt MediaMTX mit
`GET /v3/hls/muxers/list` eigene HLS-Muxer-Telemetrie bereit. Ein HLS-Sessionobjekt
enthält unter anderem `outboundBytes`, `remoteAddr`, `userAgent` und `isCDN`.
Ein HLS-Muxerobjekt enthält `created`, `lastRequest`, `outboundBytes`,
`outboundFramesDiscarded` und `path`. Der Collector lädt diesen Endpunkt,
sobald eine aktive `hlsSession` referenziert wird, und ordnet Muxer
ausschließlich über das native Feld `path` zu. Muxer-Discard wird reset-sicher
in 10-s-/60-s-Fenstern geführt und bleibt ausdrücklich ein Muxer-/Path-Wert,
kein individueller Browserverlust. User-Agent und CDN-Kennung aus HLS-Sessions
bleiben Teil der Darstellung.

RTSP- und RTSPS-RTP-/RTCP-Daten stammen ausdrücklich aus den Session-Endpunkten.
Die zusätzlich möglichen Reader-Typen `rtspConn` und `rtspsConn` werden über
ihre Connection-Listen aufgelöst. Deren Verbindungsobjekte dienen jedoch nicht
als Ersatz für die RTP-/RTCP-Zähler der Session-Objekte.

## Aktueller Umfang in Snapshot und Dashboard

- **SRT:** Der Snapshot enthält die detaillierten nativen Transportwerte und
  daraus gebildete Kurzzeitmetriken einschließlich RTT-p50, p95 und Variation.
  Das Dashboard zeigt RTT, TSBPD-Latenz, Loss, Retransmissions, Drop, Belated
  und Undecrypt sowie einen Trend für aktuelle RTT und Variation; p50 und p95
  werden nicht separat ausgegeben. Es stellt außerdem die RTT-/Latenz-Beziehung
  dar und klassifiziert SRT-Ereignisfenster aktuell als `OK`, `WARN`, `CRIT`
  oder `RECENT`.
- **RTMP/RTMPS:** Dashboard und Snapshot führen Rate, Bytes und Alter sowie
  einen Bitratenverlauf. Für Reader werden Frame-Discard-Fenster gebildet;
  zusätzlich existiert eine begrenzte, nur eindeutig zuordenbare
  Connection-Stability-Anzeige.
- **RTSP/RTSPS:** Session-Publisher zeigen Transport, Jitter samt Verlauf sowie
  Loss, RTP Error und RTCP Error in 10-s-/60-s-Fenstern. Session-Reader zeigen
  `Reported Loss` und Discard in denselben Fenstern. `rtspConn` und
  `rtspsConn` besitzen nicht dieselbe protokollspezifische Tiefe.
- **WebRTC:** Publisher zeigen nativen Jitter samt Verlauf, eingehenden
  RTP-Verlust, PeerConnection-Status und ICE-Candidates. Reader zeigen nur
  Ausgangs-Frame-Discard sowie Peer/ICE; Reader-RTT, -Loss oder -Jitter werden
  nicht ergänzt.
- **HLS:** Pro Session werden ein aus ihrer bestehenden Connection-History
  abgeleiteter `TX Ø10s`, Bytes, Alter, User-Agent und CDN-Kennung gezeigt. Der
  aktuelle Pollwert bleibt im Snapshot erhalten und ist im Tooltip sichtbar.
  Pathbezogene HLS-Muxerwerte erscheinen getrennt genau einmal pro OUT-Spalte;
  Last Request wird relativ angezeigt, während der native ISO-Wert im Tooltip
  und Snapshot erhalten bleibt.
- **MoQ:** Zeigt neben den gemeinsamen Richtungswerten die nativen Felder
  Transport, Version und State; RTT, Jitter oder Loss werden nicht abgeleitet.

MediaMTX kann damit mehr protokollspezifische Rohfelder bereitstellen, als die
aktuelle Weboberfläche speziell visualisiert.

Nicht-SRT-Gesamtcounter werden nur als kurzlebiger Redis-Messzustand gehalten.
Der Snapshot enthält reset-sichere Intervallwerte und die daraus über die
gemeinsame History gebildeten 10-s-/60-s-Summen. Ein Counter-Reset erzeugt
keinen negativen Wert; eine neue Connection-ID beginnt mit eigener Baseline.
SRT verwendet unverändert seinen bestehenden Health-State und seine Fenster.

## Raten, RTT und Forwarding

Bitraten werden weiterhin aus Byte-Deltas und Messzeit-Deltas berechnet und in
Redis geglättet. Bei SRT haben `mbpsReceiveRate` und `mbpsSendRate` Vorrang vor
dieser Berechnung. Die SRT-Transportzähler `bytesReceived` und `bytesSent`
bleiben dabei SRT-spezifische Felder und sind nicht mit den gleichnamigen,
deprecated Feldern anderer API-Objekte zu verwechseln.

MediaMTX beschreibt `mbpsLinkCapacity` als geschätzte Kapazität der
Netzwerkverbindung in Mbit/s. Der Monitor übernimmt diesen diagnostischen
Schätzwert als `link_capacity_mbps`; das Dashboard bezeichnet ihn als
`SRT est. Link`. Der Wert ist weder eine garantierte nutzbare Bandbreite noch
eine garantierte Reserve oder ein belastbarer Headroom-Wert.

Die von MediaMTX v1.21.0 gelieferten Felder `packetsReceivedRetrans`,
`packetsReceivedLoss`, `packetsReceivedDrop`, `packetsReceivedBelated`,
`packetsReceivedUndecrypt`, `packetsRetrans`, `packetsSendLoss` und
`packetsSendDrop` sind Gesamtzähler der jeweiligen SRT-Verbindung. Der Monitor
bildet daraus bereits reset-sichere Ereignisdeltas je Collector-Intervall. Die
Kurzzeithistorie speichert diese normalisierten Intervallwerte und summiert sie
für 10-s- und 60-s-Fenster; sie bildet nicht erneut Counter-Deltas.

MediaMTX-`msRTT` wird für SRT als `transport_rtt_ms` normalisiert. Für einen
Publisher beziehungsweise IN wird `msReceiveTsbPdDelay` als `srt_latency_ms`
übernommen; für einen Reader beziehungsweise OUT stammt `srt_latency_ms` aus
`msSendTsbPdDelay`. Andere Protokolle erhalten keine künstliche
RTT-Ersatzmetrik. SRT-`msRTT` ist eine von MediaMTX bereitgestellte
protokollnative Transportmetrik und kein Netzwerk-Ping.

Unterschiedliche Protokolle besitzen bewusst unterschiedliche
Monitoring-Metriken. Fehlende MediaMTX-Metriken bleiben fehlend und werden
weder durch ICMP noch durch direkte Abfragen von RTCP- oder libsrt-Statistiken
an Endgeräten ersetzt.

## RTMP-/RTMPS-Zeitdimension

Für RTMP- und RTMPS-Verbindungen übernimmt der Snapshot zusätzlich die bereits
in der allgemeinen Connection-History gespeicherten `rx_mbps`- beziehungsweise
`tx_mbps`-Samples als `rate_history`. Die Punkte bleiben nach
MediaMTX-Connection-ID getrennt; fehlende Raten werden als Lücken und nicht als
Nullwerte transportiert. Andere Protokolle erhalten durch diese Darstellung
keinen zusätzlichen Bitratenverlauf.

Der native RTMP-Reader-Counter `outboundFramesDiscarded` zählt Media-Einheiten,
die MediaMTX nicht in die volle Ausgangsqueue des konkreten Readers einreihen
konnte. Der Collector bildet ausschließlich innerhalb derselben Connection-ID
reset-sichere `frame_discard_delta`-Intervallwerte. Die bestehende
Kurzzeithistorie summiert diese getrennt unter
`window_metrics.frame_discard.10s` und `.60s`. Der kumulative native Wert bleibt
unverändert unter `details.outboundFramesDiscarded`; die Deltas sind weder
Packet Loss noch TCP-Retransmissionen oder ein Beweis für sichtbare Bildfehler.

Für RTMP/RTMPS wird außerdem ein kurzlebiger Lifecycle-State mit 120 Sekunden
TTL pro Path, Rolle und Protokoll geführt. Er meldet ausschließlich beobachtete
Connection-ID-Wechsel. Publisher sind pro Path eindeutig. Reader werden nur
dann einer Karte zugeordnet, wenn für denselben Remote-Host ohne ephemeren Port
genau eine Connection aktiv ist. Parallele, fehlende oder anderweitig
mehrdeutige Readergruppen erhalten keine individuelle Stability-Aussage. Ein
Collector-Neustart setzt eine neue Baseline und erzeugt keinen künstlichen
Wechsel.

Die Weboberfläche stellt für SRT das Verhältnis von aktueller Transport-RTT zur
von MediaMTX gemeldeten SRT-/TSBPD-Latenz dar. Der angezeigte Prozentwert ist
`RTT / SRT-Latenz × 100`; Tooltip und barrierefreies Label nennen zusätzlich
den inversen RTT-Multiplikator `SRT-Latenz / RTT`. Die Farbgebung bewertet nur
die Dimensionierung dieser Latenzreserve: ab `4 × RTT` grün, ab `3 × RTT` bis
unter `4 × RTT` gelb und unter `3 × RTT` rot. Sie ist keine Aussage über die
allgemeine Verbindungs- oder Stream-Gesundheit; Loss, Drop, Belated,
Retransmissionen sowie RTT-Trend und -Volatilität bleiben davon getrennte
Messwerte für eine spätere umfassende Bewertung.

Für jeden Path fragt der Collector `/v3/paths/forward-dests/list?path=<name>` ab.
Der Snapshot enthält ausschließlich die nicht sensitiven Beobachtungen `id`,
`pos`, `type`, `state`, `outboundBytes` und `created`; Konfiguration, URLs,
Credentials und Fehlertexte werden nicht an API oder Frontend weitergegeben.
Eine eigene Dashboarddarstellung ist derzeit nicht Teil des Monitors.

Die v1.21-Control-API liefert dafür unter
`/v3/paths/forward-dests/list?path=<name>` strukturierte Einträge mit `id`,
`pos`, `type`, `state`, `outboundBytes` und `created`; `conf` und das alte
`protocol` sind deprecated. MediaMTX definiert für `state` ausschließlich
`idle`, `forwarding` und `error`. Begriffe wie `reconnecting` oder `inactive`
werden deshalb nicht aus diesen Daten erfunden. Die Prometheus-Metriken
`forward_dests` und `forward_dests_outbound_bytes` sind mögliche ergänzende
Quellen, werden vom Monitor aktuell aber nicht zusätzlich abgefragt. Der
Endpunkt ist read-only. Ziel-URLs, Userinfo, Tokens, Stream-Keys und
Fehlertexte bleiben außerhalb des öffentlichen Snapshots.
