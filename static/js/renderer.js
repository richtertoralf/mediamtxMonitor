/**
 * 🧩 Rendert ein einzelnes Reader-Objekt als HTML-Block
 * @param {Object} reader - Reader-Objekt mit Typ, ID und Details
 * @returns {string} - HTML-Block mit Reader-Informationen
 */

function formatBytes(bytes) {
  if (!bytes || isNaN(bytes)) return "–";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return bytes.toFixed(4) + " " + units[i];
}

export function renderReader(reader) {
  const markerClass = {
    srtConn: "marker-srt",
    rtmpConn: "marker-rtmp",
    hlsMuxer: "marker-hls",
    webRTCSession: "marker-webrtc",
  }[reader.type] || "";

  const remote = reader.details?.remoteAddr || "-";
  const rateApi = reader.details?.mbpsSendRate || 0;
  const rateCalc = reader.bitrate_mbps || 0;
  const bytes = reader.details?.bytesSent || 0;

  // Finaler Wert: API bevorzugt, sonst berechnet
  const finalRate = rateApi > 0 ? rateApi : rateCalc;

  let html = `
    <div class="reader-block">
      <span class="${markerClass}"></span>Typ: ${reader.type}<br/>
      Remote: ${remote}<br/>
      Rate: ${finalRate.toFixed(2)} Mbps<br/>
      Gesendet: ${formatBytes(bytes)}
  `;

  if (reader.type === "hlsMuxer" && reader.details?.lastRequest) {
    html += ` (letzter Abruf: ${new Date(reader.details.lastRequest).toLocaleTimeString()})`;
  }

  html += "</div>";
  return html;
}

/**
 * 🧱 Erzeugt den linken Block einer Streamkarte (Publisher-Info)
 * @param {Object} stream - Streamdaten
 * @returns {string} - HTML-Block
 */
function renderStreamLeft(stream) {
  return `
    <div class="stream-left">
      <div class="stream-title">${stream.name}</div>
      Publisher (${stream.source?.type || "-"})<br/>
      Remote: ${stream.source?.details?.remoteAddr || "-"}<br/>
      RTT: ${stream.source?.details?.msRTT?.toFixed(2) || "0"} ms<br/>
      Rate: ${stream.source?.details?.mbpsReceiveRate?.toFixed(2) || "0"} Mbps<br/>
      Empfangen: ${formatBytes(stream.source?.details?.bytesReceived) || "–"}<br/>
Tracks: ${stream.tracks?.join(", ") || "-"}<br/>
    </div>
  `;
}

/**
 * 🧱 Rendert eine vollständige Streamkarte mit Publisher, Snapshot & Readers
 * @param {Object} stream - Aggregiertes Stream-Objekt mit source, tracks, readers etc.
 * @returns {HTMLDivElement} - DOM-Element für die Streamkarte
 */
export function renderStreamCard(stream, snapshotIntervalMs = 5000) {
  const readersSorted = [...stream.readers || []].sort((a, b) => {
    const order = { srtConn: 1, rtmpConn: 2, hlsMuxer: 3, webRTCSession: 4 };
    return (order[a.type] || 99) - (order[b.type] || 99);
  });

  const div = document.createElement("div");
  div.className = "stream-card";

  const left = renderStreamLeft(stream);

  const center = `
    <div class="stream-center">
      <img class="snapshot-image" src="/static/snapshots/${stream.name}.jpg?ts=${Date.now()}" alt="Snapshot: ${stream.name}">
    </div>
  `;

  const right = `
    <div class="stream-right">
      <span class="label">Readers (${readersSorted.length}):</span>
      ${readersSorted.map(renderReader).join("")}
    </div>
  `;

  div.innerHTML = left + center + right;

  const snapshot = div.querySelector(".stream-center img");
  setInterval(() => {
    snapshot.src = `/static/snapshots/${stream.name}.jpg?ts=${Date.now()}`;
  }, snapshotIntervalMs);

  return div;
}

/**
 * 🔁 Aktualisiert eine bestehende Streamkarte im DOM
 * @param {HTMLDivElement} card - DOM-Element der Streamkarte
 * @param {Object} stream - Aktuelle Streamdaten
 */
export function updateStreamCard(card, stream) {
  const left = card.querySelector(".stream-left");
  const right = card.querySelector(".stream-right");

  left.innerHTML = renderStreamLeft(stream);

  const readersSorted = [...stream.readers || []].sort((a, b) => {
    const order = { srtConn: 1, rtmpConn: 2, hlsMuxer: 3, webRTCSession: 4 };
    return (order[a.type] || 99) - (order[b.type] || 99);
  });

  right.innerHTML = `
    <span class="label">Readers (${readersSorted.length}):</span>
    ${readersSorted.map(renderReader).join("")}
  `;
}
