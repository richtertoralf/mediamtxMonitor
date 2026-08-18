import assert from "node:assert/strict";
import test from "node:test";

import {
  dataAgeStatusClass,
  escapeHtml,
  formatBytes,
  formatDataAge,
  formatRelativeTime,
} from "../static/js/format-utils.js";

test("format utilities are directly importable and side-effect free", () => {
  assert.equal(escapeHtml(`<&>"'`), "&lt;&amp;&gt;&quot;&#39;");
  assert.equal(formatBytes(4096), "4.00 KB");
  assert.equal(formatDataAge(1000, 1000400), "Datenalter: 0.4 s");
  assert.equal(dataAgeStatusClass(989.9, 1000000), "data-age-stale");
  assert.equal(
    formatRelativeTime("2026-08-16T20:08:22Z", Date.parse("2026-08-16T20:08:23Z")),
    "vor 1 s",
  );
});
assert.equal(formatDataAge(1000, 1000400), "Datenalter: 0.4 s");
assert.equal(formatDataAge(1001, 1000000), "Datenalter: 0.0 s");
assert.equal(formatDataAge(null, 1000000), null);
assert.equal(formatDataAge("invalid", 1000000), null);
assert.equal(dataAgeStatusClass(997.1, 1000000), "data-age-fresh");
assert.equal(dataAgeStatusClass(997, 1000000), "data-age-warning");
assert.equal(dataAgeStatusClass(990, 1000000), "data-age-warning");
assert.equal(dataAgeStatusClass(989.9, 1000000), "data-age-stale");
assert.equal(dataAgeStatusClass(null, 1000000), "data-age-unknown");
