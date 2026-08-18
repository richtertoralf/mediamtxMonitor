import {
  assert,
  assertMetric,
  assertRttLatencyRelation,
  assertSparklineValue,
  assertSrtImpact,
  recordSnapshotTelemetry,
  renderReader,
  renderSrtHealth,
  renderStreamLeft,
  rendererStyles,
  resetTelemetryHistories,
} from "./renderer-test-helpers.mjs";

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
const metricLabels = html => [...html.matchAll(/class="metric-label">([^<]+)</g)]
  .map(match => match[1]);
assert.deepEqual(metricLabels(srtPublisher), [
  "RX", "Total", "RTT", "Rcv Latency", "Rcv Loss Rate", "SRT est. Link", "Age",
]);
assert.deepEqual(metricLabels(srtReader), [
  "TX", "Total", "RTT", "Snd Latency", "Send Loss Rate", "SRT est. Link", "Frame Discard", "Age",
]);
