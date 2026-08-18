import {
  assert,
  rendererExportNames,
  rendererSource,
  rendererStyles,
  renderMonitorTitle,
  renderReader,
  renderStreamCard,
  renderStreamLeft,
} from "./renderer-test-helpers.mjs";

assert.deepEqual(rendererExportNames, [
  "dataAgeStatusClass",
  "formatDataAge",
  "formatRelativeTime",
  "recordSnapshotTelemetry",
  "renderMonitorTitle",
  "renderReader",
  "renderSrtHealth",
  "renderStreamCard",
  "renderStreamLeft",
  "resetTelemetryHistories",
  "telemetryHistoryFor",
  "telemetryScaleState",
  "telemetryTrendY",
  "telemetryVariationY",
  "updateStreamCard",
]);

const originalDocument = globalThis.document;
const pageTitle = {textContent: ""};
globalThis.document = {title: ""};
renderMonitorTitle(pageTitle, "0.8.0");
assert.equal(pageTitle.textContent, "MediaMTX Stream Monitor · v0.8.0 - richterprojects.com");
assert.equal(document.title, pageTitle.textContent);
renderMonitorTitle(pageTitle, undefined);
assert.equal(pageTitle.textContent, "MediaMTX Stream Monitor - richterprojects.com");
assert.equal(document.title, pageTitle.textContent);
globalThis.document = originalDocument;

assert.doesNotMatch(rendererSource, /protocol-marker|marker-srt|marker-rtmp/);
assert.doesNotMatch(rendererStyles, /protocol-marker|marker-srt|marker-rtmp/);
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
