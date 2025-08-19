/**
 * renderer.js – Render-Funktionen für Streamkarten (Publisher + Readers)
 *
 * - Zeigt links die Publisher-Infos inkl. Rate:
 *   bevorzugt API-Wert (z. B. SRT mbpsReceiveRate), sonst berechnete Bitrate
 *   aus dem Collector (stream.source.bitrate_mbps).
 * - Zeigt rechts die Reader inkl. Rate:
 *   bevorzugt API-Wert (mbpsSendRate), sonst berechnete Bitrate reader.bitrate_mbps.
 *
 * Hinweis:
 * Die berechneten Bitraten stammen aus dem Backend (Collector) via bitrate.py.
 * Dieses Frontend macht keine eigene Delta-Berechnung.
 */

/**
 * Formatiert Bytes in eine lesbare Einheit.
 * @param {number} bytes - Bytewert (kumuliert)
 * @returns {string} Formatierter String, z. B. "12.3 MB"
 */
function formatBytes(bytes) {
  if (bytes == null || isNaN(bytes)) return "–";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let val = Number(bytes);
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(4)} ${units[i]}`;
}

/**
 * Rendert einen einzelnen Reader-Block (rechte Spalte).
 * @param {Object} reader - Reader-Objekt mit Typ, ID und Details
 * @returns {string} HTML-Fragment
 */
export function renderReader(reader) {
  const markerClass = {
    srtConn: "marker-srt",
    rtmpConn: "marker-rtmp",
    hlsMuxer: "marker-hls",
    webRTCSession: "marker-webrtc",
  }[reader.type] || "";

  const remote = reader?.details?.remoteAddr || "-";
  const rateApi = Number(reader?.details?.mbpsSendRate) || 0;
  const rateCalc = Number(reader?.bitrate_mbps) || 0;

  // Finaler Wert: API bevorzugt, sonst berechnet.
  const finalRate = rateApi > 0 ? rateApi : rateCalc;

  const bytesSent = Number(reader?.details?.bytesSent) || 0;

  let html = `
    <div class="reader-block">
      <span class="${markerClass}"></span>Typ: ${reader.type}<br/>
      Remote: ${remote}<br/>
      Rate: ${finalRate > 0 ? finalRate.toFixed(2) : "0.00"} Mbps<br/>
      Gesendet: ${formatBytes(bytesSent)}
  `;

  // HLS: optional letzter Abrufzeitpunkt zeigen.
  if (reader.type === "hlsMuxer" && reader?.details?.lastRequest) {
    const ts = new Date(reader.details.lastRequest);
    html += ` (letzter Abruf: ${isNaN(ts.getTime()) ? reader.details.lastRequest : ts.toLocaleTimeString()})`;
  }

  html += "</div>";
  return html;
}

/**
 * Rendert den linken Block (Publisher/Ingest) einer Streamkarte.
 * @param {Object} stream - Aggregierte Streamdaten
 * @returns {string} HTML-Fragment
 */
function renderStreamLeft(stream) {
  const src = stream?.source || {};
  const details = src.details || {};

  // API-Rate (SRT) bevorzugen, sonst berechnete Rate aus dem Collector.
  const apiRate = Number(details.mbpsReceiveRate) || 0;
  const calcRate = Number(src.bitrate_mbps) || 0;
  const finalRate = apiRate > 0 ? apiRate : calcRate;

  // RTT abgesichert formatieren.
  const rtt = details.msRTT != null && !isNaN(Number(details.msRTT))
    ? Number(details.msRTT).toFixed(2)
    : "0";

  // Empfangen: bevorzugt Detailzähler, fallback auf Path-Feld.
  const bytesRx = details.bytesReceived != null
    ? Number(details.bytesReceived)
    : Number(stream.bytesReceived || 0);

  return `
    <div class="stream-left">
      <div class="stream-title">${stream.name}</div>
      Publisher (${src.type || "-"})<br/>
      Remote: ${details.remoteAddr || "-"}<br/>
      RTT: ${rtt} ms<br/>
      Rate: ${finalRate > 0 ? finalRate.toFixed(2) : "0.00"} Mbps<br/>
      Empfangen: ${formatBytes(bytesRx)}<br/>
      Tracks: ${Array.isArray(stream.tracks) && stream.tracks.length ? stream.tracks.join(", ") : "-"}<br/>
    </div>
  `;
}

/**
 * Rendert eine komplette Streamkarte (links Publisher, Mitte Snapshot, rechts Readers).
 * @param {Object} stream - Aggregiertes Stream-Objekt mit source, tracks, readers etc.
 * @param {number} [snapshotIntervalMs=5000] - Reload-Intervall für das Snapshot-Bild
 * @returns {HTMLDivElement} DOM-Element der Streamkarte
 */
export function renderStreamCard(stream, snapshotIntervalMs = 5000) {
  // Readers typisiert sortieren: SRT → RTMP → HLS → WebRTC.
  const readersSorted = [...(stream.readers || [])].sort((a, b) => {
    const order = { srtConn: 1, rtmpConn: 2, hlsMuxer: 3, webRTCSession: 4 };
    return (order[a.type] || 99) - (order[b.type] || 99);
  });

  const div = document.createElement("div");
  div.className = "stream-card";

  const left = renderStreamLeft(stream);

  const center = `
    <div class="stream-center">
      <img
        class="snapshot-image"
        src="/static/snapshots/${stream.name}.jpg?ts=${Date.now()}"
        alt="Snapshot: ${stream.name}"
      >
    </div>
  `;

  const right = `
    <div class="stream-right">
      <span class="label">Readers (${readersSorted.length}):</span>
      ${readersSorted.map(renderReader).join("")}
    </div>
  `;

  div.innerHTML = left + center + right;

  // Snapshot periodisch aktualisieren, Cache-Busting via Timestamp.
  const snapshot = div.querySelector(".stream-center img");
  if (snapshot) {
    setInterval(() => {
      snapshot.src = `/static/snapshots/${stream.name}.jpg?ts=${Date.now()}`;
    }, snapshotIntervalMs);
  }

  return div;
}

/**
 * Aktualisiert eine bestehende Streamkarte im DOM (ohne komplettes Re-Rendern).
 * @param {HTMLDivElement} card - Root-Element der Streamkarte
 * @param {Object} stream - Aktuelle Streamdaten
 */
export function updateStreamCard(card, stream) {
  const left = card.querySelector(".stream-left");
  const right = card.querySelector(".stream-right");

  if (left) {
    left.innerHTML = renderStreamLeft(stream);
  }

  // Leser erneut sortieren und rendern.
  const readersSorted = [...(stream.readers || [])].sort((a, b) => {
    const order = { srtConn: 1, rtmpConn: 2, hlsMuxer: 3, webRTCSession: 4 };
    return (order[a.type] || 99) - (order[b.type] || 99);
  });

  if (right) {
    right.innerHTML = `
      <span class="label">Readers (${readersSorted.length}):</span>
      ${readersSorted.map(renderReader).join("")}
    `;
  }
}
