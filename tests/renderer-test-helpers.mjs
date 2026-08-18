import assert from "node:assert/strict";
import {readdir, readFile} from "node:fs/promises";

import * as renderer from "../static/js/renderer.js";

const javascriptDirectory = new URL("../static/js/", import.meta.url);
const javascriptSources = await Promise.all(
  (await readdir(javascriptDirectory))
    .filter(name => name.endsWith(".js"))
    .map(name => readFile(new URL(name, javascriptDirectory), "utf8")),
);

export {assert};
export const rendererExportNames = Object.keys(renderer).sort();
export const rendererSource = javascriptSources.join("\n");
export const rendererStyles = await readFile(
  new URL("../static/css/style.css", import.meta.url),
  "utf8",
);
export const {
  dataAgeStatusClass,
  formatDataAge,
  formatRelativeTime,
  recordSnapshotTelemetry,
  renderMonitorTitle,
  renderReader,
  renderSrtHealth,
  renderStreamCard,
  renderStreamLeft,
  resetTelemetryHistories,
  telemetryHistoryFor,
  telemetryScaleState,
  telemetryTrendY,
  telemetryVariationY,
  updateStreamCard,
} = renderer;

export function assertMetric(html, label, value, unit = null) {
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

export function assertRttLatencyRelation(
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

export function assertSparklineValue(html, rowClass, label, value, hasUnit = true) {
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

export function assertSrtImpact(html, status, label, detail) {
  assert.match(html, new RegExp(
    `class="srt-impact srt-impact-${status}"[\\s\\S]*?`
      + `aria-label="SRT Impact ${label}: ${detail}"[\\s\\S]*?`
      + `<span class="srt-impact-status">${label}<\\/span>[\\s\\S]*?`
      + `<div class="srt-impact-detail">${detail}<\\/div>`,
  ));
}
