import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";


const rendererSource = await readFile(
  new URL("../static/js/renderer.js", import.meta.url),
  "utf8",
);
const rendererStyles = await readFile(
  new URL("../static/css/style.css", import.meta.url),
  "utf8",
);
const {
  dataAgeStatusClass,
  formatDataAge,
  formatRelativeTime,
  recordSnapshotTelemetry,
  renderReader,
  renderSrtHealth,
  renderStreamCard,
  renderStreamLeft,
  resetTelemetryHistories,
  telemetryHistoryFor,
  telemetryScaleState,
  telemetryTrendY,
  telemetryVariationY,
} = await import(`data:text/javascript;base64,${Buffer.from(rendererSource).toString("base64")}`);

assert.doesNotMatch(rendererSource, /protocol-marker|marker-srt|marker-rtmp/);
assert.doesNotMatch(rendererStyles, /protocol-marker|marker-srt|marker-rtmp/);

function assertMetric(html, label, value, unit = null) {
  const escaped = text => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const unitMarkup = unit == null
    ? ""
    : `\\s*<span class="metric-unit">${escaped(unit)}</span>`;
  const expression = new RegExp(
    `<dt>\\s*<span class="metric-label">${escaped(label)}</span>${unitMarkup}\\s*</dt>`
      + `\\s*<dd(?: [^>]*)?>${escaped(value)}</dd>`,
  );
  assert.match(html, expression);
}

function assertRttLatencyRelation(
  html,
  status,
  percentageLabel,
  fillPercentage,
  multiplierLabel,
) {
  const escapedLabel = percentageLabel.replace("<", "&lt;");
  const description = `RTT / SRT-Latency: ${escapedLabel}; `
    + `SRT-Latency entspricht ${multiplierLabel} RTT`;
  assert.match(html, new RegExp(
    `class="srt-rtt-assessment srt-rtt-${status}"[\\s\\S]*`
      + `aria-label="${description}"[\\s\\S]*`
      + `title="${description}"[\\s\\S]*`
      + `style="width: ${fillPercentage}%"[\\s\\S]*`
      + `<span class="srt-rtt-percentage">${escapedLabel}<\\/span>`,
  ));
}

function assertSparklineValue(html, rowClass, label, value, hasUnit = true) {
  const escaped = text => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const unitMarkup = hasUnit
    ? '<span class="sparkline-unit">ms<\\/span>'
    : "";
  assert.match(html, new RegExp(
    `class="sparkline-row sparkline-${escaped(rowClass)}"[\\s\\S]*?`
      + `class="sparkline-label">${escaped(label)}<\\/span>[\\s\\S]*?`
      + `class="sparkline-number">${escaped(value)}<\\/span>${unitMarkup}`,
  ));
}

function assertSrtImpact(html, status, label, detail) {
  assert.match(html, new RegExp(
    `class="srt-impact srt-impact-${status}"[\\s\\S]*?`
      + `aria-label="SRT Impact ${label}: ${detail}"[\\s\\S]*?`
      + `<span class="srt-impact-status">${label}<\\/span>[\\s\\S]*?`
      + `<div class="srt-impact-detail">${detail}<\\/div>`,
  ));
}


const srtPublisherStream = {
  name: "camera/srt",
  inboundBytes: 8192,
  source: {
    id: "publisher-a",
    type: "srtConn",
    bitrate_mbps: 3.75,
    transport_rtt_ms: 24,
    details: {
      remoteAddr: "192.0.2.3:9000",
      bytesReceived: 4096,
      msSendTsbPdDelay: 9999,
      packetsReceivedLossRate: 0,
      created: "2020-01-01T00:00:00Z",
    },
    srt_latency_ms: 2000,
    srt_health: {
      link_capacity_mbps: 12.5,
      retrans_packets: 0,
      drop_packets: 0,
      undecrypt_packets: 0,
    },
    window_metrics: {
      timing_source: "transport_rtt_ms",
      timing: {
        "10s": {sample_count: 3, p50_ms: 22, p95_ms: 28, variation_ms: 6},
        "60s": {sample_count: 17, p50_ms: 20, p95_ms: 30, variation_ms: 10},
      },
      p50_delta_ms: 2,
      events: {
        "10s": {
          retrans_packets: 0,
          loss_packets: 1,
          drop_packets: 0,
          belated_packets: 3,
          undecrypt_packets: 0,
        },
        "60s": {
          retrans_packets: 0,
          loss_packets: 4,
          drop_packets: 1,
          belated_packets: 7,
          undecrypt_packets: 2,
        },
      },
    },
  },
};
resetTelemetryHistories();
recordSnapshotTelemetry([srtPublisherStream], 1000);
recordSnapshotTelemetry([srtPublisherStream], 1001);
const srtPublisher = renderStreamLeft(srtPublisherStream);

