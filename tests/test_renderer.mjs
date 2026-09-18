import {
  assert,
  isStreamActive,
  rendererExportNames,
  rendererSource,
  rendererStyles,
  renderForwardDestination,
  renderMonitorTitle,
  renderReader,
  renderStreamCard,
  renderStreamLeft,
  updateStreamCard,
} from "./renderer-test-helpers.mjs";

assert.deepEqual(rendererExportNames, [
  "dataAgeStatusClass",
  "formatDataAge",
  "formatRelativeTime",
  "isStreamActive",
  "recordSnapshotTelemetry",
  "renderForwardDestination",
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
    this.srcWrites = 0;
    this.srcRemovals = 0;
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  setAttribute(name, value) {
    if (name === "src") this.srcWrites += 1;
    this.attributes.set(name, String(value));
  }

  removeAttribute(name) {
    if (name === "src" && this.attributes.has(name)) this.srcRemovals += 1;
    this.attributes.delete(name);
  }
}

class FakePanel {
  constructor() {
    this.innerHTML = "";
    this.outerHTML = "";
  }
}

class FakeCard {
  constructor() {
    this.iframe = new FakeIframe();
    this.innerHTML = "";
    this.panels = new Map(
      [".stream-header", ".stream-left", ".stream-center", ".media-summary", ".stream-right"]
        .map(selector => [selector, new FakePanel()]),
    );
  }

  querySelector(selector) {
    if (selector === ".preview-frame") return this.iframe;
    return this.panels.get(selector) || null;
  }
}

globalThis.document = {createElement: () => new FakeCard()};
globalThis.window = {location: {hostname: "monitor.example"}};

const noReaderCard = renderStreamCard({
  name: "camera/main",
  available: true,
  online: true,
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

const offlineCard = renderStreamCard({name: "offline", available: false, readers: []});
assert.equal(offlineCard.iframe.attributes.has("src"), false);
updateStreamCard(offlineCard, {name: "offline", available: true, readers: []}, "http://monitor.example:8889");
assert.equal(
  offlineCard.iframe.attributes.get("src"),
  "http://monitor.example:8889/__preview__/offline?controls=false&muted=true&autoplay=true&playsInline=true",
);
updateStreamCard(offlineCard, {name: "offline", available: false, readers: []});
assert.equal(offlineCard.iframe.attributes.has("src"), false);

// Preview-Lebenszyklus: ein normaler Metrics-Refresh darf die bestehende
// WebRTC-Sitzung nicht neu starten.
const previewBase = "http://monitor.example:8889";
const previewSrc = path =>
  `${previewBase}/__preview__/${path}?controls=false&muted=true&autoplay=true&playsInline=true`;
const activeStream = extra => ({name: "camera/main", available: true, readers: [], ...extra});

const lifecycleCard = renderStreamCard(activeStream(), previewBase);
const lifecycleIframe = lifecycleCard.iframe;
assert.equal(lifecycleIframe.srcWrites, 1);
assert.equal(lifecycleIframe.getAttribute("src"), previewSrc("camera/main"));

updateStreamCard(lifecycleCard, activeStream(), previewBase);
assert.equal(lifecycleCard.querySelector(".preview-frame"), lifecycleIframe);
assert.equal(lifecycleIframe.srcWrites, 1);
assert.equal(lifecycleIframe.srcRemovals, 0);

for (const bitrate of [4.8, 5.1, 6.2]) {
  updateStreamCard(
    lifecycleCard,
    activeStream({source: {type: "srtConn", bitrate_mbps: bitrate, details: {}}}),
    previewBase,
  );
}
assert.equal(lifecycleCard.querySelector(".preview-frame"), lifecycleIframe);
assert.equal(lifecycleIframe.srcWrites, 1);
assert.equal(lifecycleIframe.srcRemovals, 0);
assert.match(lifecycleCard.panels.get(".stream-left").outerHTML, /stream-left/);
assert.match(lifecycleCard.panels.get(".stream-right").innerHTML, /Keine OUT-Verbindung/);
assert.equal(lifecycleCard.panels.get(".stream-center").innerHTML, "");

updateStreamCard(lifecycleCard, activeStream({available: false}), previewBase);
assert.equal(lifecycleIframe.getAttribute("src"), null);
assert.equal(lifecycleIframe.srcRemovals, 1);
updateStreamCard(lifecycleCard, activeStream({available: false}), previewBase);
assert.equal(lifecycleIframe.srcRemovals, 1);

updateStreamCard(lifecycleCard, activeStream(), previewBase);
assert.equal(lifecycleIframe.srcWrites, 2);
assert.equal(lifecycleIframe.getAttribute("src"), previewSrc("camera/main"));
updateStreamCard(lifecycleCard, activeStream(), previewBase);
assert.equal(lifecycleIframe.srcWrites, 2);

updateStreamCard(lifecycleCard, activeStream({name: "camera/backup"}), previewBase);
assert.equal(lifecycleIframe.srcWrites, 3);
assert.equal(lifecycleIframe.getAttribute("src"), previewSrc("camera/backup"));
updateStreamCard(lifecycleCard, activeStream({name: "camera/backup"}), previewBase);
assert.equal(lifecycleIframe.srcWrites, 3);
assert.equal(lifecycleIframe.srcRemovals, 1);

// main.js rendert ausschliesslich die aktiven Streams und raeumt den Rest ab.
// Die Schleife ist ohne DOM nicht importierbar, deshalb wird ihr Vertrag hier
// an der Quelle festgehalten.
assert.match(rendererSource, /const activeStreams = streams\.filter\(isStreamActive\);/);
assert.match(rendererSource, /for \(const stream of activeStreams\) \{\s*\n\s*seen\.add\(stream\.name\);/);
assert.match(rendererSource, /if \(!seen\.has\(name\)\) \{\s*\n\s*card\.remove\(\);\s*\n\s*streamCards\.delete\(name\);/);
assert.match(rendererSource, /noStreams\.style\.display = activeStreams\.length === 0/);

// Sichtbarkeitsvertrag: nur tatsaechlich laufende Pfade sind Streams.
assert.equal(isStreamActive({available: true, online: true}), true);
for (const state of [
  {available: false, online: false},
  {available: false, online: true},
  {available: true, online: false},
  {},
  null,
]) {
  assert.equal(isStreamActive(state), false);
}

// Das LIVE-Badge spiegelt den realen Zustand und zaehlt Reader plus Forwards.
const activeHeader = renderStreamCard(
  {name: "aktiv", available: true, online: true, readers: [], forwardDestinations: []},
  previewBase,
).innerHTML;
assert.match(activeHeader, /<span class="live-dot"><\/span>LIVE · 0 OUT/);
assert.doesNotMatch(activeHeader, /stream-status-idle/);

const idleHeader = renderStreamCard(
  {name: "inaktiv", available: false, online: false, readers: []},
  previewBase,
).innerHTML;
assert.match(idleHeader, /stream-status-idle/);
assert.match(idleHeader, /<span class="live-dot"><\/span>INAKTIV · 0 OUT/);
assert.doesNotMatch(idleHeader, /LIVE ·/);
assert.match(rendererStyles, /\.stream-status-idle \.live-dot\s*\{[^}]*background:\s*var\(--text-muted\);/s);

// Forward-/Push-Ziele erscheinen zusaetzlich zu den Readern unter OUT.
const forwardOnly = renderStreamCard({
  name: "forward-only",
  available: true,
  online: true,
  readers: [],
  forwardDestinations: [
    {id: "fw-1", pos: 0, type: "rtmp", state: "forwarding",
      outboundBytes: 2048, created: "2026-08-16T20:08:22Z"},
  ],
}, previewBase);
assert.match(forwardOnly.innerHTML, /<h3>Forward 1<\/h3>/);
assert.match(forwardOnly.innerHTML, /<span>RTMP<\/span>/);
assert.match(forwardOnly.innerHTML, /class="forward-state">· forwarding</);
assert.doesNotMatch(forwardOnly.innerHTML, /Keine OUT-Verbindung/);
assert.match(forwardOnly.innerHTML, /LIVE · 1 OUT/);

const readersAndForwards = renderStreamCard({
  name: "beides",
  available: true,
  online: true,
  source: {type: "srtConn", bitrate_mbps: 1, details: {}},
  readers: [{type: "rtmpConn", bitrate_mbps: 1, details: {}}],
  forwardDestinations: [
    {id: "fw-1", pos: 0, type: "rtmp", state: "forwarding", outboundBytes: 1024},
    {id: "fw-2", pos: 1, type: "srt", state: "error", outboundBytes: 0},
  ],
}, previewBase);
assert.equal((readersAndForwards.innerHTML.match(/<h3>Reader 1<\/h3>/g) || []).length, 1);
assert.equal((readersAndForwards.innerHTML.match(/<h3>Forward [12]<\/h3>/g) || []).length, 2);
assert.match(readersAndForwards.innerHTML, /class="forward-state">· error</);
assert.match(readersAndForwards.innerHTML, /LIVE · 3 OUT/);
assert.ok(
  readersAndForwards.innerHTML.indexOf("Reader 1")
    < readersAndForwards.innerHTML.indexOf("Forward 1"),
);

// Ein leeres Forward-Array laesst die bisherige Reader-Anzeige unveraendert.
const readersOnly = renderStreamCard({
  name: "nur-reader",
  available: true,
  online: true,
  readers: [{type: "rtmpConn", bitrate_mbps: 1, details: {}}],
  forwardDestinations: [],
}, previewBase);
assert.match(readersOnly.innerHTML, /<h3>Reader 1<\/h3>/);
assert.doesNotMatch(readersOnly.innerHTML, /Forward/);
assert.doesNotMatch(readersOnly.innerHTML, /Keine OUT-Verbindung/);
assert.match(readersOnly.innerHTML, /LIVE · 1 OUT/);
assert.match(
  renderStreamCard({name: "leer", available: true, online: true, readers: []}, previewBase).innerHTML,
  /Keine OUT-Verbindung/,
);

// Nur sanitisierte Felder erreichen das HTML; Secrets sind nicht Teil des Vertrags.
const forwardHtml = renderForwardDestination({
  id: "fw-secret",
  pos: 0,
  type: "rtmps",
  state: "forwarding",
  outboundBytes: 4096,
  created: "2026-08-16T20:08:22Z",
  url: "rtmps://live.example/app/SUPERSECRETKEY?token=abc",
  streamKey: "SUPERSECRETKEY",
  password: "hunter2",
});
for (const secret of ["SUPERSECRETKEY", "hunter2", "token=abc", "rtmps://live.example"]) {
  assert.ok(!forwardHtml.includes(secret), `Secret im HTML: ${secret}`);
}
assert.match(forwardHtml, /<span>RTMPS<\/span>/);

const forwardInjection = renderForwardDestination({
  type: '"><svg onload=alert(1)>',
  state: '"><img src=x onerror=alert(1)>',
  outboundBytes: 1,
});
assert.doesNotMatch(forwardInjection, /<(?:script|img|svg)\b/i);
assert.doesNotMatch(forwardInjection, /<[^>]*\son(?:error|load)\s*=/i);

// Fehlende Felder erfinden keine Zustaende.
const sparseForward = renderForwardDestination({id: "fw-3"});
assert.match(sparseForward, /<span>—<\/span>/);
assert.match(sparseForward, /class="forward-state">· —</);

const multiReaderCard = renderStreamCard({
  name: "multi",
  available: true,
  online: true,
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
  available: true,
  online: true,
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
  available: true,
  online: true,
  source: {type: "rtmpConn", details: {}},
  media: {other: [{displayCodec: previewPayload}]},
  readers: [],
}, "http://monitor.example:8889");
assert.doesNotMatch(injectionCard.innerHTML, /<svg\b/i);
assert.doesNotMatch(injectionCard.innerHTML, /<[^>]*\sonload\s*=/i);
assert.equal(injectionCard.iframe.attributes.get("title"), `Preview: ${previewPayload}`);
assert.equal(
  injectionCard.iframe.attributes.get("src"),
  "http://monitor.example:8889/__preview__/%22%3E%3Csvg%20onload%3Dalert(1)%3E?controls=false&muted=true&autoplay=true&playsInline=true",
);

for (const base of ["http://media.example:8899", "https://media.example:9443/preview-proxy/"]) {
  const card = renderStreamCard({name: "camera/main", available: true}, base);
  assert.equal(card.iframe.attributes.get("src"),
    `${base.replace(/\/$/, "")}/__preview__/camera/main?controls=false&muted=true&autoplay=true&playsInline=true`);
}
for (const base of ["", "javascript:alert(1)", "https://user:secret@example.test", "https://example.test?token=secret"]) {
  const card = renderStreamCard({name: "camera", available: true}, base);
  assert.equal(card.iframe.attributes.has("src"), false);
}
