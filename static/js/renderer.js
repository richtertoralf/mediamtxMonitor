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

function formatSampleRate(sampleRate) {
  const value = Number(sampleRate);
  if (!Number.isFinite(value) || value <= 0) return null;
  if (value >= 1000) return `${Number((value / 1000).toFixed(1))} kHz`;
  return `${value} Hz`;
}

function formatChannels(channelCount) {
  const value = Number(channelCount);
  if (!Number.isFinite(value) || value <= 0) return null;
  if (value === 1) return "Mono";
  if (value === 2) return "Stereo";
  return `${value} Kanäle`;
}

function renderMedia(stream) {
  const media = stream?.media || {};
  const lines = [];

  for (const track of media.video || []) {
    const parts = [track.displayCodec || track.codec].filter(Boolean);
    if (track.width != null && track.height != null) {
      parts.push(`${track.width}×${track.height}`);
    } else if (track.width != null) {
      parts.push(`${track.width} px breit`);
    } else if (track.height != null) {
      parts.push(`${track.height} px hoch`);
    }
    if (parts.length) lines.push(`Video: ${parts.join(" · ")}`);
  }

  for (const track of media.audio || []) {
    const parts = [track.displayCodec || track.codec].filter(Boolean);
    const sampleRate = formatSampleRate(track.sampleRate);
    const channels = formatChannels(track.channelCount);
    if (sampleRate) parts.push(sampleRate);
    if (channels) parts.push(channels);
    if (parts.length) lines.push(`Audio: ${parts.join(" · ")}`);
  }

  for (const track of media.other || []) {
    const codec = track.displayCodec || track.codec;
    if (codec) lines.push(`Medium: ${codec}`);
  }

  if (!lines.length && Array.isArray(stream?.tracks) && stream.tracks.length) {
    lines.push(`Tracks: ${stream.tracks.join(", ")}`);
  }

  return lines.map(line => `${line}<br/>`).join("");
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
    rtmpsConn: "marker-rtmp",
    hlsSession: "marker-hls",
    webRTCSession: "marker-webrtc",
  }[reader.type] || "";

  const remote = reader?.details?.remoteAddr || "-";
  const rateApi = Number(reader?.details?.mbpsSendRate) || 0;
  const rateCalc = Number(reader?.bitrate_mbps) || 0;

  // Finaler Wert: API bevorzugt, sonst berechnet.
  const finalRate = rateApi > 0 ? rateApi : rateCalc;

  const bytesSent = Number(reader?.details?.outboundBytes)
    || (reader.type === "srtConn" ? Number(reader?.details?.bytesSent) : 0) || 0;

  let html = `
    <div class="reader-block">
      <span class="${markerClass}"></span>Typ: ${reader.type}<br/>
      Remote: ${remote}<br/>
      Rate: ${finalRate > 0 ? finalRate.toFixed(2) : "0.00"} Mbps<br/>
      Gesendet: ${formatBytes(bytesSent)}
  `;

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

  // SRT liefert eine Transport-RTT; bei anderen Protokollen ist nur ICMP-Ping verfügbar.
  const latencyLabel = src.type === "srtConn" ? "RTT" : "Ping";
  const latencyValue = src.type === "srtConn"
    ? Number(src.transport_rtt_ms || details.msRTT)
    : Number(src.icmp_rtt_ms);
  const latencyLine = Number.isFinite(latencyValue) && latencyValue > 0
    ? `${latencyLabel}: ${latencyValue.toFixed(2)} ms<br/>`
    : "";


  // Empfangen: bevorzugt Detailzähler, fallback auf Path-Feld.
  const bytesRx = details.inboundBytes != null
    ? Number(details.inboundBytes)
    : (src.type === "srtConn" && details.bytesReceived != null
      ? Number(details.bytesReceived)
      : Number(stream.inboundBytes || 0));

  return `
    <div class="stream-left">
      <div class="stream-title">${stream.name}</div>
      Publisher (${src.type || "-"})<br/>
      Remote: ${details.remoteAddr || "-"}<br/>
      ${latencyLine}
      Rate: ${finalRate > 0 ? finalRate.toFixed(2) : "0.00"} Mbps<br/>
      Empfangen: ${formatBytes(bytesRx)}<br/>
      ${renderMedia(stream)}
    </div>
  `;
}

function buildPreviewIframeSrc(streamName) {
  const encodedPath = streamName
    .split("/")
    .map(segment => encodeURIComponent(segment))
    .join("/");

  return `http://${window.location.hostname}:8889/__preview__/${encodedPath}?controls=false&muted=true&autoplay=true&playsInline=true`;
}

/**
 * Rendert eine komplette Streamkarte (links Publisher, Mitte Vorschaustream, rechts Readers).
 * @param {Object} stream - Aggregiertes Stream-Objekt mit source, tracks, readers etc.
 * @returns {HTMLDivElement} DOM-Element der Streamkarte
 */
export function renderStreamCard(stream) {
  // Readers typisiert sortieren: SRT → RTMP → HLS → WebRTC.
  const readersSorted = [...(stream.readers || [])].sort((a, b) => {
    const order = {
      srtConn: 1, rtmpConn: 2, rtmpsConn: 3, rtspSession: 4,
      rtspsSession: 5, hlsSession: 6, webRTCSession: 7, moqSession: 8,
    };
    return (order[a.type] || 99) - (order[b.type] || 99);
  });

  const div = document.createElement("div");
  div.className = "stream-card";

  const left = renderStreamLeft(stream);

  const previewSrc = buildPreviewIframeSrc(stream.name);

  const center = `
  <div class="stream-center">
    <iframe
      class="preview-frame"
      src="${previewSrc}"
      title="Preview: ${stream.name}"
      loading="lazy"
      scrolling="no"
      allow="autoplay"
      referrerpolicy="no-referrer">
    </iframe>
  </div>
`;

  const right = `
    <div class="stream-right">
      <span class="label">Readers (${readersSorted.length}):</span>
      ${readersSorted.map(renderReader).join("")}
    </div>
  `;

  div.innerHTML = left + center + right;


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
    const order = {
      srtConn: 1, rtmpConn: 2, rtmpsConn: 3, rtspSession: 4,
      rtspsSession: 5, hlsSession: 6, webRTCSession: 7, moqSession: 8,
    };
    return (order[a.type] || 99) - (order[b.type] || 99);
  });

  if (right) {
    right.innerHTML = `
      <span class="label">Readers (${readersSorted.length}):</span>
      ${readersSorted.map(renderReader).join("")}
    `;
  }
}
