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
  formatDataAge,
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

function assertMetric(html, label, value, unit = null) {
  const escaped = text => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const unitMarkup = unit == null
    ? ""
    : `\\s*<span class="metric-unit">${escaped(unit)}</span>`;
  const expression = new RegExp(
    `<dt>\\s*<span class="metric-label">${escaped(label)}</span>${unitMarkup}\\s*</dt>`
      + `\\s*<dd(?: class="[^"]+")?>${escaped(value)}</dd>`,
  );
  assert.match(html, expression);
}

function assertRttAssessment(html, status, percentageLabel, fillPercentage) {
  const escapedLabel = percentageLabel.replace("<", "&lt;");
  assert.match(html, new RegExp(
    `class="srt-rtt-assessment srt-rtt-${status}"[\\s\\S]*`
      + `aria-label="RTT-Latency-Nutzung: ${escapedLabel}"[\\s\\S]*`
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
assertRttAssessment(srtPublisher, "good", "1%", 3);
assert.doesNotMatch(srtPublisher, /9999/);
assertMetric(srtPublisher, "Loss", "0.00", "%");
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
assert.match(srtPublisher, /impact-retrans impact-clear/);
assert.match(srtPublisher, /impact-drop impact-recent/);
assert.match(srtPublisher, /impact-belated impact-current/);
assert.match(srtPublisher, /title="Retrans: 0"><span class="impact-label">Retrans<\/span><span class="impact-dot"><\/span><\/span>/);
assert.match(srtPublisher, /impact-drop impact-recent[\s\S]*?<span class="impact-value">1<\/span>/);
assert.match(srtPublisher, /impact-belated impact-current[\s\S]*?<span class="impact-value">3<\/span>/);
assert.doesNotMatch(srtPublisher, /window-metrics|RTT 10 s|RTT 60 s|Events 10 s|p50 Δ|>Variation</);

const srtReaderData = {
  id: "reader-a",
  type: "srtConn",
  details: {
    remoteAddr: "192.0.2.1:9000",
    bytesSent: 999999,
    msReceiveTsbPdDelay: 8888,
    packetsSendLossRate: 0,
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
        belated_packets: 5,
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
assertRttAssessment(srtReader, "good", "2%", 5.17);
assert.doesNotMatch(srtReader, /8888/);
assertMetric(srtReader, "Loss", "0.00", "%");
assertMetric(srtReader, "SRT est. Link", "11.4", "Mbit/s");
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
assertMetric(srtReader, "Undecrypt", "—", "pkt");
assert.match(srtReader, /impact-retrans impact-current/);
assert.match(srtReader, /impact-drop impact-current/);
assert.match(srtReader, /impact-belated impact-current/);
assert.match(srtReader, /impact-retrans impact-current[\s\S]*?<span class="impact-value">2<\/span>/);
assert.match(srtReader, /impact-drop impact-current[\s\S]*?<span class="impact-value">4<\/span>/);
assert.match(srtReader, /impact-belated impact-current[\s\S]*?<span class="impact-value">5<\/span>/);
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
    icmp_rtt_ms: 12,
    details: {
      remoteAddr: "192.0.2.10:8554",
      inboundBytes: 2048,
      inboundRTPPacketsLost: 0,
      inboundRTPPacketsJitter: 3.4,
      inboundRTPPacketsInError: 0,
    },
    window_metrics: {
      timing_source: "icmp_rtt_ms",
      timing: {
        "10s": {sample_count: 1, p50_ms: 12, p95_ms: 12, variation_ms: 0},
      },
    },
  },
};
resetTelemetryHistories();
recordSnapshotTelemetry([rtspPublisherStream], 3000);
recordSnapshotTelemetry([rtspPublisherStream], 3001);
const rtspPublisher = renderStreamLeft(rtspPublisherStream);
assertMetric(rtspPublisher, "Ping", "12.00", "ms");
assertMetric(rtspPublisher, "Jitter", "3.40", "ms");
assertMetric(rtspPublisher, "Loss", "0", "pkt");
assert.doesNotMatch(rtspPublisher, /metric-label">RTT/);
assert.match(rtspPublisher, /aria-label="Ping-Trend der letzten 60 Sekunden"/);
assert.match(rtspPublisher, /class="trend-line trend-current"/);
assert.match(rtspPublisher, /class="trend-line trend-variation-10"/);
assertSparklineValue(rtspPublisher, "current", "Ping", "12.0");
assertSparklineValue(rtspPublisher, "variation10", "Var 10s", "0.0");
assertSparklineValue(rtspPublisher, "variation60", "Var 60s", "—", false);
assert.match(rtspPublisher, /class="metric-full-row"/);
assert.doesNotMatch(rtspPublisher, /trend-variation-60|impact-indicators|srt-rtt-assessment/);

const rtspReader = renderReader({
  type: "rtspSession",
  bitrate_mbps: 4.8,
  details: {
    remoteAddr: "192.0.2.11:8554",
    outboundBytes: 4096,
    outboundRTPPacketsReportedLost: 2,
    outboundRTPPacketsDiscarded: 0,
  },
}, 1);
assert.match(rtspReader, /Reader 2/);
assertMetric(rtspReader, "Loss", "2", "pkt");
assertMetric(rtspReader, "Discard", "0");
assert.doesNotMatch(rtspReader, /RTT|Ping|Jitter|Retrans/);

const rtmpReader = renderReader({
  type: "rtmpConn",
  bitrate_mbps: 2.5,
  ping_rtt_ms: 0,
  details: {
    remoteAddr: "192.0.2.4:1935",
    outboundBytes: 1024,
    outboundFramesDiscarded: 0,
  },
}, 0);
assertMetric(rtmpReader, "TX", "2.50", "Mbit/s");
assertMetric(rtmpReader, "Ping", "0.00", "ms");
assertMetric(rtmpReader, "Discard", "0");
assert.doesNotMatch(rtmpReader, /RTT|Loss|Retrans|Link|Reserve/);

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
assertMetric(hlsReader, "TX", "—", "Mbit/s");
assertMetric(hlsReader, "Total", "0 B");
assert.match(hlsReader, /Agent: Field Player\/1\.0/);
assert.match(hlsReader, /CDN: nein/);
assert.doesNotMatch(hlsReader, /RTT|Ping|Loss|Jitter/);
assert.doesNotMatch(hlsReader, /Latency/);

const missingSrtLatency = renderReader({
  type: "srtConn",
  srt_latency_ms: null,
  details: {msSendTsbPdDelay: null},
});
assert.doesNotMatch(missingSrtLatency, /Latency/);
assert.doesNotMatch(missingSrtLatency, /srt-rtt-assessment/);
assert.doesNotMatch(missingSrtLatency, /rtt-trend|impact-indicators/);

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
assert.match(partialHistory, /impact-retrans impact-unavailable/);
assert.match(partialHistory, /impact-drop impact-clear/);
assert.match(partialHistory, /impact-belated impact-unavailable/);
assert.match(partialHistory, /title="Retrans: nicht verfügbar"><span class="impact-label">Retrans<\/span>/);
assert.match(partialHistory, /title="Belated: nicht verfügbar"><span class="impact-label">Belated<\/span>/);
assert.doesNotMatch(partialHistory, /p50|p95|>Variation</);

function renderEventStates(events) {
  return renderReader({
    id: "event-reader",
    type: "srtConn",
    transport_rtt_ms: 10,
    details: {},
    window_metrics: {events},
  }, 0, "events");
}

const allRecentEvents = renderEventStates({
  "10s": {retrans_packets: 0, drop_packets: 0, belated_packets: 0},
  "60s": {retrans_packets: 2, drop_packets: 3, belated_packets: 4},
});
for (const field of ["retrans", "drop", "belated"]) {
  assert.match(allRecentEvents, new RegExp(`impact-${field} impact-recent`));
}
assert.doesNotMatch(allRecentEvents, /impact-pulse/);

const allClearEvents = renderEventStates({
  "10s": {retrans_packets: 0, drop_packets: 0, belated_packets: 0},
  "60s": {retrans_packets: 0, drop_packets: 0, belated_packets: 0},
});
for (const field of ["retrans", "drop", "belated"]) {
  assert.match(allClearEvents, new RegExp(`impact-${field} impact-clear`));
}
assert.doesNotMatch(allClearEvents, /impact-value/);

const allUnavailableEvents = renderEventStates({"10s": {}, "60s": {}});
for (const field of ["retrans", "drop", "belated"]) {
  assert.match(allUnavailableEvents, new RegExp(`impact-${field} impact-unavailable`));
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

const healthySrtIn = renderStreamLeft({
  source: {
    type: "srtConn",
    transport_rtt_ms: 70,
    srt_latency_ms: 2000,
    details: {},
  },
});
assertMetric(healthySrtIn, "RTT", "70.00", "ms");
assertMetric(healthySrtIn, "Rcv Latency", "2000", "ms");
assertRttAssessment(healthySrtIn, "good", "4%", 8.75);
assert.match(healthySrtIn, /<dd class="srt-rtt-good">2000<\/dd>/);

const warningSrtOut = renderReader({
  type: "srtConn",
  srt_latency_ms: 2000,
  details: {msRTT: 600},
});
assertMetric(warningSrtOut, "RTT", "600.00", "ms");
assertMetric(warningSrtOut, "Snd Latency", "2000", "ms");
assertRttAssessment(warningSrtOut, "warning", "30%", 75);
assert.match(warningSrtOut, /<dd class="srt-rtt-warning">2000<\/dd>/);

const criticalSrtOut = renderReader({
  type: "srtConn",
  srt_latency_ms: 2000,
  details: {msRTT: 900},
});
assertRttAssessment(criticalSrtOut, "critical", "45%", 100);
assert.match(criticalSrtOut, /<dd class="srt-rtt-critical">2000<\/dd>/);

const percentageCases = [
  {ratio: 0, label: "0%", fill: 0},
  {ratio: 0.0033, label: "<1%", fill: 0.82},
  {ratio: 0.0349, label: "3%", fill: 8.72},
  {ratio: 0.30, label: "30%", fill: 75},
  {ratio: 1.24, label: "124%", fill: 100},
];
for (const {ratio, label, fill} of percentageCases) {
  const html = renderReader({
    type: "srtConn",
    srt_latency_ms: 100,
    details: {msRTT: ratio * 100},
  });
  const status = ratio < 0.25 ? "good" : ratio <= 0.33 ? "warning" : "critical";
  assertRttAssessment(html, status, label, fill);
}

for (const latency of [undefined, null, 0]) {
  const unavailableAssessment = renderReader({
    type: "srtConn",
    srt_latency_ms: latency,
    details: {msRTT: 100},
  });
  assert.doesNotMatch(unavailableAssessment, /srt-rtt-assessment/);
}

const missingRttAssessment = renderReader({
  type: "srtConn",
  srt_latency_ms: 2000,
  details: {msRTT: null},
});
assert.doesNotMatch(missingRttAssessment, /srt-rtt-assessment/);
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
assert.match(rendererStyles, /\.impact-current \.impact-dot\s*\{[^}]*animation:\s*impact-pulse/s);
assert.match(rendererStyles, /\.sparkline-graph\s*\{[^}]*height:\s*24px;/s);
assert.match(rendererStyles, /\.trend-line\s*\{[^}]*fill:\s*none;/s);
assert.match(rendererStyles, /\.trend-end-marker\s*\{[^}]*stroke-width:\s*1;/s);
assert.doesNotMatch(
  rendererStyles,
  /(?:^|\n)\.trend-(?:current|variation-10|variation-60)\s*\{[^}]*fill:/s,
);
assert.match(
  rendererStyles,
  /\.impact-indicators\s*\{[^}]*grid-template-columns:\s*repeat\(3, minmax\(68px, 1fr\)\);/s,
);

const metricLabels = html => [...html.matchAll(/class="metric-label">([^<]+)</g)]
  .map(match => match[1]);
assert.deepEqual(metricLabels(srtPublisher), [
  "RX", "Total", "RTT", "Rcv Latency", "Loss", "SRT est. Link", "Undecrypt", "Age",
]);
assert.deepEqual(metricLabels(srtReader), [
  "TX", "Total", "RTT", "Snd Latency", "Loss", "SRT est. Link", "Undecrypt", "Age",
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
