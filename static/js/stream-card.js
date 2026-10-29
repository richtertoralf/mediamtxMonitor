/**
 * MediaMTX Monitor - Stream card composition.
 *
 * Composes stream panels and updates cards while preserving preview iframes.
 * A preview runs only after the viewer ticks "Vorschau anzeigen" on a card.
 */

import {connectionTotal} from "./connection-metrics.js";
import {escapeHtml, firstAvailable, formatBytes, formatConnectionAge, formatRelativeTime, formatUntil} from "./format-utils.js";
import {metric, renderConnectionHeading, renderMetrics} from "./metric-grid.js";
import {renderMedia} from "./media-tracks.js";
import {renderHlsMuxer, renderNonSrtMetrics, renderPathMetrics} from "./protocol-metrics.js";
import {renderSrtMetrics} from "./srt-metrics.js";
import {connectionTelemetryKey} from "./telemetry-store.js";

/** Report whether MediaMTX currently serves this path as a running stream. */
export function isStreamActive(stream) {
  return stream?.available === true && stream?.online === true;
}

/** Render the monitor version in the page heading and browser tab. */
export function renderMonitorTitle(titleElement, monitorVersion) {
  const version = typeof monitorVersion === "string" ? monitorVersion.trim() : "";
  const title = version
    ? `MediaMTX Stream Monitor · v${version} - richterprojects.com`
    : "MediaMTX Stream Monitor - richterprojects.com";
  if (titleElement) titleElement.textContent = title;
  document.title = title;
}

/** Report whether MediaMTX pulls this source itself (static source). */
function isStaticSource(source) {
  return typeof source?.type === "string" && source.type.endsWith("Source");
}

function renderStaticSourceStatus(source) {
  if (!isStaticSource(source)) return "";
  const details = source?.details || {};
  const status = renderMetrics([metric("Pull", details.state || "—")]);
  const error = details.last_error
    ? `<div class="connection-notes">Fehler: ${escapeHtml(details.last_error)}</div>`
    : "";
  return status + error;
}

function renderConnectionMetrics(source, direction, stream = null) {
  // Static sources carry the metrics of their equivalent connection type.
  const connection = source?.connection_type
    ? {...source, type: source.connection_type}
    : source;
  const totalBytes = connectionTotal(connection, direction, stream);
  const historyKey = connectionTelemetryKey(
    stream?.name,
    direction === "in" ? "publisher" : "reader",
    connection,
  );
  return connection?.type === "srtConn"
    ? renderSrtMetrics(connection, direction, totalBytes, historyKey)
    : renderNonSrtMetrics(connection, direction, totalBytes)
      + (direction === "in" ? renderPathMetrics(stream) : "");
}

function connectionNotes(connection) {
  const details = connection?.details || {};
  const lines = [];
  if (details.userAgent) lines.push(`Agent: ${details.userAgent}`);
  if (connection?.type === "hlsSession" && details.isCDN != null) {
    lines.push(`CDN: ${details.isCDN ? "ja" : "nein"}`);
  }
  // MediaMTX closes a session when its authentication (JWT) expires.
  const expiry = formatUntil(details.expiresAt);
  if (expiry) lines.push(`Session endet: ${expiry} (${details.expiresAt})`);
  return lines.length
    ? `<div class="connection-notes">${lines.map(escapeHtml).join("<br>")}</div>`
    : "";
}

/** Render one permanent OUT connection block. */
export function renderReader(reader, index = 0, streamName = "", stream = null) {
  return `
    <section class="reader-block">
      <h3>Reader ${index + 1}</h3>
      ${renderConnectionHeading(reader?.type, reader?.details || {}, reader)}
      ${renderConnectionMetrics(reader, "out", stream || {name: streamName})}
      ${connectionNotes(reader)}
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
      ${renderConnectionHeading(source.type, source.details || {}, source)}
      ${renderStaticSourceStatus(source)}
      ${renderConnectionMetrics(source, "in", stream)}
      ${connectionNotes(source)}
    </section>
  `;
}

