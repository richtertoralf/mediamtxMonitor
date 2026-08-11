/**
 * MediaMTX Monitor - Stream card renderer.
 *
 * Renders the normalized stream snapshot as a permanent IN / Preview / OUT
 * signal-flow view. Protocol-specific metrics remain explicitly labelled.
 */

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function optionalNumber(value) {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function firstAvailable(...values) {
  return values.find(value => value !== null && value !== undefined) ?? null;
}

function formatNumber(value, digits) {
  const number = optionalNumber(value);
  return number == null ? null : number.toFixed(digits);
}

function formatCount(value) {
  const number = optionalNumber(value);
  return number == null ? null : `${number}`;
}

function formatBytes(bytes) {
  let value = optionalNumber(bytes);
  if (value == null) return null;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let unitIndex = 0;
  while (Math.abs(value) >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex++;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 2)} ${units[unitIndex]}`;
}

function formatConnectionAge(created) {
  if (!created) return null;
  const createdAt = Date.parse(created);
  if (!Number.isFinite(createdAt)) return null;
  const seconds = Math.max(0, Math.floor((Date.now() - createdAt) / 1000));
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h`;
  return `${Math.floor(seconds / 86400)} d`;
}

function protocolLabel(type) {
  return {
    srtConn: "SRT",
    rtmpConn: "RTMP",
    rtmpsConn: "RTMPS",
    rtspConn: "RTSP",
    rtspSession: "RTSP",
    rtspsConn: "RTSPS",
    rtspsSession: "RTSPS",
    hlsSession: "HLS",
    webRTCSession: "WebRTC",
    moqSession: "MoQ",
  }[type] || type || "—";
}

function protocolMarkerClass(type) {
  if (type === "srtConn") return "marker-srt";
  if (type === "rtmpConn" || type === "rtmpsConn") return "marker-rtmp";
  if (type === "hlsSession") return "marker-hls";
  if (type === "webRTCSession") return "marker-webrtc";
  return "marker-generic";
}

function metric(label, value, unit = null) {
  return value == null ? null : {label, value, unit};
}

function renderMetrics(metrics) {
  const available = metrics.filter(Boolean);
  if (!available.length) return "";
  return `
    <dl class="metric-grid">
      ${available.map(item => `
        <div class="metric">
          <dt>
            <span class="metric-label">${escapeHtml(item.label)}</span>
            ${item.unit == null
              ? ""
              : `<span class="metric-unit">${escapeHtml(item.unit)}</span>`}
          </dt>
          <dd>${escapeHtml(item.value)}</dd>
        </div>
      `).join("")}
    </dl>
  `;
}

function renderConnectionHeading(type, details) {
  const remote = details?.remoteAddr || "—";
  return `
    <div class="connection-heading">
      <span class="protocol-marker ${protocolMarkerClass(type)}"></span>
      <span>${escapeHtml(protocolLabel(type))}</span>
      <span class="remote-address">· ${escapeHtml(remote)}</span>
    </div>
  `;
}

function connectionRate(connection, direction) {
  const details = connection?.details || {};
  const health = connection?.srt_health || {};
  const nativeRate = direction === "in"
    ? firstAvailable(health.rx_mbps, details.mbpsReceiveRate)
    : firstAvailable(health.tx_mbps, details.mbpsSendRate);
  return firstAvailable(nativeRate, connection?.bitrate_mbps);
}

function connectionTotal(connection, direction, stream) {
  const details = connection?.details || {};
  if (direction === "in") {
    return firstAvailable(
      details.inboundBytes,
      connection?.type === "srtConn" ? details.bytesReceived : null,
      stream?.inboundBytes,
    );
  }
  return firstAvailable(
    details.outboundBytes,
    connection?.type === "srtConn" ? details.bytesSent : null,
  );
}

function pingValue(connection) {
  return firstAvailable(connection?.ping_rtt_ms, connection?.icmp_rtt_ms);
}

