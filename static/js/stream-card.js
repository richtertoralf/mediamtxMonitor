/**
 * MediaMTX Monitor - Stream card composition.
 *
 * Composes stream panels and updates cards while preserving preview iframes.
 */

import {connectionTotal} from "./connection-metrics.js";
import {escapeHtml} from "./format-utils.js";
import {renderConnectionHeading} from "./metric-grid.js";
import {renderMedia} from "./media-tracks.js";
import {renderHlsMuxer, renderNonSrtMetrics, renderPathMetrics} from "./protocol-metrics.js";
import {renderSrtMetrics} from "./srt-metrics.js";
import {connectionTelemetryKey} from "./telemetry-store.js";

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
    ${renderHlsMuxer(stream)}
    ${readers.length
      ? readers.map((reader, index) => renderReader(reader, index, stream?.name, stream)).join("")
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