function buildPreviewIframeSrc(streamName, webrtcBaseUrl) {
  const encodedPath = String(streamName || "")
    .split("/")
    .map(segment => encodeURIComponent(segment))
    .join("/");
  let base;
  try {
    base = new URL(webrtcBaseUrl);
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password
        || base.search || base.hash) return null;
  } catch {
    return null;
  }
  return `${base.href.replace(/\/$/, "")}/__preview__/${encodedPath}?controls=false&muted=true&autoplay=true&playsInline=true`;
}

/**
 * Apply the wanted preview source without restarting an unchanged session.
 *
 * Re-assigning an unchanged `src` reloads the iframe and therefore rebuilds the
 * WebRTC session, so the attribute is only written on an actual change.
 * Removing `src` closes this browser's WebRTC reader; MediaMTX stops the shared
 * transcoder itself once no reader is left (`runOnDemandCloseAfter`).
 */
function updatePreview(card) {
  const preview = card?.querySelector(".preview-frame");
  if (!preview) return;
  const {stream, webrtcBaseUrl} = card.previewContext || {};
  const wanted = card.querySelector(".preview-toggle")?.checked === true;
  preview.setAttribute("title", `Preview: ${stream?.name || ""}`);
  const wantedSrc = !wanted || stream?.available === false
    ? null
    : buildPreviewIframeSrc(stream?.name, webrtcBaseUrl);
  const currentSrc = preview.getAttribute("src");
  if (!wantedSrc) {
    if (currentSrc !== null) preview.removeAttribute("src");
    return;
  }
  if (currentSrc !== wantedSrc) preview.setAttribute("src", wantedSrc);
}

function renderForwardMetrics(destination) {
  // The collector maps a forward type to the connection type with equal
  // native transport fields, so the existing OUT renderers apply.
  const details = destination?.details || {};
  const connection = {
    ...destination,
    type: destination?.connection_type,
    details: {
      ...details,
      outboundBytes: firstAvailable(details.outboundBytes, destination?.outboundBytes),
      created: destination?.created,
    },
  };
  if (connection.type === "srtConn") {
    return renderSrtMetrics(connection, "out", connectionTotal(connection, "out"));
  }
  if (connection.type) {
    return renderNonSrtMetrics(connection, "out", connectionTotal(connection, "out"));
  }
  return renderMetrics([
    metric("Total", formatBytes(destination?.outboundBytes)),
    metric(
      "Aufgebaut",
      formatRelativeTime(destination?.created),
      null,
      null,
      null,
      destination?.created,
    ),
  ]);
}

/** Render one MediaMTX forward destination as a permanent OUT block. */
export function renderForwardDestination(destination, index = 0) {
  const type = destination?.type;
  const state = destination?.state;
  return `
    <section class="reader-block forward-block${isForwardAnomalous(destination) ? " forward-block-warn" : ""}">
      <h3>Forward ${index + 1}</h3>
      <div class="connection-heading">
        <span>${escapeHtml(type ? String(type).toUpperCase() : "—")}</span>
        <span class="forward-state">· ${escapeHtml(state || "—")}</span>
      </div>
      ${renderForwardMetrics(destination)}
    </section>
  `;
}

function sortedReaders(stream) {
  const order = {
    srtConn: 1, rtmpConn: 2, rtmpsConn: 3, rtspSession: 4,
    rtspsSession: 5, hlsSession: 6, webRTCSession: 7, moqSession: 8,
  };
  return [...(stream?.readers || [])].sort((a, b) =>
    (order[a.type] || 99) - (order[b.type] || 99));
}

/** Sum native discard windows of all OUT consumers over the last 60 s. */
export function streamDiscards60s(stream) {
  const windows = connection => connection?.window_metrics || {};
  const outputs = [...(stream?.readers || []), ...(stream?.forwardDestinations || [])];
  let total = 0;
  for (const connection of outputs) {
    const metrics = windows(connection);
    for (const value of [
      metrics.frame_discard?.["60s"],
      metrics.protocol_counters?.["60s"]?.frame_discard,
      metrics.protocol_counters?.["60s"]?.discard,
      metrics.events?.["60s"]?.discarded_frames,
    ]) {
      if (typeof value === "number" && value > 0) total += value;
    }
  }
  const muxer = stream?.hls_muxer?.window_metrics?.protocol_counters?.["60s"]?.mux_discard;
  if (typeof muxer === "number" && muxer > 0) total += muxer;
  return total;
}

