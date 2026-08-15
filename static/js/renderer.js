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

/** Format the age of the last successful collector snapshot. */
export function formatDataAge(collectedAt, nowMs = Date.now()) {
  const timestamp = optionalNumber(collectedAt);
  const currentTime = optionalNumber(nowMs);
  if (timestamp == null || currentTime == null) return null;
  const ageSeconds = Math.max(0, currentTime / 1000 - timestamp);
  return `Datenalter: ${ageSeconds.toFixed(1)} s`;
}

/** Classify snapshot freshness without assessing server or stream health. */
export function dataAgeStatusClass(collectedAt, nowMs = Date.now()) {
  const timestamp = optionalNumber(collectedAt);
  const currentTime = optionalNumber(nowMs);
  if (timestamp == null || currentTime == null) return "data-age-unknown";
  const ageSeconds = Math.max(0, currentTime / 1000 - timestamp);
  if (ageSeconds < 3) return "data-age-fresh";
  if (ageSeconds <= 10) return "data-age-warning";
  return "data-age-stale";
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

function metric(label, value, unit = null, assessment = null, valueClass = null) {
  return value == null ? null : {label, value, unit, assessment, valueClass};
}

function metricFullRow(content) {
  return content ? {kind: "full-row", content} : null;
}

function renderMetrics(metrics) {
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
            ${item.unit == null
              ? ""
              : `<span class="metric-unit">${escapeHtml(item.unit)}</span>`}
          </dt>
          <dd${item.valueClass ? ` class="${escapeHtml(item.valueClass)}"` : ""}>${escapeHtml(item.value)}</dd>
          ${item.assessment || ""}
        </div>
        `}
      `).join("")}
    </dl>
  `;
}

function renderConnectionHeading(type, details) {
  const remote = details?.remoteAddr || "—";
  return `
    <div class="connection-heading">
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

const TELEMETRY_WINDOW_SECONDS = 60;
const TREND_SCALE_HEADROOM = 1.15;
const TREND_SCALE_MINIMUM_MS = 100;
const VARIATION_SCALE_MINIMUM_MS = 50;
const SPARKLINE_BASELINE_Y = 22;
const SPARKLINE_VERTICAL_RANGE = 20;
const telemetryHistories = new Map();
let trendScaleState = {
  requiredMaximum: 0,
  scaleMaximum: TREND_SCALE_MINIMUM_MS,
  lowerRequiredSince: null,
};
let variationScaleState = {
  requiredMaximum: 0,
  scaleMaximum: VARIATION_SCALE_MINIMUM_MS,
  lowerRequiredSince: null,
};

function connectionTelemetryKey(pathName, role, connection) {
  const connectionId = connection?.id;
  if (!pathName || !connection?.type || !connectionId) return null;
  return `${pathName}:${role}:${connection.type}:${connectionId}`;
}

function connectionTimingValues(connection) {
  const timing = connection?.window_metrics?.timing || {};
  const current = connection?.type === "srtConn"
    ? firstAvailable(
      connection?.transport_rtt_ms,
      connection?.srt_health?.rtt_ms,
      connection?.details?.msRTT,
    )
    : pingValue(connection);
  return {
    current: optionalNumber(current),
    variation10: optionalNumber(timing["10s"]?.variation_ms),
    variation60: optionalNumber(timing["60s"]?.variation_ms),
  };
}

function recordConnectionTelemetry(key, connection, timestamp) {
  if (!key) return;
  const values = connectionTimingValues(connection);
  if (
    values.current == null
    && values.variation10 == null
    && values.variation60 == null
  ) return;
  const history = telemetryHistories.get(key) || [];
  if (history.some(point => point.timestamp === timestamp)) return;
  history.push({timestamp, ...values});
  history.sort((left, right) => left.timestamp - right.timestamp);
  telemetryHistories.set(
    key,
    history.filter(point => point.timestamp > timestamp - TELEMETRY_WINDOW_SECONDS),
  );
}

function activeTelemetryMaximum(fields) {
  let maximum = 0;
  for (const history of telemetryHistories.values()) {
    for (const point of history) {
      for (const field of fields) {
        const value = point[field];
        if (value != null) maximum = Math.max(maximum, value);
      }
    }
  }
  return maximum;
}

function updatedScaleState(state, requiredMaximum, minimum, timestamp) {
  if (requiredMaximum >= state.requiredMaximum) {
    return {
      requiredMaximum,
      scaleMaximum: Math.max(requiredMaximum * TREND_SCALE_HEADROOM, minimum),
      lowerRequiredSince: null,
    };
  }
  const lowerRequiredSince = state.lowerRequiredSince ?? timestamp;
  if (timestamp - lowerRequiredSince >= TELEMETRY_WINDOW_SECONDS) {
    return {
      requiredMaximum,
      scaleMaximum: Math.max(requiredMaximum * TREND_SCALE_HEADROOM, minimum),
      lowerRequiredSince: null,
    };
  }
  return {...state, lowerRequiredSince};
}

function updateSharedTrendScales(timestamp) {
  trendScaleState = updatedScaleState(
    trendScaleState,
    activeTelemetryMaximum(["current"]),
    TREND_SCALE_MINIMUM_MS,
    timestamp,
  );
  variationScaleState = updatedScaleState(
    variationScaleState,
    activeTelemetryMaximum(["variation10", "variation60"]),
    VARIATION_SCALE_MINIMUM_MS,
    timestamp,
  );
}

