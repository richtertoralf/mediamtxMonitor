import {
  assert,
  assertMetric,
  formatRelativeTime,
  recordSnapshotTelemetry,
  renderReader,
  renderStreamLeft,
  resetTelemetryHistories,
} from "./renderer-test-helpers.mjs";

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

assert.doesNotMatch(rtmpReader, /srt-rtt-assessment/);
