/**
 * MediaMTX Monitor - Renderer compatibility facade.
 *
 * Preserves the established public renderer contract through re-exports.
 */

export {dataAgeStatusClass, formatDataAge, formatRelativeTime} from "./format-utils.js";
export {recordSnapshotTelemetry, resetTelemetryHistories, telemetryHistoryFor, telemetryScaleState, telemetryTrendY, telemetryVariationY} from "./telemetry-store.js";
export {renderMonitorTitle, renderReader, renderSrtHealth, renderStreamCard, renderStreamLeft, updateStreamCard} from "./stream-card.js";