/** A forward destination that is not forwarding, or forwards no data. */
export function isForwardAnomalous(destination) {
  if (destination?.state !== "forwarding") return true;
  return destination?.bitrate_mbps === 0;
}

function renderHeaderBadges(stream) {
  const badges = [];
  const discards = streamDiscards60s(stream);
  if (discards > 0) {
    badges.push(`<span class="stream-badge stream-badge-warn" title="Von MediaMTX verworfene Frames bzw. Pakete aller OUT-Verbindungen in den letzten 60 s">Discard 60s: ${discards}</span>`);
  }
  const anomalous = (stream?.forwardDestinations || []).filter(isForwardAnomalous);
  if (anomalous.length) {
    const states = anomalous.map(item => item?.state || "—").join(", ");
    badges.push(`<span class="stream-badge stream-badge-warn" title="${escapeHtml(`Zustand: ${states}`)}">Forward auffällig: ${anomalous.length}</span>`);
  }
  return badges.join("");
}

function renderHeaderContent(stream) {
  const outCount = (stream?.readers?.length || 0)
    + (stream?.forwardDestinations?.length || 0);
  const active = isStreamActive(stream);
  const since = active ? formatConnectionAge(stream?.availableTime) : null;
  const times = [
    stream?.availableTime ? `verfügbar seit ${stream.availableTime}` : null,
    stream?.onlineTime ? `online seit ${stream.onlineTime}` : null,
  ].filter(Boolean).join(" · ");
  // Only a differing rule (regex, all_others) explains something new.
  const rule = stream?.confName && stream.confName !== stream?.name
    ? `<span class="stream-rule" title="Verwendete Konfigurationsregel">Regel ${escapeHtml(stream.confName)}</span>`
    : "";
  return `
    <div class="stream-name">${escapeHtml(stream?.name || "—")}${rule}${renderHeaderBadges(stream)}</div>
    <div class="stream-status${active ? "" : " stream-status-idle"}"${times ? ` title="${escapeHtml(times)}"` : ""}>
      <span class="live-dot"></span>${active ? "LIVE" : "INAKTIV"}${since ? ` seit ${escapeHtml(since)}` : ""} · ${outCount} OUT
    </div>
  `;
}

function renderCenterContent(stream) {
  return `
    <h2 class="panel-title">PREVIEW</h2>
    <label class="preview-toggle-label"
           title="Startet in MediaMTX einen Vorschau-Transcoder; mehrere Betrachter eines Streams teilen ihn.">
      <input type="checkbox" class="preview-toggle"> Vorschau anzeigen
    </label>
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
  const forwards = stream?.forwardDestinations || [];
  return `
    <h2 class="panel-title">OUT</h2>
    ${renderHlsMuxer(stream)}
    ${readers.map((reader, index) =>
      renderReader(reader, index, stream?.name, stream)).join("")}
    ${forwards.map((destination, index) =>
      renderForwardDestination(destination, index)).join("")}
    ${readers.length || forwards.length
      ? ""
      : '<div class="no-readers">Keine OUT-Verbindung</div>'}
  `;
}

/** Render a complete stream card with a fixed semantic three-part flow. */
export function renderStreamCard(stream, webrtcBaseUrl = "") {
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

  card.previewContext = {stream, webrtcBaseUrl};
  card.querySelector(".preview-toggle")
    ?.addEventListener("change", () => updatePreview(card));
  updatePreview(card);
  return card;
}

/** Update changing metrics while preserving the existing preview iframe. */
export function updateStreamCard(card, stream, webrtcBaseUrl = "") {
  const header = card.querySelector(".stream-header");
  const left = card.querySelector(".stream-left");
  const media = card.querySelector(".media-summary");
  const right = card.querySelector(".stream-right");

  if (header) header.innerHTML = renderHeaderContent(stream);
  if (left) left.outerHTML = renderStreamLeft(stream);
  if (media) media.innerHTML = renderMedia(stream);
  if (right) right.innerHTML = renderRightContent(stream);
  card.previewContext = {stream, webrtcBaseUrl};
  updatePreview(card);
}
