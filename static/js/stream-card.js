/**
 * MediaMTX Monitor - Stream card composition.
 *
 * Composes stream panels and updates cards while preserving preview iframes.
 */

import {connectionTotal} from "./connection-metrics.js";
import {escapeHtml, formatBytes, formatRelativeTime} from "./format-utils.js";
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

function renderConnectionMetrics(connection, direction, stream = null) {
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
export function renderReader(reader, index = 0, streamName = "", stream = null) {
  return `
    <section class="reader-block">
      <h3>Reader ${index + 1}</h3>
      ${renderConnectionHeading(reader?.type, reader?.details || {}, reader)}
      ${renderConnectionMetrics(reader, "out", stream || {name: streamName})}
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
      ${renderConnectionHeading(source.type, source.details || {}, source)}
      ${renderConnectionMetrics(source, "in", stream)}
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
 */
function updatePreview(preview, stream, webrtcBaseUrl) {
  if (!preview) return;
  preview.setAttribute("title", `Preview: ${stream?.name || ""}`);
  const wantedSrc = stream?.available === false
    ? null
    : buildPreviewIframeSrc(stream?.name, webrtcBaseUrl);
  const currentSrc = preview.getAttribute("src");
  if (!wantedSrc) {
    if (currentSrc !== null) preview.removeAttribute("src");
    return;
  }
  if (currentSrc !== wantedSrc) preview.setAttribute("src", wantedSrc);
}

/** Render one MediaMTX forward destination as a permanent OUT block. */
export function renderForwardDestination(destination, index = 0) {
  const type = destination?.type;
  const state = destination?.state;
  return `
    <section class="reader-block forward-block">
      <h3>Forward ${index + 1}</h3>
      <div class="connection-heading">
        <span>${escapeHtml(type ? String(type).toUpperCase() : "—")}</span>
        <span class="forward-state">· ${escapeHtml(state || "—")}</span>
      </div>
      ${renderMetrics([
        metric("Total", formatBytes(destination?.outboundBytes)),
        metric(
          "Aufgebaut",
          formatRelativeTime(destination?.created),
          null,
          null,
          null,
          destination?.created,
        ),
      ])}
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

function renderHeaderContent(stream) {
  const outCount = (stream?.readers?.length || 0)
    + (stream?.forwardDestinations?.length || 0);
  const active = isStreamActive(stream);
  return `
    <div class="stream-name">${escapeHtml(stream?.name || "—")}</div>
    <div class="stream-status${active ? "" : " stream-status-idle"}">
      <span class="live-dot"></span>${active ? "LIVE" : "INAKTIV"} · ${outCount} OUT
    </div>
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

  updatePreview(card.querySelector(".preview-frame"), stream, webrtcBaseUrl);
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
  updatePreview(card.querySelector(".preview-frame"), stream, webrtcBaseUrl);
}
