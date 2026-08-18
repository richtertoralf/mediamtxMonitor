/**
 * MediaMTX Monitor - SVG sparkline charts.
 *
 * Renders trends from telemetry-store data without owning history state.
 */

import {escapeHtml, formatNumber, optionalNumber} from "./format-utils.js";
import {
  connectionTimingValues,
  SPARKLINE_BASELINE_Y,
  SPARKLINE_VERTICAL_RANGE,
  TELEMETRY_WINDOW_SECONDS,
  telemetryHistoryByKey,
  telemetryScaleState,
  telemetryTrendY,
  telemetryVariationY,
} from "./telemetry-store.js";

function renderTrendSeries(history, field, className, xPosition, yPosition) {
  const segments = [];
  let currentSegment = [];
  for (const point of history) {
    const value = optionalNumber(point[field]);
    if (value == null) {
      if (currentSegment.length) segments.push(currentSegment);
      currentSegment = [];
      continue;
    }
    currentSegment.push(`${xPosition(point.timestamp).toFixed(2)},${yPosition(value).toFixed(2)}`);
  }
  if (currentSegment.length) segments.push(currentSegment);
  const lastPoint = segments.at(-1)?.at(-1);
  const series = segments.map(points => points.length === 1
    ? points[0] === lastPoint
      ? ""
      : `<circle class="trend-point ${className}" cx="${points[0].split(",")[0]}" cy="${points[0].split(",")[1]}" r="1.8"></circle>`
    : `<polyline class="trend-line ${className}" points="${points.join(" ")}"></polyline>`
  ).join("");
  if (!lastPoint) return series;
  const [lastX, lastY] = lastPoint.split(",");
  return `${series}<circle class="trend-end-marker ${className}" cx="${lastX}" cy="${lastY}" r="2.2"></circle>`;
}

function formatScaleMaximum(value) {
  const number = optionalNumber(value);
  if (number == null) return "—";
  return `${number < 10 ? number.toFixed(1) : Math.round(number)} ms`;
}

export function renderRttTrend(connection, historyKey) {
  const history = telemetryHistoryByKey(historyKey);
  const values = history.flatMap(point => [
    point.current,
    point.variation10,
    point.variation60,
  ].filter(value => value != null));
  if (!history.length || !values.length) return "";
  const latestTimestamp = history[history.length - 1].timestamp;
  const minimumTimestamp = latestTimestamp - TELEMETRY_WINDOW_SECONDS;
  const xPosition = timestamp => Math.max(0, Math.min(240,
    ((timestamp - minimumTimestamp) / TELEMETRY_WINDOW_SECONDS) * 240));
  const timingLabel = "RTT";
  const currentValues = connectionTimingValues(connection);
  const rows = [
    [timingLabel, "current", "trend-current", telemetryTrendY, telemetryScaleState().trend.scaleMaximum],
    ["Var 10s", "variation10", "trend-variation-10", telemetryVariationY,
      telemetryScaleState().variation.scaleMaximum],
    ["Var 60s", "variation60", "trend-variation-60", telemetryVariationY,
      telemetryScaleState().variation.scaleMaximum],
  ];
  return `
    <div class="rtt-trend" role="img" aria-label="${timingLabel}-Trend der letzten 60 Sekunden">
      ${rows.map(([label, field, className, yPosition, scaleMaximum]) => `
        <div class="sparkline-row sparkline-${field}">
          <span class="sparkline-label">${escapeHtml(label)}</span>
          <span class="sparkline-value"><span class="sparkline-number">${escapeHtml(
            formatNumber(currentValues[field], 1) ?? "—",
          )}</span>${currentValues[field] == null
            ? ""
            : '<span class="sparkline-unit">ms</span>'}</span>
          <span class="sparkline-plot">
            <span class="sparkline-scale-max">${escapeHtml(
              formatScaleMaximum(scaleMaximum),
            )}</span>
            <svg class="sparkline-graph" viewBox="0 0 240 24" preserveAspectRatio="none" aria-hidden="true">
              <line class="sparkline-time-marker" x1="120" y1="2" x2="120" y2="22"></line>
              <line class="sparkline-baseline" x1="0" y1="22" x2="240" y2="22"></line>
              ${renderTrendSeries(history, field, className, xPosition, yPosition)}
            </svg>
          </span>
        </div>
      `).join("")}
    </div>
  `;
}