assert.match(srtPublisher, /<h2 class="panel-title">IN<\/h2>/);
assert.match(srtPublisher, /SRT/);
assert.match(srtPublisher, /192\.0\.2\.3:9000/);
assertMetric(srtPublisher, "RX", "3.75", "Mbit/s");
assertMetric(srtPublisher, "Total", "4.00 KB");
assertMetric(srtPublisher, "RTT", "24.00", "ms");
assertMetric(srtPublisher, "Rcv Latency", "2000", "ms");
assertRttLatencyRelation(srtPublisher, "good", "1%", 3, "83.3×");
assert.doesNotMatch(srtPublisher, /9999/);
assertMetric(srtPublisher, "Rcv Loss Rate", "0.00", "%");
assertMetric(srtPublisher, "SRT est. Link", "12.5", "Mbit/s");
assert.doesNotMatch(srtPublisher, /Reserve/);
assert.doesNotMatch(srtPublisher, /Ping/);
assert.doesNotMatch(srtPublisher, /H\.264|Video:/);
assert.match(srtPublisher, /class="trend-line trend-current"/);
assert.match(srtPublisher, /class="trend-line trend-variation-10"/);
assert.match(srtPublisher, /class="trend-line trend-variation-60"/);
assert.equal((srtPublisher.match(/class="sparkline-row /g) || []).length, 3);
assert.equal((srtPublisher.match(/viewBox="0 0 240 24"/g) || []).length, 3);
assert.equal((srtPublisher.match(/class="sparkline-time-marker"/g) || []).length, 3);
assert.equal((srtPublisher.match(/class="trend-end-marker /g) || []).length, 3);
assert.match(srtPublisher, /class="sparkline-scale-max">100 ms/);
assert.equal((srtPublisher.match(/class="sparkline-scale-max">50 ms/g) || []).length, 2);
assert.match(srtPublisher, /class="sparkline-label">Var 10s/);
assert.match(srtPublisher, /class="sparkline-label">Var 60s/);
assertSparklineValue(srtPublisher, "current", "RTT", "24.0");
assertSparklineValue(srtPublisher, "variation10", "Var 10s", "6.0");
assertSparklineValue(srtPublisher, "variation60", "Var 60s", "10.0");
assert.match(srtPublisher, /class="metric-full-row"/);
assertSrtImpact(
  srtPublisher,
  "crit",
  "CRIT",
  "Rcv Loss 10s 1 · 60s 4 · Drop 60s 1 · Belated 10s 3 · 60s 7 · Undecrypt 60s 2",
);
assert.doesNotMatch(srtPublisher, /window-metrics|RTT 10 s|RTT 60 s|Events 10 s|p50 Δ|>Variation</);

const srtReaderData = {
  id: "reader-a",
  type: "srtConn",
  details: {
    remoteAddr: "192.0.2.1:9000",
    bytesSent: 999999,
    msReceiveTsbPdDelay: 8888,
    packetsSendLossRate: 0,
    outboundFramesDiscarded: 6,
    created: "2020-01-01T00:00:00Z",
  },
  srt_latency_ms: 1500,
  bitrate_mbps: 9.99,
  srt_health: {
    tx_mbps: 4.25,
    link_capacity_mbps: 11.4,
    rtt_ms: 31,
    retrans_packets: 2,
    drop_packets: 0,
  },
  window_metrics: {
    timing_source: "transport_rtt_ms",
    timing: {
      "10s": {sample_count: 1, p50_ms: 31, p95_ms: 31, variation_ms: 0},
      "60s": {sample_count: 5, p50_ms: 30, p95_ms: 33, variation_ms: 3},
    },
    p50_delta_ms: 1,
    events: {
      "10s": {
        retrans_packets: 2, loss_packets: 0, drop_packets: 4,
      },
      "60s": {retrans_packets: 6, loss_packets: 1, drop_packets: 4},
    },
  },
};
resetTelemetryHistories();
recordSnapshotTelemetry([{
  name: "camera/srt",
  source: {},
  readers: [srtReaderData],
}], 2000);
recordSnapshotTelemetry([{
  name: "camera/srt",
  source: {},
  readers: [srtReaderData],
}], 2001);
const srtReader = renderReader(srtReaderData, 0, "camera/srt");

assert.match(srtReader, /Reader 1/);
assertMetric(srtReader, "TX", "4.25", "Mbit/s");
assertMetric(srtReader, "RTT", "31.00", "ms");
assertMetric(srtReader, "Snd Latency", "1500", "ms");
assertRttLatencyRelation(srtReader, "good", "2%", 5.17, "48.4×");
assert.doesNotMatch(srtReader, /8888/);
assertMetric(srtReader, "Send Loss Rate", "0.00", "%");
assertMetric(srtReader, "SRT est. Link", "11.4", "Mbit/s");
assertMetric(srtReader, "Frame Discard", "6");
assert.doesNotMatch(srtReader, /Reserve/);
assert.doesNotMatch(srtReader, /Ping/);
assert.doesNotMatch(srtReader, /9\.99/);
assert.match(srtReader, /class="trend-line trend-current"/);
assert.match(srtReader, /class="trend-line trend-variation-10"/);
assert.match(srtReader, /class="trend-line trend-variation-60"/);
assert.equal((srtReader.match(/class="sparkline-row /g) || []).length, 3);
assert.equal((srtReader.match(/viewBox="0 0 240 24"/g) || []).length, 3);
assertSparklineValue(srtReader, "current", "RTT", "31.0");
assertSparklineValue(srtReader, "variation10", "Var 10s", "0.0");
assertSparklineValue(srtReader, "variation60", "Var 60s", "3.0");
assertSrtImpact(
  srtReader,
  "crit",
  "CRIT",
  "Send Loss 60s 1 · Retrans 10s 2 · 60s 6 · Send Drop 10s 4 · 60s 4",
);
assert.doesNotMatch(srtReader, /impact-belated|impact-undecrypt|>Belated<|>Undecrypt</);
assert.doesNotMatch(srtReader, /window-metrics|RTT 10 s|RTT 60 s|Events 60 s|p50 Δ|>Variation</);
assert.doesNotMatch(srtReader, /STABLE|VARIABLE|UNSTABLE|DEGRADED|CRITICAL/);

const nullRate = renderStreamLeft({
  source: {type: "rtmpConn", bitrate_mbps: null, details: {}},
});
assertMetric(nullRate, "RX", "—", "Mbit/s");
assert.doesNotMatch(nullRate, /<dd>0\.00<\/dd>/);

const measuredZeroRate = renderStreamLeft({
  source: {type: "rtmpConn", bitrate_mbps: 0, details: {}},
});
assertMetric(measuredZeroRate, "RX", "0.00", "Mbit/s");

const rtspPublisherStream = {
  name: "camera/rtsp",
  source: {
    id: "rtsp-publisher-a",
    type: "rtspSession",
    bitrate_mbps: 5.2,
    details: {
      remoteAddr: "192.0.2.10:8554",
      inboundBytes: 2048,
      inboundRTPPacketsLost: 0,
      inboundRTPPacketsJitter: 3.4,
      inboundRTPPacketsInError: 0,
    },
    protocol_metrics: {gauges: {jitter_ms: 3.4}, metadata: {transport: "udp"}},
    window_metrics: {protocol_counters: {
      "10s": {loss: 0, rtp_error: 0},
      "60s": {loss: 0, rtp_error: 0},
    }},
  },
};
resetTelemetryHistories();
recordSnapshotTelemetry([rtspPublisherStream], 3000);
recordSnapshotTelemetry([rtspPublisherStream], 3001);
const rtspPublisher = renderStreamLeft(rtspPublisherStream);
assert.match(rtspPublisher, /RTSP\/UDP/);
assertMetric(rtspPublisher, "Jitter", "3.40", "ms");
assertMetric(rtspPublisher, "Loss", "10s 0 · 60s 0", "pkt");
assert.doesNotMatch(rtspPublisher, /metric-label">RTT|Ping|rtt-trend/);
assert.doesNotMatch(rtspPublisher, /trend-variation-60|srt-impact|srt-rtt-assessment/);

const rtspReader = renderReader({
  id: "rtsp-reader-a",
  type: "rtspSession",
  bitrate_mbps: 4.8,
  details: {
    remoteAddr: "192.0.2.11:8554",
    outboundBytes: 4096,
    outboundRTPPacketsReportedLost: 2,
    outboundRTPPacketsDiscarded: 0,
  },
  window_metrics: {protocol_counters: {
    "10s": {reported_loss: 2, discard: 0},
    "60s": {reported_loss: 2, discard: 0},
  }},
}, 1);
assert.match(rtspReader, /Reader 2/);
assertMetric(rtspReader, "Reported Loss", "10s 2 · 60s 2", "pkt");
assertMetric(rtspReader, "Discard", "10s 0 · 60s 0");
assert.doesNotMatch(rtspReader, /metric-label">RTT|Ping|Jitter|Retrans|rtt-trend/);

const rtmpReader = renderReader({
  id: "rtmp-reader-a",
  type: "rtmpConn",
  bitrate_mbps: 2.5,
  details: {
    remoteAddr: "192.0.2.4:1935",
    outboundBytes: 1024,
    outboundFramesDiscarded: 0,
  },
  rate_history: [
    {timestamp: 100, mbps: 2.5},
    {timestamp: 110, mbps: 0},
    {timestamp: 120, mbps: null},
    {timestamp: 130, mbps: 3.0},
  ],
  window_metrics: {frame_discard: {"10s": 18, "60s": 21}},
  connection_stability: {
    changes_60s: 1,
    seconds_since_last_change: 18,
  },
}, 0);
assertMetric(rtmpReader, "TX", "2.50", "Mbit/s");
assertMetric(rtmpReader, "Frame Discard", "10s 18 · 60s 21");
assertMetric(rtmpReader, "Connection", "changed 18 s ago");
assert.match(rtmpReader, /aria-label="TX-Verlauf der letzten 60 Sekunden"/);
assert.match(rtmpReader, /class="trend-line trend-rate"/);
assert.equal((rtmpReader.match(/class="trend-end-marker trend-rate"/g) || []).length, 1);
assert.doesNotMatch(rtmpReader, /RTT|Ping|Loss|Retrans|Link|Reserve/);

const rtmpsPublisherTrend = renderStreamLeft({
  name: "secure",
  source: {
    id: "rtmps-publisher",
    type: "rtmpsConn",
    bitrate_mbps: 4.5,
    details: {remoteAddr: "192.0.2.8:1936", inboundBytes: 2048},
    rate_history: [
      {timestamp: 100, mbps: null},
      {timestamp: 101, mbps: 4.5},
      {timestamp: 102, mbps: 4.2},
    ],
    connection_stability: {changes_60s: 0, seconds_since_last_change: null},
  },
});
assert.match(rtmpsPublisherTrend, /aria-label="RX-Verlauf der letzten 60 Sekunden"/);
assertMetric(rtmpsPublisherTrend, "Connection", "stable");

for (const connection of [
  {type: "srtConn", rate_history: [{timestamp: 1, mbps: 3}], details: {}},
  {type: "rtspSession", rate_history: [{timestamp: 1, mbps: 3}], details: {}},
]) {
  assert.doesNotMatch(renderReader(connection), /TX-Verlauf|trend-rate/);
}

const unavailableRtmpReader = renderReader({
  type: "rtmpConn",
  details: {remoteAddr: "192.0.2.5:1935"},
}, 0);
assert.doesNotMatch(unavailableRtmpReader, /Ping|0\.00 ms|RTT/);

const hlsReader = renderReader({
  type: "hlsSession",
  bitrate_mbps: null,
  details: {
    remoteAddr: "192.0.2.20:49152",
    outboundBytes: 0,
    userAgent: "Field Player/1.0",
    isCDN: false,
  },
}, 0);
assertMetric(hlsReader, "TX aktuell", "—", "Mbit/s");
assertMetric(hlsReader, "Total", "0 B");
assert.match(hlsReader, /Agent: Field Player\/1\.0/);
assert.match(hlsReader, /CDN: nein/);
assert.doesNotMatch(hlsReader, /RTT|Ping|Loss|Jitter/);
assert.doesNotMatch(hlsReader, /Latency/);

const averagedHlsReader = renderReader({
  type: "hlsSession",
  bitrate_mbps: 4.69,
  common: {direction: "OUT", remoteAddr: "192.0.2.21:49153", total_bytes: 2048},
  details: {created: "2026-08-16T00:00:00Z"},
  rate_metrics: {"10s": {average_mbps: 4.12, sample_count: 8}},
});
assertMetric(averagedHlsReader, "TX Ø10s", "4.12", "Mbit/s");
assert.match(averagedHlsReader, /title="Aktuell: 4\.69 Mbit\/s"/);
assert.doesNotMatch(averagedHlsReader, /Mux Discard|Last Request/);
assert.equal(formatRelativeTime("2026-08-16T20:08:22Z", Date.parse("2026-08-16T20:08:23Z")), "vor 1 s");
assert.equal(formatRelativeTime("2026-08-16T20:07:00Z", Date.parse("2026-08-16T20:08:23Z")), "vor 1 min");

const webRtcPublisher = renderStreamLeft({
  name: "whip",
  source: {
    type: "webRTCSession",
    common: {remoteAddr: "192.0.2.30:5000", rx_mbit_s: 3.2, total_bytes: 4096},
    details: {},
    protocol_metrics: {
      gauges: {jitter_ms: 2.25},
      metadata: {
        peer_connection_established: true,
        local_candidate: {type: "host", protocol: "udp", address: "10.0.0.1", port: 5000},
        remote_candidate: {type: "srflx", protocol: "udp", address: "192.0.2.30", port: 5001},
      },
    },
    jitter_history: [{timestamp: 1, ms: 1.5}, {timestamp: 2, ms: 2.25}],
    window_metrics: {protocol_counters: {
      "10s": {rtp_loss: 1}, "60s": {rtp_loss: 3},
    }},
  },
  path_metrics: {window_metrics: {protocol_counters: {
    "10s": {frame_error: 2}, "60s": {frame_error: 4},
  }}},
});
assertMetric(webRtcPublisher, "Jitter", "2.25", "ms");
assertMetric(webRtcPublisher, "RTP Loss", "10s 1 · 60s 3", "pkt");
assertMetric(webRtcPublisher, "Peer", "established");
assertMetric(webRtcPublisher, "Path Frame Error", "10s 2 · 60s 4");
assert.match(webRtcPublisher, /host · UDP · 10\.0\.0\.1:5000/);
assert.match(webRtcPublisher, /aria-label="Jitter-Verlauf der letzten 60 Sekunden"/);
assert.doesNotMatch(webRtcPublisher, /metric-label">RTT|SRT Impact/);

const webRtcReader = renderReader({
  type: "webRTCSession",
  common: {remoteAddr: "192.0.2.31:5002", tx_mbit_s: 2.1, total_bytes: 2048},
  details: {},
  protocol_metrics: {metadata: {peer_connection_established: true}},
  window_metrics: {protocol_counters: {
    "10s": {frame_discard: 2}, "60s": {frame_discard: 5},
  }},
});
assertMetric(webRtcReader, "Frame Discard", "10s 2 · 60s 5");
assert.doesNotMatch(webRtcReader, /Jitter|Loss|RTT/);

const icePair = renderReader({
  type: "webRTCSession",
  details: {},
  protocol_metrics: {metadata: {
    local_candidate: "host/udp/127.0.0.1/8189",
    remote_candidate: {type: "srflx", protocol: "tcp", address: "10.77.0.1", port: 54321},
  }},
});
assertMetric(
  icePair,
  "ICE",
  "host · UDP · 127.0.0.1:8189 ↔ srflx · TCP · 10.77.0.1:54321",
);
assert.equal((icePair.match(/↔/g) || []).length, 1);

const iceLocalOnly = renderReader({
  type: "webRTCSession",
  details: {},
  protocol_metrics: {metadata: {
    local_candidate: "relay/udp/127.0.0.1/8189",
    remote_candidate: "",
  }},
});
assertMetric(iceLocalOnly, "ICE Local", "relay · UDP · 127.0.0.1:8189");
assert.doesNotMatch(iceLocalOnly, /↔/);

const iceRemoteOnly = renderReader({
  type: "webRTCSession",
  details: {},
  protocol_metrics: {metadata: {
    local_candidate: {},
    remote_candidate: {type: "host", protocol: "udp", ip: "10.77.0.1", port: 54321},
  }},
});
assertMetric(iceRemoteOnly, "ICE Remote", "host · UDP · 10.77.0.1:54321");
assert.doesNotMatch(iceRemoteOnly, /↔/);

const noIceCandidate = renderReader({
  type: "webRTCSession",
  details: {},
  protocol_metrics: {metadata: {}},
});
assert.doesNotMatch(noIceCandidate, /metric-label">ICE|↔/);

const moqReader = renderReader({
  type: "moqSession",
  common: {remoteAddr: "192.0.2.40:4443", tx_mbit_s: 1.5, total_bytes: 1024},
  details: {},
  protocol_metrics: {metadata: {
    transport: "quic", version: "draft-01", state: "read",
  }},
});
assertMetric(moqReader, "Transport", "quic");
assertMetric(moqReader, "Version", "draft-01");
assertMetric(moqReader, "State", "read");
assert.doesNotMatch(moqReader, /RTT|Jitter|Loss/);

const missingSrtLatency = renderReader({
  type: "srtConn",
  srt_latency_ms: null,
  details: {msSendTsbPdDelay: null},
});
assert.doesNotMatch(missingSrtLatency, /Latency/);
assert.doesNotMatch(missingSrtLatency, /srt-rtt-assessment/);
assert.doesNotMatch(missingSrtLatency, /rtt-trend|srt-impact/);

const partialReader = {
  id: "partial-reader",
  type: "srtConn",
  details: {},
  window_metrics: {
    timing_source: "transport_rtt_ms",
    timing: {"10s": {sample_count: 1, variation_ms: 5}},
    events: {
      "10s": {retrans_packets: null, drop_packets: 0},
      "60s": {retrans_packets: null, drop_packets: 0},
    },
  },
};
resetTelemetryHistories();
recordSnapshotTelemetry([{name: "partial", source: {}, readers: [partialReader]}], 4000);
const partialHistory = renderReader(partialReader, 0, "partial");
assert.match(partialHistory, /class="trend-end-marker trend-variation-10"/);
assert.doesNotMatch(partialHistory, /trend-variation-60|trend-current/);
assertSparklineValue(partialHistory, "current", "RTT", "—", false);
assertSparklineValue(partialHistory, "variation10", "Var 10s", "5.0");
assertSparklineValue(partialHistory, "variation60", "Var 60s", "—", false);
assertSrtImpact(partialHistory, "unavailable", "—", "10s — · 60s —");
assert.doesNotMatch(partialHistory, /impact-belated|impact-undecrypt/);
assert.doesNotMatch(partialHistory, /p50|p95|>Variation</);

function renderEventStates(direction, events) {
  const connection = {
    id: "event-reader",
    type: "srtConn",
    transport_rtt_ms: 10,
    details: {},
    window_metrics: {events},
  };
  return direction === "in"
    ? renderStreamLeft({name: "events", source: connection})
    : renderReader(connection, 0, "events");
}

const clearInEvents = renderEventStates("in", {
  "10s": {
    loss_packets: 0, retrans_packets: 0, drop_packets: 0,
    belated_packets: 0, undecrypt_packets: 0,
  },
  "60s": {
    loss_packets: 0, retrans_packets: 0, drop_packets: 0,
    belated_packets: 0, undecrypt_packets: 0,
  },
});
assertSrtImpact(clearInEvents, "ok", "OK", "10s OK · 60s OK");

const retransWarningIn = renderEventStates("in", {
  "10s": {loss_packets: 0, retrans_packets: 8, drop_packets: 0,
    belated_packets: 0, undecrypt_packets: 0},
  "60s": {loss_packets: 0, retrans_packets: 31, drop_packets: 0,
    belated_packets: 0, undecrypt_packets: 0},
});
assertSrtImpact(retransWarningIn, "warn", "WARN", "Retrans 10s 8 · 60s 31");
assert.doesNotMatch(retransWarningIn, /Rcv Loss 10s|Drop 10s|Belated 10s|Undecrypt 10s/);

const lossWarningIn = renderEventStates("in", {
  "10s": {loss_packets: 3, retrans_packets: 0, drop_packets: 0,
    belated_packets: 0, undecrypt_packets: 0},
  "60s": {loss_packets: 9, retrans_packets: 0, drop_packets: 0,
    belated_packets: 0, undecrypt_packets: 0},
});
assertSrtImpact(lossWarningIn, "warn", "WARN", "Rcv Loss 10s 3 · 60s 9");

for (const [field, label] of [
  ["drop_packets", "Drop"],
  ["belated_packets", "Belated"],
  ["undecrypt_packets", "Undecrypt"],
]) {
  const criticalIn = renderEventStates("in", {
    "10s": {loss_packets: 0, retrans_packets: 0, drop_packets: 0,
      belated_packets: 0, undecrypt_packets: 0, [field]: 2},
    "60s": {loss_packets: 0, retrans_packets: 0, drop_packets: 0,
      belated_packets: 0, undecrypt_packets: 0, [field]: 5},
  });
  assertSrtImpact(criticalIn, "crit", "CRIT", `${label} 10s 2 · 60s 5`);
}

const recentCriticalIn = renderEventStates("in", {
  "10s": {loss_packets: 0, retrans_packets: 0, drop_packets: 0,
    belated_packets: 0, undecrypt_packets: 0},
  "60s": {loss_packets: 0, retrans_packets: 0, drop_packets: 2,
    belated_packets: 5, undecrypt_packets: 0},
});
assertSrtImpact(
  recentCriticalIn,
  "recent",
  "RECENT",
  "10s OK · Drop 60s 2 · Belated 60s 5",
);
assert.doesNotMatch(recentCriticalIn, /srt-impact-crit/);

const clearOutEvents = renderEventStates("out", {
  "10s": {loss_packets: 0, retrans_packets: 0, drop_packets: 0},
  "60s": {loss_packets: 0, retrans_packets: 0, drop_packets: 0},
});
assertSrtImpact(clearOutEvents, "ok", "OK", "10s OK · 60s OK");

const warningOutEvents = renderEventStates("out", {
  "10s": {loss_packets: 2, retrans_packets: 4, drop_packets: 0},
  "60s": {loss_packets: 7, retrans_packets: 12, drop_packets: 0},
});
assertSrtImpact(
  warningOutEvents,
  "warn",
  "WARN",
  "Send Loss 10s 2 · 60s 7 · Retrans 10s 4 · 60s 12",
);

const criticalOutEvents = renderEventStates("out", {
  "10s": {loss_packets: 0, retrans_packets: 0, drop_packets: 2},
  "60s": {loss_packets: 0, retrans_packets: 0, drop_packets: 5},
});
assertSrtImpact(criticalOutEvents, "crit", "CRIT", "Send Drop 10s 2 · 60s 5");

const recentOutEvents = renderEventStates("out", {
  "10s": {loss_packets: 0, retrans_packets: 0, drop_packets: 0},
  "60s": {loss_packets: 0, retrans_packets: 0, drop_packets: 5},
});
assertSrtImpact(recentOutEvents, "recent", "RECENT", "10s OK · Send Drop 60s 5");
for (const outImpact of [clearOutEvents, warningOutEvents, criticalOutEvents, recentOutEvents]) {
  assert.doesNotMatch(outImpact, /Belated|Undecrypt/);
}

function telemetryStream(connectionId, current, variation10, variation60) {
  return {
    name: "ringbuffer",
    source: {
      id: connectionId,
      type: "srtConn",
      transport_rtt_ms: current,
      details: {},
      window_metrics: {
        timing_source: "transport_rtt_ms",
        timing: {
          "10s": {variation_ms: variation10},
          "60s": {variation_ms: variation60},
        },
      },
    },
    readers: [],
  };
}

resetTelemetryHistories();
const firstConnection = telemetryStream("connection-a", 10, 9, 8);
recordSnapshotTelemetry([firstConnection], 5000);
recordSnapshotTelemetry([telemetryStream("connection-a", 99, 98, 97)], 5000);
assert.equal(
  telemetryHistoryFor("ringbuffer", "publisher", firstConnection.source).length,
  1,
);
recordSnapshotTelemetry([telemetryStream("connection-a", 11, null, 8.5)], 5001);
let ringHistory = telemetryHistoryFor("ringbuffer", "publisher", firstConnection.source);
assert.equal(ringHistory.length, 2);
assert.equal(ringHistory[1].variation10, null);
recordSnapshotTelemetry([telemetryStream("connection-a", 12, 10, 9)], 5060);
ringHistory = telemetryHistoryFor("ringbuffer", "publisher", firstConnection.source);
assert.deepEqual(ringHistory.map(point => point.timestamp), [5001, 5060]);

const reconnected = telemetryStream("connection-b", 13, 11, 10);
recordSnapshotTelemetry([reconnected], 5061);
assert.equal(
  telemetryHistoryFor("ringbuffer", "publisher", firstConnection.source).length,
  0,
);
assert.equal(
  telemetryHistoryFor("ringbuffer", "publisher", reconnected.source).length,
  1,
);
assert.equal(telemetryScaleState().trend.requiredMaximum, 13);

resetTelemetryHistories();
recordSnapshotTelemetry([telemetryStream("gap", 10, 1, 2)], 5100);
recordSnapshotTelemetry([telemetryStream("gap", 11, 1, 2)], 5101);
recordSnapshotTelemetry([telemetryStream("gap", null, 1, 2)], 5102);
recordSnapshotTelemetry([telemetryStream("gap", 12, 1, 2)], 5103);
const gapStream = telemetryStream("gap", 13, 1, 2);
recordSnapshotTelemetry([gapStream], 5104);
const gapTrend = renderStreamLeft(gapStream);
assert.equal((gapTrend.match(/class="trend-line trend-current"/g) || []).length, 2);
assert.equal((gapTrend.match(/class="trend-end-marker trend-current"/g) || []).length, 1);

resetTelemetryHistories();
const sharedScaleSnapshot = {
  name: "shared-scale",
  source: {
    id: "lan",
    type: "srtConn",
    transport_rtt_ms: 1,
    details: {},
    window_metrics: {
      timing: {
        "10s": {variation_ms: 0.3},
        "60s": {variation_ms: 0.5},
      },
    },
  },
  readers: [{
    id: "wan",
    type: "srtConn",
    transport_rtt_ms: 90,
    details: {},
    window_metrics: {
      timing: {
        "10s": {variation_ms: 25},
        "60s": {variation_ms: 35},
      },
    },
  }],
};
recordSnapshotTelemetry([sharedScaleSnapshot], 6000);
assert.equal(telemetryScaleState().trend.requiredMaximum, 90);
assert.ok(Math.abs(telemetryScaleState().trend.scaleMaximum - 103.5) < 1e-9);
assert.equal(telemetryScaleState().variation.requiredMaximum, 35);
assert.equal(telemetryScaleState().variation.scaleMaximum, 50);
const lanY = telemetryTrendY(1);
const wanY = telemetryTrendY(90);
assert.ok(lanY > wanY + 9);
const lanHeight = 22 - lanY;
const wanHeight = 22 - wanY;
assert.ok(lanHeight / wanHeight > 0.08);
assert.ok(lanHeight / wanHeight < 0.12);
const lowVariationHeight = 22 - telemetryVariationY(0.5);
const mediumVariationHeight = 22 - telemetryVariationY(25);
const fullVariationHeight = 22 - telemetryVariationY(50);
assert.ok(lowVariationHeight <= 0.2);
assert.ok(mediumVariationHeight > lowVariationHeight + 9);
assert.ok(Math.abs(mediumVariationHeight / fullVariationHeight - 0.5) < 1e-9);

const peakSnapshot = structuredClone(sharedScaleSnapshot);
peakSnapshot.readers[0].transport_rtt_ms = 300;
peakSnapshot.readers[0].window_metrics.timing["10s"].variation_ms = 80;
peakSnapshot.readers[0].window_metrics.timing["60s"].variation_ms = 60;
recordSnapshotTelemetry([peakSnapshot], 6001);
assert.equal(telemetryScaleState().trend.requiredMaximum, 300);
assert.ok(Math.abs(telemetryScaleState().trend.scaleMaximum - 345) < 1e-9);
assert.equal(telemetryScaleState().variation.requiredMaximum, 80);
assert.ok(Math.abs(telemetryScaleState().variation.scaleMaximum - 92) < 1e-9);
assert.ok(telemetryTrendY(300) < telemetryTrendY(100) - 7);
assert.ok(telemetryVariationY(80) < telemetryVariationY(35) - 9);

const lanOnlySnapshot = structuredClone(sharedScaleSnapshot);
lanOnlySnapshot.readers = [];
recordSnapshotTelemetry([lanOnlySnapshot], 6002);
assert.ok(Math.abs(telemetryScaleState().trend.scaleMaximum - 345) < 1e-9);
assert.ok(Math.abs(telemetryScaleState().variation.scaleMaximum - 92) < 1e-9);
recordSnapshotTelemetry([lanOnlySnapshot], 6061);
assert.ok(Math.abs(telemetryScaleState().trend.scaleMaximum - 345) < 1e-9);
assert.ok(Math.abs(telemetryScaleState().variation.scaleMaximum - 92) < 1e-9);
recordSnapshotTelemetry([lanOnlySnapshot], 6062);
assert.equal(telemetryScaleState().trend.requiredMaximum, 1);
assert.equal(telemetryScaleState().trend.scaleMaximum, 100);
assert.equal(telemetryScaleState().variation.requiredMaximum, 0.5);
assert.equal(telemetryScaleState().variation.scaleMaximum, 50);

assert.equal(formatDataAge(1000, 1000400), "Datenalter: 0.4 s");
assert.equal(formatDataAge(1001, 1000000), "Datenalter: 0.0 s");
assert.equal(formatDataAge(null, 1000000), null);
assert.equal(formatDataAge("invalid", 1000000), null);
assert.equal(dataAgeStatusClass(997.1, 1000000), "data-age-fresh");
assert.equal(dataAgeStatusClass(997, 1000000), "data-age-warning");
assert.equal(dataAgeStatusClass(990, 1000000), "data-age-warning");
assert.equal(dataAgeStatusClass(989.9, 1000000), "data-age-stale");
assert.equal(dataAgeStatusClass(null, 1000000), "data-age-unknown");

const lowRttSrtIn = renderStreamLeft({
  source: {
    type: "srtConn",
    transport_rtt_ms: 70,
    srt_latency_ms: 2000,
    details: {},
  },
});
assert.doesNotMatch(lowRttSrtIn, /protocol-marker|marker-srt/);
assertMetric(lowRttSrtIn, "RTT", "70.00", "ms");
assertMetric(lowRttSrtIn, "Rcv Latency", "2000", "ms");
assertRttLatencyRelation(lowRttSrtIn, "good", "4%", 8.75, "28.6×");
assert.match(lowRttSrtIn, /<dd class="srt-rtt-good">2000<\/dd>/);

const mediumRttSrtOut = renderReader({
  type: "srtConn",
  srt_latency_ms: 2000,
  details: {msRTT: 600},
});
assertMetric(mediumRttSrtOut, "RTT", "600.00", "ms");
assertMetric(mediumRttSrtOut, "Snd Latency", "2000", "ms");
assertRttLatencyRelation(mediumRttSrtOut, "warning", "30%", 75, "3.3×");
assert.match(mediumRttSrtOut, /<dd class="srt-rtt-warning">2000<\/dd>/);

const highRttSrtOut = renderReader({
  type: "srtConn",
  srt_latency_ms: 2000,
  details: {msRTT: 900},
});
assertMetric(highRttSrtOut, "RTT", "900.00", "ms");
assertMetric(highRttSrtOut, "Snd Latency", "2000", "ms");
assertRttLatencyRelation(highRttSrtOut, "critical", "45%", 100, "2.2×");
assert.match(highRttSrtOut, /<dd class="srt-rtt-critical">2000<\/dd>/);

const multiplierBoundaries = [
  {multiplier: 4, status: "good", percentage: "25%", fill: 62.5},
  {multiplier: 3, status: "warning", percentage: "33%", fill: 83.33},
  {multiplier: 2.99, status: "critical", percentage: "33%", fill: 83.61},
];
for (const {multiplier, status, percentage, fill} of multiplierBoundaries) {
  const html = renderReader({
    type: "srtConn",
    srt_latency_ms: multiplier * 100,
    details: {msRTT: 100},
  });
  assertRttLatencyRelation(
    html,
    status,
    percentage,
    fill,
    `${multiplier.toFixed(1)}×`,
  );
}

for (const latency of [undefined, null, 0]) {
  const unavailableLatency = renderReader({
    type: "srtConn",
    srt_latency_ms: latency,
    details: {msRTT: 100},
  });
  assert.doesNotMatch(unavailableLatency, /srt-rtt-assessment/);
}

const missingRtt = renderReader({
  type: "srtConn",
  srt_latency_ms: 2000,
  details: {msRTT: null},
});
assert.doesNotMatch(missingRtt, /srt-rtt-assessment/);
assert.doesNotMatch(rtmpReader, /srt-rtt-assessment/);

const healthOnly = renderSrtHealth({
  rx_mbps: 4.2,
  rtt_ms: 28,
  retrans_packets: 3,
  drop_packets: 0,
}, "rx_mbps");
assertMetric(healthOnly, "RX", "4.20", "Mbit/s");
assertMetric(healthOnly, "RTT", "28.00", "ms");
assert.doesNotMatch(healthOnly, /metric-label">(?:Retrans|Drop|Belated)</);

const longLinkValue = renderSrtHealth({
  rx_mbps: 4.22,
  link_capacity_mbps: 3753.47,
}, "rx_mbps");
assertMetric(longLinkValue, "SRT est. Link", "3753.5", "Mbit/s");
assert.doesNotMatch(longLinkValue, /<dd>3753\.5 Mbit\/s<\/dd>/);
assert.match(rendererStyles, /\.metric dd\s*\{[^}]*font-variant-numeric:\s*tabular-nums;/s);
assert.match(rendererStyles, /\.metric dd\s*\{[^}]*text-align:\s*right;/s);
assert.match(rendererStyles, /\.metric dd\s*\{[^}]*white-space:\s*nowrap;/s);
assert.match(rendererStyles, /\.metric dt\s*\{[^}]*white-space:\s*nowrap;/s);
assert.match(rendererStyles, /\.metric-label\s*\{[^}]*white-space:\s*nowrap;/s);
assert.match(rendererStyles, /\.metric-grid\s*\{[^}]*border:\s*1px solid var\(--border\);/s);
assert.match(rendererStyles, /\.metric-full-row\s*\{[^}]*grid-column:\s*1 \/ -1;/s);
assert.doesNotMatch(rendererStyles, /\.metric\s*\{[^}]*flex-wrap:\s*wrap;/s);
assert.match(rendererStyles, /\.metric-with-assessment\s*\{[^}]*flex-wrap:\s*wrap;/s);
assert.match(rendererStyles, /\.srt-rtt-track\s*\{[^}]*flex:\s*1 1 auto;/s);
assert.match(rendererStyles, /\.srt-impact-crit \.srt-impact-dot\s*\{[^}]*animation:\s*impact-pulse/s);
assert.match(rendererStyles, /\.sparkline-graph\s*\{[^}]*height:\s*24px;/s);
assert.match(rendererStyles, /\.trend-line\s*\{[^}]*fill:\s*none;/s);
assert.match(rendererStyles, /\.trend-end-marker\s*\{[^}]*stroke-width:\s*1;/s);
assert.match(rendererStyles, /\.rate-trend\s*\{[^}]*display:\s*grid;/s);
assert.match(rendererStyles, /\.trend-rate\s*\{[^}]*stroke:\s*var\(--accent\);/s);
assert.doesNotMatch(
  rendererStyles,
  /(?:^|\n)\.trend-(?:current|variation-10|variation-60)\s*\{[^}]*fill:/s,
);
assert.match(
  rendererStyles,
  /\.srt-impact-warn \.srt-impact-dot,[\s\S]*?\.srt-impact-recent \.srt-impact-dot\s*\{[^}]*background:\s*var\(--status-warning\);/s,
);

const metricLabels = html => [...html.matchAll(/class="metric-label">([^<]+)</g)]
  .map(match => match[1]);
assert.deepEqual(metricLabels(srtPublisher), [
  "RX", "Total", "RTT", "Rcv Latency", "Rcv Loss Rate", "SRT est. Link", "Age",
]);
assert.deepEqual(metricLabels(srtReader), [
  "TX", "Total", "RTT", "Snd Latency", "Send Loss Rate", "SRT est. Link", "Frame Discard", "Age",
]);


const injectionPayloads = [
  ["<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"],
  ["<img src=x onerror=alert(1)>", "&lt;img src=x onerror=alert(1)&gt;"],
  ['"><svg onload=alert(1)>', "&quot;&gt;&lt;svg onload=alert(1)&gt;"],
  [`STREAM<&>"'`, "STREAM&lt;&amp;&gt;&quot;&#39;"],
];

for (const [payload, visibleText] of injectionPayloads) {
  const streamHtml = renderStreamLeft({
    source: {type: payload, details: {remoteAddr: payload}},
  });
  const readerHtml = renderReader({type: payload, details: {remoteAddr: payload}});

  for (const html of [streamHtml, readerHtml]) {
    assert.doesNotMatch(html, /<(?:script|img|svg)\b/i);
    assert.doesNotMatch(html, /<[^>]*\son(?:error|load)\s*=/i);
    assert.ok(html.includes(visibleText));
  }
}


class FakeIframe {
  constructor() {
    this.attributes = new Map();
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
}

class FakeCard {
  constructor() {
    this.iframe = new FakeIframe();
    this.innerHTML = "";
  }

  querySelector(selector) {
    return selector === ".preview-frame" ? this.iframe : null;
  }
}

globalThis.document = {createElement: () => new FakeCard()};
globalThis.window = {location: {hostname: "monitor.example"}};

const noReaderCard = renderStreamCard({
  name: "camera/main",
  source: {type: "rtmpConn", bitrate_mbps: null, details: {}},
  media: {video: [{displayCodec: "H.264", width: 1920, height: 1080}]},
  readers: [],
});
assert.match(noReaderCard.innerHTML, /LIVE · 0 OUT/);
assert.match(noReaderCard.innerHTML, /Keine OUT-Verbindung/);
assert.match(noReaderCard.innerHTML, /stream-left/);
assert.match(noReaderCard.innerHTML, /stream-center/);
assert.match(noReaderCard.innerHTML, /stream-right/);
assert.equal((noReaderCard.innerHTML.match(/H\.264 · 1920×1080/g) || []).length, 1);

const multiReaderCard = renderStreamCard({
  name: "multi",
  source: {type: "srtConn", bitrate_mbps: 1, details: {}},
  media: {audio: [{displayCodec: "AAC", sampleRate: 48000, channelCount: 2}]},
  readers: [
    {type: "hlsSession", bitrate_mbps: 1, details: {}},
    {type: "rtmpConn", bitrate_mbps: 1, details: {}},
    {type: "srtConn", bitrate_mbps: 1, details: {}},
  ],
});
assert.match(multiReaderCard.innerHTML, /LIVE · 3 OUT/);
assert.equal((multiReaderCard.innerHTML.match(/<h3>Reader [123]<\/h3>/g) || []).length, 3);
assert.ok(
  multiReaderCard.innerHTML.indexOf("SRT") < multiReaderCard.innerHTML.indexOf("RTMP")
  && multiReaderCard.innerHTML.indexOf("RTMP") < multiReaderCard.innerHTML.indexOf("HLS"),
);
assert.equal((multiReaderCard.innerHTML.match(/AAC · 48 kHz · Stereo/g) || []).length, 1);

const originalDateNow = Date.now;
Date.now = () => Date.parse("2026-08-16T20:08:23Z");
const twoHlsReadersCard = renderStreamCard({
  name: "hls-multi",
  source: {type: "rtmpConn", details: {}},
  hls_muxer: {
    scope: "hls_muxer",
    lastRequest: "2026-08-16T20:08:22Z",
    window_metrics: {protocol_counters: {
      "10s": {mux_discard: 2}, "60s": {mux_discard: 5},
    }},
  },
  readers: [
    {
      type: "hlsSession",
      id: "hls-a",
      bitrate_mbps: 4.8,
      rate_metrics: {"10s": {average_mbps: 4.12, sample_count: 5}},
      details: {remoteAddr: "192.0.2.50:5000", userAgent: "A"},
    },
    {
      type: "hlsSession",
      id: "hls-b",
      bitrate_mbps: 0.2,
      rate_metrics: {"10s": {average_mbps: 4.08, sample_count: 5}},
      details: {remoteAddr: "192.0.2.51:5001", userAgent: "B"},
    },
  ],
});
Date.now = originalDateNow;
assert.equal((twoHlsReadersCard.innerHTML.match(/<h3>HLS Muxer<\/h3>/g) || []).length, 1);
assert.equal((twoHlsReadersCard.innerHTML.match(/metric-label">Mux Discard/g) || []).length, 1);
assert.equal((twoHlsReadersCard.innerHTML.match(/metric-label">Last Request/g) || []).length, 1);
assert.equal((twoHlsReadersCard.innerHTML.match(/metric-label">TX Ø10s/g) || []).length, 2);
assert.equal((twoHlsReadersCard.innerHTML.match(/<h3>Reader [12]<\/h3>/g) || []).length, 2);
assert.match(twoHlsReadersCard.innerHTML, /<dd title="2026-08-16T20:08:22Z">vor 1 s<\/dd>/);
assert.match(twoHlsReadersCard.innerHTML, /192\.0\.2\.50:5000/);
assert.match(twoHlsReadersCard.innerHTML, /192\.0\.2\.51:5001/);

const previewPayload = '"><svg onload=alert(1)>';
const injectionCard = renderStreamCard({
  name: previewPayload,
  source: {type: "rtmpConn", details: {}},
  media: {other: [{displayCodec: previewPayload}]},
  readers: [],
});
assert.doesNotMatch(injectionCard.innerHTML, /<svg\b/i);
assert.doesNotMatch(injectionCard.innerHTML, /<[^>]*\sonload\s*=/i);
assert.equal(injectionCard.iframe.attributes.get("title"), `Preview: ${previewPayload}`);
assert.equal(
  injectionCard.iframe.attributes.get("src"),
  "http://monitor.example:8889/__preview__/%22%3E%3Csvg%20onload%3Dalert(1)%3E?controls=false&muted=true&autoplay=true&playsInline=true",
);
