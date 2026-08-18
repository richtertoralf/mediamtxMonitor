import assert from "node:assert/strict";
import test from "node:test";

import {
  recordSnapshotTelemetry,
  resetTelemetryHistories,
  telemetryHistoryFor,
  telemetryScaleState,
} from "../static/js/telemetry-store.js";

test("telemetry store owns history independently of renderers", () => {
  const source = {id: "source", type: "srtConn", transport_rtt_ms: 25};
  resetTelemetryHistories();
  recordSnapshotTelemetry([{name: "camera", source}], 1000);
  assert.deepEqual(telemetryHistoryFor("camera", "publisher", source), [{
    timestamp: 1000,
    current: 25,
    variation10: null,
    variation60: null,
  }]);
  assert.equal(telemetryScaleState().trend.requiredMaximum, 25);
});
