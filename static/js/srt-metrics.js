/**
 * MediaMTX Monitor - SRT metric rendering.
 *
 * Presents native SRT timing, latency assessment, and impact telemetry.
 */

import {connectionRate} from "./connection-metrics.js";
import {escapeHtml, firstAvailable, formatBytes, formatConnectionAge, formatCount, formatNumber, optionalNumber} from "./format-utils.js";
import {metric, metricFullRow, renderMetrics} from "./metric-grid.js";
import {renderRttTrend} from "./sparkline-charts.js";

function getSrtRttAssessment(rttValue, latencyValue) {
  const rtt = optionalNumber(rttValue);
  const latency = optionalNumber(latencyValue);
  if (rtt == null || rtt < 0 || latency == null || latency <= 0) return null;

  const ratio = rtt / latency;
  const status = ratio <= 0.25
    ? "good"
    : ratio <= 1 / 3 ? "warning" : "critical";
  const percentage = ratio * 100;
  const percentageLabel = percentage === 0
    ? "0%"
    : percentage < 1 ? "<1%" : `${Math.round(percentage)}%`;
  const fillPercentage = Number((Math.min(ratio / 0.40, 1) * 100).toFixed(2));
  const multiplier = rtt === 0 ? null : latency / rtt;
  const multiplierLabel = multiplier == null ? "∞×" : `${multiplier.toFixed(1)}×`;

  return {status, percentageLabel, fillPercentage, multiplierLabel};
}

function renderSrtRttAssessment(assessment) {
  if (!assessment) return "";
  const description = `RTT / SRT-Latency: ${assessment.percentageLabel}; `
    + `SRT-Latency entspricht ${assessment.multiplierLabel} RTT`;
  return `
    <div class="srt-rtt-assessment srt-rtt-${assessment.status}"
         aria-label="${escapeHtml(description)}"
         title="${escapeHtml(description)}">
      <span class="srt-rtt-track" aria-hidden="true">
        <span class="srt-rtt-fill" style="width: ${assessment.fillPercentage}%"></span>
      </span>
      <span class="srt-rtt-percentage">${escapeHtml(assessment.percentageLabel)}</span>
    </div>
  `;
}

function renderImpactIndicators(connection, direction) {
  const eventWindows = connection?.window_metrics?.events || {};
  const recentEvents = eventWindows["10s"] || {};
  const heldEvents = eventWindows["60s"] || {};
  if (!eventWindows["10s"] && !eventWindows["60s"]) return "";
  const definitions = direction === "in"
    ? [
      ["Rcv Loss", "loss_packets", false],
      ["Retrans", "retrans_packets", false],
      ["Drop", "drop_packets", true],
      ["Belated", "belated_packets", true],
      ["Undecrypt", "undecrypt_packets", true],
    ]
    : [
      ["Send Loss", "loss_packets", false],
      ["Retrans", "retrans_packets", false],
      ["Send Drop", "drop_packets", true],
    ];
  const impacts = definitions.map(([label, field, critical]) => ({
    label,
    field,
    critical,
    value10: optionalNumber(recentEvents[field]),
    value60: optionalNumber(heldEvents[field]),
  }));
  const currentCritical = impacts.some(item => item.critical && item.value10 > 0);
  const currentWarning = impacts.some(item => !item.critical && item.value10 > 0);
  const recentImpact = impacts.some(item => item.value60 > 0);
  const allClear = impacts.every(item => item.value10 === 0 && item.value60 === 0);
  const status = currentCritical
    ? "crit"
    : currentWarning ? "warn" : recentImpact ? "recent" : allClear ? "ok" : "unavailable";
  const statusLabel = {
    crit: "CRIT",
    warn: "WARN",
    recent: "RECENT",
    ok: "OK",
    unavailable: "—",
  }[status];
  const causes = impacts.flatMap(item => {
    const values = [];
    if (item.value10 > 0) values.push(`10s ${formatCount(item.value10)}`);
    if (item.value60 > 0) values.push(`60s ${formatCount(item.value60)}`);
    return values.length ? [`${item.label} ${values.join(" · ")}`] : [];
  });
  const detail = status === "ok"
    ? "10s OK · 60s OK"
    : status === "recent"
      ? `10s OK · ${causes.join(" · ")}`
      : causes.join(" · ") || "10s — · 60s —";
  return `
    <div class="srt-impact srt-impact-${status}"
         aria-label="SRT Impact ${escapeHtml(statusLabel)}: ${escapeHtml(detail)}">
      <div class="srt-impact-summary">
        <span class="srt-impact-title">SRT Impact</span>
        <span class="srt-impact-dot" aria-hidden="true"></span>
        <span class="srt-impact-status">${escapeHtml(statusLabel)}</span>
      </div>
      <div class="srt-impact-detail">${escapeHtml(detail)}</div>
    </div>
  `;
}

function renderLinkTelemetry(connection, historyKey, assessment = null, direction = null) {
  const trend = renderRttTrend(connection, historyKey);
  const latencyRelation = connection?.type === "srtConn"
    ? renderSrtRttAssessment(assessment)
    : "";
  const impacts = connection?.type === "srtConn"
    ? renderImpactIndicators(connection, direction)
    : "";
  if (!trend && !latencyRelation && !impacts) return null;
  return `<div class="link-telemetry">${trend}${latencyRelation}${impacts}</div>`;
}

export function renderSrtMetrics(connection, direction, totalBytes, historyKey = null) {
  const details = connection?.details || {};
  const health = connection?.srt_health || {};
  const rateLabel = direction === "in" ? "RX" : "TX";
  const rate = connectionRate(connection, direction);
  const lossRate = direction === "in"
    ? details.packetsReceivedLossRate
    : details.packetsSendLossRate;
  const lossLabel = direction === "in" ? "Rcv Loss Rate" : "Send Loss Rate";
  const loss = lossRate == null
    ? null
    : metric(lossLabel, formatNumber(lossRate, 2), "%");
  const rtt = firstAvailable(
    connection?.transport_rtt_ms,
    health.rtt_ms,
    details.msRTT,
  );
  const assessment = getSrtRttAssessment(rtt, connection?.srt_latency_ms);
  const linkTelemetry = renderLinkTelemetry(
    connection,
    historyKey,
    assessment,
    direction,
  );

  return renderMetrics([
    metric(rateLabel, rate == null ? "—" : formatNumber(rate, 2), "Mbit/s"),
    metric("Total", formatBytes(totalBytes)),
    metric(
      "RTT",
      rtt == null && linkTelemetry ? "—" : formatNumber(rtt, 2),
      "ms",
    ),
    metric(
      direction === "in" ? "Rcv Latency" : "Snd Latency",
      formatCount(connection?.srt_latency_ms),
      "ms",
      null,
      assessment ? `srt-rtt-${assessment.status}` : null,
    ),
    metricFullRow(linkTelemetry),
    loss,
    metric("SRT est. Link", formatNumber(
      firstAvailable(health.link_capacity_mbps, details.mbpsLinkCapacity),
      1,
    ), "Mbit/s"),
    direction === "out"
      ? metric("Frame Discard", formatCount(details.outboundFramesDiscarded))
      : null,
    metric("Age", formatConnectionAge(details.created) ?? "—"),
  ]);
}
