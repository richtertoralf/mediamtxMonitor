/**
 * MediaMTX Monitor - Generic metric grid rendering.
 *
 * Builds connection headings and protocol-agnostic metric rows.
 */

import {escapeHtml} from "./format-utils.js";

function protocolLabel(type) {
  return {
    srtConn: "SRT", rtmpConn: "RTMP", rtmpsConn: "RTMPS",
    rtspConn: "RTSP", rtspSession: "RTSP", rtspsConn: "RTSPS",
    rtspsSession: "RTSPS", hlsSession: "HLS",
    webRTCSession: "WebRTC", moqSession: "MoQ",
  }[type] || type || "—";
}

export function metric(label, value, unit = null, assessment = null,
  valueClass = null, title = null) {
  return value == null ? null : {label, value, unit, assessment, valueClass, title};
}

export function metricFullRow(content) {
  return content ? {kind: "full-row", content} : null;
}

export function renderMetrics(metrics) {
  const available = metrics.filter(Boolean);
  if (!available.length) return "";
  return `
    <dl class="metric-grid">
      ${available.map(item => `
        ${item.kind === "full-row" ? `
          <div class="metric-full-row">${item.content}</div>
        ` : `
        <div class="metric${item.assessment ? " metric-with-assessment" : ""}">
          <dt>
            <span class="metric-label">${escapeHtml(item.label)}</span>
            ${item.unit == null ? "" : `<span class="metric-unit">${escapeHtml(item.unit)}</span>`}
          </dt>
          <dd${item.valueClass ? ` class="${escapeHtml(item.valueClass)}"` : ""}${
            item.title ? ` title="${escapeHtml(item.title)}"` : ""
          }>${escapeHtml(item.value)}</dd>
          ${item.assessment || ""}
        </div>
        `}
      `).join("")}
    </dl>
  `;
}

export function renderConnectionHeading(type, details, connection = null) {
  const remote = connection?.common?.remoteAddr || details?.remoteAddr || "—";
  const transport = connection?.protocol_metrics?.metadata?.transport;
  const protocol = protocolLabel(type);
  const shownProtocol = (type === "rtspSession" || type === "rtspsSession") && transport
    ? `${protocol}/${String(transport).toUpperCase()}` : protocol;
  return `
    <div class="connection-heading">
      <span>${escapeHtml(shownProtocol)}</span>
      <span class="remote-address">· ${escapeHtml(remote)}</span>
    </div>
  `;
}
