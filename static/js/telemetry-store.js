/**
 * MediaMTX Monitor - Browser-local telemetry history and scales.
 *
 * Owns snapshot history and deterministic graph scaling without rendering.
 */

import {firstAvailable, optionalNumber} from "./format-utils.js";

export const TELEMETRY_WINDOW_SECONDS = 60;
export const SPARKLINE_BASELINE_Y = 22;
export const SPARKLINE_VERTICAL_RANGE = 20;
const TREND_SCALE_HEADROOM = 1.15;
const TREND_SCALE_MINIMUM_MS = 100;
const VARIATION_SCALE_MINIMUM_MS = 50;
const telemetryHistories = new Map();
let trendScaleState;
let variationScaleState;

export function connectionTelemetryKey(pathName, role, connection) {
  const connectionId = connection?.id;
  if (!pathName || !connection?.type || !connectionId) return null;
  return `${pathName}:${role}:${connection.type}:${connectionId}`;
}

export function connectionTimingValues(connection) {
  const timing = connection?.window_metrics?.timing || {};
  const current = connection?.type === "srtConn"
    ? firstAvailable(connection?.transport_rtt_ms, connection?.srt_health?.rtt_ms,
      connection?.details?.msRTT) : null;
  return {
    current: optionalNumber(current),
    variation10: optionalNumber(timing["10s"]?.variation_ms),
    variation60: optionalNumber(timing["60s"]?.variation_ms),
  };
}

export function telemetryHistoryByKey(key) {
  return [...(telemetryHistories.get(key) || [])];
}

function recordConnectionTelemetry(key, connection, timestamp) {
  if (!key) return;
  const values = connectionTimingValues(connection);
  if (values.current == null && values.variation10 == null && values.variation60 == null) return;
  const history = telemetryHistories.get(key) || [];
  if (history.some(point => point.timestamp === timestamp)) return;
  history.push({timestamp, ...values});
  history.sort((left, right) => left.timestamp - right.timestamp);
  telemetryHistories.set(key,
    history.filter(point => point.timestamp > timestamp - TELEMETRY_WINDOW_SECONDS));
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
    return {requiredMaximum,
      scaleMaximum: Math.max(requiredMaximum * TREND_SCALE_HEADROOM, minimum),
      lowerRequiredSince: null};
  }
  const lowerRequiredSince = state.lowerRequiredSince ?? timestamp;
  if (timestamp - lowerRequiredSince >= TELEMETRY_WINDOW_SECONDS) {
    return {requiredMaximum,
      scaleMaximum: Math.max(requiredMaximum * TREND_SCALE_HEADROOM, minimum),
      lowerRequiredSince: null};
  }
  return {...state, lowerRequiredSince};
}

function updateSharedTrendScales(timestamp) {
  trendScaleState = updatedScaleState(trendScaleState,
    activeTelemetryMaximum(["current"]), TREND_SCALE_MINIMUM_MS, timestamp);
  variationScaleState = updatedScaleState(variationScaleState,
    activeTelemetryMaximum(["variation10", "variation60"]),
    VARIATION_SCALE_MINIMUM_MS, timestamp);
}

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

export function resetTelemetryHistories() {
  telemetryHistories.clear();
  trendScaleState = {requiredMaximum: 0, scaleMaximum: TREND_SCALE_MINIMUM_MS,
    lowerRequiredSince: null};
  variationScaleState = {requiredMaximum: 0, scaleMaximum: VARIATION_SCALE_MINIMUM_MS,
    lowerRequiredSince: null};
}

export function telemetryHistoryFor(pathName, role, connection) {
  const key = connectionTelemetryKey(pathName, role, connection);
  return key ? telemetryHistoryByKey(key) : [];
}

export function telemetryScaleState() {
  return {trend: {...trendScaleState}, variation: {...variationScaleState}};
}

export function telemetryTrendY(value) {
  const number = optionalNumber(value);
  if (number == null) return null;
  const normalized = Math.sqrt(Math.max(0, number)) / Math.sqrt(trendScaleState.scaleMaximum);
  return SPARKLINE_BASELINE_Y - Math.max(0, Math.min(1, normalized)) * SPARKLINE_VERTICAL_RANGE;
}

export function telemetryVariationY(value) {
  const number = optionalNumber(value);
  if (number == null) return null;
  const normalized = Math.max(0, number) / variationScaleState.scaleMaximum;
  return SPARKLINE_BASELINE_Y - Math.max(0, Math.min(1, normalized)) * SPARKLINE_VERTICAL_RANGE;
}

resetTelemetryHistories();
