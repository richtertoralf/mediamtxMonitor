import {
  assert,
  recordSnapshotTelemetry,
  renderStreamLeft,
  resetTelemetryHistories,
  telemetryHistoryFor,
  telemetryScaleState,
  telemetryTrendY,
  telemetryVariationY,
} from "./renderer-test-helpers.mjs";

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