function renderSrtMetrics(connection, direction, totalBytes) {
  const details = connection?.details || {};
  const health = connection?.srt_health || {};
  const rateLabel = direction === "in" ? "RX" : "TX";
  const rate = connectionRate(connection, direction);
  const lossRate = direction === "in"
    ? details.packetsReceivedLossRate
    : details.packetsSendLossRate;
  const loss = lossRate != null
    ? metric("Loss", formatNumber(lossRate, 2), "%")
    : metric("Loss", formatCount(health.loss_packets), "pkt");

  return renderMetrics([
    metric(rateLabel, rate == null ? "—" : formatNumber(rate, 2), "Mbit/s"),
    metric("Total", formatBytes(totalBytes)),
    metric("RTT", formatNumber(firstAvailable(
      connection?.transport_rtt_ms,
      health.rtt_ms,
      details.msRTT,
    ), 2), "ms"),
    loss,
    metric("Retrans", formatCount(health.retrans_packets), "pkt"),
    metric("Drop", formatCount(health.drop_packets), "pkt"),
    metric("Link", formatNumber(
      firstAvailable(health.link_capacity_mbps, details.mbpsLinkCapacity),
      1,
    ), "Mbit/s"),
    metric("Reserve", formatNumber(health.reserve_ratio, 1), "×"),
    metric("Belated", formatCount(health.belated_packets), "pkt"),
    metric("Undecrypt", formatCount(health.undecrypt_packets), "pkt"),
    metric("Age", formatConnectionAge(details.created)),
  ]);
}

function renderNonSrtMetrics(connection, direction, totalBytes) {
  const details = connection?.details || {};
  const type = connection?.type;
  const rateLabel = direction === "in" ? "RX" : "TX";
  const rate = connectionRate(connection, direction);
  const metrics = [
    metric(rateLabel, rate == null
      ? "—"
      : formatNumber(rate, 2), "Mbit/s"),
    metric("Total", formatBytes(totalBytes)),
    metric("Ping", formatNumber(pingValue(connection), 2), "ms"),
  ];

  if (type === "rtspSession" || type === "rtspsSession") {
    if (direction === "in") {
      metrics.push(
        metric("Jitter", formatNumber(details.inboundRTPPacketsJitter, 2), "ms"),
        metric("Loss", formatCount(details.inboundRTPPacketsLost), "pkt"),
        metric("RTP Error", formatCount(details.inboundRTPPacketsInError)),
        metric("RTCP Error", formatCount(details.inboundRTCPPacketsInError)),
      );
    } else {
      metrics.push(
        metric("Loss", formatCount(details.outboundRTPPacketsReportedLost), "pkt"),
        metric("Discard", formatCount(details.outboundRTPPacketsDiscarded)),
      );
    }
  }

  if ((type === "rtmpConn" || type === "rtmpsConn") && direction === "out") {
    metrics.push(metric("Discard", formatCount(details.outboundFramesDiscarded)));
  }

  metrics.push(metric("Age", formatConnectionAge(details.created)));
  return renderMetrics(metrics);
}

function renderConnectionMetrics(connection, direction, stream = null) {
  const totalBytes = connectionTotal(connection, direction, stream);
  return connection?.type === "srtConn"
    ? renderSrtMetrics(connection, direction, totalBytes)
    : renderNonSrtMetrics(connection, direction, totalBytes);
}

function formatSampleRate(sampleRate) {
  const value = optionalNumber(sampleRate);
  if (value == null || value <= 0) return null;
  if (value >= 1000) return `${Number((value / 1000).toFixed(1))} kHz`;
  return `${value} Hz`;
}

function formatChannels(channelCount) {
  const value = optionalNumber(channelCount);
  if (value == null || value <= 0) return null;
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
    if (parts.length) lines.push(parts.join(" · "));
  }

  for (const track of media.audio || []) {
    const parts = [track.displayCodec || track.codec].filter(Boolean);
    const sampleRate = formatSampleRate(track.sampleRate);
    const channels = formatChannels(track.channelCount);
    if (sampleRate) parts.push(sampleRate);
    if (channels) parts.push(channels);
    if (parts.length) lines.push(parts.join(" · "));
  }

  for (const track of media.other || []) {
    const codec = track.displayCodec || track.codec;
    if (codec) lines.push(codec);
  }

  if (!lines.length && Array.isArray(stream?.tracks) && stream.tracks.length) {
    lines.push(stream.tracks.join(" · "));
  }

  if (!lines.length) return '<div class="media-empty">Keine Media-Details</div>';
  return `<div class="media-lines">${lines.map(line =>
    `<div>${escapeHtml(line)}</div>`).join("")}</div>`;
}

function readerDetails(reader) {
  const details = reader?.details || {};
  const lines = [];
  if (reader?.type === "hlsSession") {
    if (details.userAgent) lines.push(`Agent: ${details.userAgent}`);
    if (details.isCDN != null) lines.push(`CDN: ${details.isCDN ? "ja" : "nein"}`);
  }
  return lines.length
    ? `<div class="connection-notes">${lines.map(escapeHtml).join("<br>")}</div>`
    : "";
}