function trendYPosition(value) {
  const normalized = Math.sqrt(Math.max(0, value))
    / Math.sqrt(trendScaleState.scaleMaximum);
  return SPARKLINE_BASELINE_Y
    - Math.max(0, Math.min(1, normalized)) * SPARKLINE_VERTICAL_RANGE;
}

function variationYPosition(value) {
  const normalized = Math.max(0, value) / variationScaleState.scaleMaximum;
  return SPARKLINE_BASELINE_Y
    - Math.max(0, Math.min(1, normalized)) * SPARKLINE_VERTICAL_RANGE;
}

/** Record one API snapshot without duplicating an already seen collected_at. */
export function recordSnapshotTelemetry(streams, collectedAt) {
  const timestamp = optionalNumber(collectedAt);
  if (timestamp == null) return;
  const activeKeys = new Set();
  for (const stream of streams || []) {
    const publisherKey = connectionTelemetryKey(stream?.name, "publisher", stream?.source);
    if (publisherKey) {
      activeKeys.add(publisherKey);
      recordConnectionTelemetry(publisherKey, stream.source, timestamp);
    }
    for (const reader of stream?.readers || []) {
      const readerKey = connectionTelemetryKey(stream?.name, "reader", reader);
      if (!readerKey) continue;
      activeKeys.add(readerKey);
      recordConnectionTelemetry(readerKey, reader, timestamp);
    }
  }
  for (const key of telemetryHistories.keys()) {
    if (!activeKeys.has(key)) telemetryHistories.delete(key);
  }
  updateSharedTrendScales(timestamp);
}

/** Reset browser-local telemetry, used when the page reloads and by tests. */
export function resetTelemetryHistories() {
  telemetryHistories.clear();
  trendScaleState = {
    requiredMaximum: 0,
    scaleMaximum: TREND_SCALE_MINIMUM_MS,
    lowerRequiredSince: null,
  };
  variationScaleState = {
    requiredMaximum: 0,
    scaleMaximum: VARIATION_SCALE_MINIMUM_MS,
    lowerRequiredSince: null,
  };
}

/** Return a copy for focused frontend lifecycle tests. */
export function telemetryHistoryFor(pathName, role, connection) {
  const key = connectionTelemetryKey(pathName, role, connection);
  return key ? [...(telemetryHistories.get(key) || [])] : [];
}

/** Expose the shared graphical scale for deterministic renderer tests. */
export function telemetryScaleState() {
  return {
    trend: {...trendScaleState},
    variation: {...variationScaleState},
  };
}

/** Map a raw millisecond value through the shared compressed graph scale. */
export function telemetryTrendY(value) {
  const number = optionalNumber(value);
  return number == null ? null : trendYPosition(number);
}

/** Map a raw variation value through the shared linear variation scale. */
export function telemetryVariationY(value) {
  const number = optionalNumber(value);
  return number == null ? null : variationYPosition(number);
}

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

function renderRttTrend(connection, historyKey) {
  const history = telemetryHistories.get(historyKey) || [];
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
  const timingLabel = connection?.window_metrics?.timing_source === "icmp_rtt_ms"
    ? "Ping"
    : "RTT";
  const currentValues = connectionTimingValues(connection);
  const rows = [
    [timingLabel, "current", "trend-current", trendYPosition, trendScaleState.scaleMaximum],
    ["Var 10s", "variation10", "trend-variation-10", variationYPosition,
      variationScaleState.scaleMaximum],
    ["Var 60s", "variation60", "trend-variation-60", variationYPosition,
      variationScaleState.scaleMaximum],
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

function renderSrtMetrics(connection, direction, totalBytes, historyKey = null) {
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

function renderNonSrtMetrics(connection, direction, totalBytes, historyKey = null) {
  const details = connection?.details || {};
  const type = connection?.type;
  const rateLabel = direction === "in" ? "RX" : "TX";
  const rate = connectionRate(connection, direction);
  const ping = pingValue(connection);
  const linkTelemetry = renderLinkTelemetry(connection, historyKey);
  const metrics = [
    metric(rateLabel, rate == null
      ? "—"
      : formatNumber(rate, 2), "Mbit/s"),
    metric("Total", formatBytes(totalBytes)),
    metric(
      "Ping",
      ping == null && linkTelemetry ? "—" : formatNumber(ping, 2),
      "ms",
    ),
    metricFullRow(linkTelemetry),
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
  const historyKey = connectionTelemetryKey(
    stream?.name,
    direction === "in" ? "publisher" : "reader",
    connection,
  );
  return connection?.type === "srtConn"
    ? renderSrtMetrics(connection, direction, totalBytes, historyKey)
    : renderNonSrtMetrics(connection, direction, totalBytes, historyKey);
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
export function renderReader(reader, index = 0, streamName = "") {
  return `
    <section class="reader-block">
      <h3>Reader ${index + 1}</h3>
      ${renderConnectionHeading(reader?.type, reader?.details || {})}
      ${renderConnectionMetrics(reader, "out", {name: streamName})}
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
      ? readers.map((reader, index) => renderReader(reader, index, stream?.name)).join("")
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