export function renderRateTrend(connection, direction) {
  const history = Array.isArray(connection?.rate_history)
    ? connection.rate_history
    : [];
  const values = history.map(point => optionalNumber(point?.mbps))
    .filter(value => value != null && value >= 0);
  const timestamps = history.map(point => optionalNumber(point?.timestamp))
    .filter(value => value != null);
  if (!values.length || !timestamps.length) return "";

  const latestTimestamp = Math.max(...timestamps);
  const minimumTimestamp = latestTimestamp - TELEMETRY_WINDOW_SECONDS;
  const maximum = Math.max(...values, 0.1);
  const xPosition = timestamp => Math.max(0, Math.min(240,
    ((timestamp - minimumTimestamp) / TELEMETRY_WINDOW_SECONDS) * 240));
  const yPosition = value => SPARKLINE_BASELINE_Y
    - (Math.max(0, Math.min(maximum, value)) / maximum) * SPARKLINE_VERTICAL_RANGE;
  const points = history.map(point => ({
    timestamp: optionalNumber(point?.timestamp),
    rate: optionalNumber(point?.mbps),
  })).filter(point => point.timestamp != null);
  const label = direction === "in" ? "RX-Verlauf" : "TX-Verlauf";

  return `
    <div class="rate-trend" role="img" aria-label="${label} der letzten 60 Sekunden">
      <span class="rate-trend-label">${label}</span>
      <span class="sparkline-plot">
        <span class="rate-scale-max">${escapeHtml(formatNumber(maximum, 2))} Mbit/s</span>
        <svg class="sparkline-graph" viewBox="0 0 240 24" preserveAspectRatio="none" aria-hidden="true">
          <line class="sparkline-time-marker" x1="120" y1="2" x2="120" y2="22"></line>
          <line class="sparkline-baseline" x1="0" y1="22" x2="240" y2="22"></line>
          ${renderTrendSeries(points, "rate", "trend-rate", xPosition, yPosition)}
        </svg>
      </span>
    </div>
  `;
}

export function renderJitterTrend(connection) {
  const history = Array.isArray(connection?.jitter_history)
    ? connection.jitter_history
    : [];
  const values = history.map(point => optionalNumber(point?.ms))
    .filter(value => value != null && value >= 0);
  const timestamps = history.map(point => optionalNumber(point?.timestamp))
    .filter(value => value != null);
  if (!values.length || !timestamps.length) return "";
  const latestTimestamp = Math.max(...timestamps);
  const minimumTimestamp = latestTimestamp - TELEMETRY_WINDOW_SECONDS;
  const maximum = Math.max(...values, 0.1);
  const xPosition = timestamp => Math.max(0, Math.min(240,
    ((timestamp - minimumTimestamp) / TELEMETRY_WINDOW_SECONDS) * 240));
  const yPosition = value => SPARKLINE_BASELINE_Y
    - (Math.max(0, Math.min(maximum, value)) / maximum) * SPARKLINE_VERTICAL_RANGE;
  const points = history.map(point => ({
    timestamp: optionalNumber(point?.timestamp),
    jitter: optionalNumber(point?.ms),
  })).filter(point => point.timestamp != null);
  return `
    <div class="rate-trend" role="img" aria-label="Jitter-Verlauf der letzten 60 Sekunden">
      <span class="rate-trend-label">Jitter-Verlauf</span>
      <span class="sparkline-plot">
        <span class="rate-scale-max">${escapeHtml(formatNumber(maximum, 2))} ms</span>
        <svg class="sparkline-graph" viewBox="0 0 240 24" preserveAspectRatio="none" aria-hidden="true">
          <line class="sparkline-time-marker" x1="120" y1="2" x2="120" y2="22"></line>
          <line class="sparkline-baseline" x1="0" y1="22" x2="240" y2="22"></line>
          ${renderTrendSeries(points, "jitter", "trend-rate", xPosition, yPosition)}
        </svg>
      </span>
    </div>
  `;
}