/** Render one permanent OUT connection block. */
export function renderReader(reader, index = 0) {
  return `
    <section class="reader-block">
      <h3>Reader ${index + 1}</h3>
      ${renderConnectionHeading(reader?.type, reader?.details || {})}
      ${renderConnectionMetrics(reader, "out")}
      ${readerDetails(reader)}
    </section>
  `;
}

/** Compatibility export for focused SRT metric tests. */
export function renderSrtHealth(health, rateField, fallbackRate = null, details = {}) {
  const direction = rateField === "rx_mbps" ? "in" : "out";
  const connection = {
    type: "srtConn",
    bitrate_mbps: fallbackRate,
    details,
    srt_health: health || {},
  };
  return renderSrtMetrics(connection, direction, null);
}

/** Render the IN column without stream-level media information. */
export function renderStreamLeft(stream) {
  const source = stream?.source || {};
  return `
    <section class="stream-left flow-panel" aria-label="Eingangsverbindung">
      <h2 class="panel-title">IN</h2>
      ${renderConnectionHeading(source.type, source.details || {})}
      ${renderConnectionMetrics(source, "in", stream)}
    </section>
  `;
}

function buildPreviewIframeSrc(streamName) {
  const encodedPath = String(streamName || "")
    .split("/")
    .map(segment => encodeURIComponent(segment))
    .join("/");
  return `http://${window.location.hostname}:8889/__preview__/${encodedPath}?controls=false&muted=true&autoplay=true&playsInline=true`;
}

function sortedReaders(stream) {
  const order = {
    srtConn: 1, rtmpConn: 2, rtmpsConn: 3, rtspSession: 4,
    rtspsSession: 5, hlsSession: 6, webRTCSession: 7, moqSession: 8,
  };
  return [...(stream?.readers || [])].sort((a, b) =>
    (order[a.type] || 99) - (order[b.type] || 99));
}

function renderHeaderContent(stream) {
  const outCount = stream?.readers?.length || 0;
  return `
    <div class="stream-name">${escapeHtml(stream?.name || "—")}</div>
    <div class="stream-status"><span class="live-dot"></span>LIVE · ${outCount} OUT</div>
  `;
}

function renderCenterContent(stream) {
  return `
    <h2 class="panel-title">PREVIEW</h2>
    <iframe
      class="preview-frame"
      loading="lazy"
      scrolling="no"
      allow="autoplay"
      referrerpolicy="no-referrer">
    </iframe>
    <div class="media-summary">${renderMedia(stream)}</div>
  `;
}

function renderRightContent(stream) {
  const readers = sortedReaders(stream);
  return `
    <h2 class="panel-title">OUT</h2>
    ${readers.length
      ? readers.map((reader, index) => renderReader(reader, index)).join("")
      : '<div class="no-readers">Keine OUT-Verbindung</div>'}
  `;
}

/** Render a complete stream card with a fixed semantic three-part flow. */
export function renderStreamCard(stream) {
  const card = document.createElement("article");
  card.className = "stream-card";
  card.innerHTML = `
    <header class="stream-header">${renderHeaderContent(stream)}</header>
    <div class="stream-flow">
      ${renderStreamLeft(stream)}
      <section class="stream-center flow-panel" aria-label="Preview und Media">
        ${renderCenterContent(stream)}
      </section>
      <section class="stream-right flow-panel" aria-label="Ausgangsverbindungen">
        ${renderRightContent(stream)}
      </section>
    </div>
  `;

  const preview = card.querySelector(".preview-frame");
  preview.setAttribute("src", buildPreviewIframeSrc(stream?.name));
  preview.setAttribute("title", `Preview: ${stream?.name || ""}`);
  return card;
}

/** Update changing metrics while preserving the existing preview iframe. */
export function updateStreamCard(card, stream) {
  const header = card.querySelector(".stream-header");
  const left = card.querySelector(".stream-left");
  const media = card.querySelector(".media-summary");
  const right = card.querySelector(".stream-right");

  if (header) header.innerHTML = renderHeaderContent(stream);
  if (left) left.outerHTML = renderStreamLeft(stream);
  if (media) media.innerHTML = renderMedia(stream);
  if (right) right.innerHTML = renderRightContent(stream);
}
