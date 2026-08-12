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
  renderReader,
  renderSrtHealth,
  renderStreamCard,
  renderStreamLeft,
} = await import(`data:text/javascript;base64,${Buffer.from(rendererSource).toString("base64")}`);

function assertMetric(html, label, value, unit = null) {
  const escaped = text => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const unitMarkup = unit == null
    ? ""
    : `\\s*<span class="metric-unit">${escaped(unit)}</span>`;
  const expression = new RegExp(
    `<dt>\\s*<span class="metric-label">${escaped(label)}</span>${unitMarkup}\\s*</dt>`
      + `\\s*<dd>${escaped(value)}</dd>`,
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


const srtPublisher = renderStreamLeft({
  name: "camera/srt",
  inboundBytes: 8192,
  source: {
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
      reserve_ratio: 3.3,
      retrans_packets: 0,
      drop_packets: 0,
    },
  },
});

assert.match(srtPublisher, /<h2 class="panel-title">IN<\/h2>/);
assert.match(srtPublisher, /SRT/);
assert.match(srtPublisher, /192\.0\.2\.3:9000/);
assertMetric(srtPublisher, "RX", "3.75", "Mbit/s");
assertMetric(srtPublisher, "Total", "4.00 KB");
assertMetric(srtPublisher, "RTT", "24.00", "ms");
assertMetric(srtPublisher, "Latency", "2000", "ms");
assertRttAssessment(srtPublisher, "good", "1%", 3);
assert.doesNotMatch(srtPublisher, /9999/);
assertMetric(srtPublisher, "Loss", "0.00", "%");
assertMetric(srtPublisher, "Retrans", "0", "pkt");
assertMetric(srtPublisher, "Drop", "0", "pkt");
assertMetric(srtPublisher, "Link", "12.5", "Mbit/s");
assert.doesNotMatch(srtPublisher, /Ping/);
assert.doesNotMatch(srtPublisher, /H\.264|Video:/);

const srtReader = renderReader({
  type: "srtConn",
  details: {
    remoteAddr: "192.0.2.1:9000",
    bytesSent: 999999,
    msReceiveTsbPdDelay: 8888,
    packetsSendLossRate: 0,
  },
  srt_latency_ms: 1500,
  bitrate_mbps: 9.99,
  srt_health: {
    tx_mbps: 4.25,
    link_capacity_mbps: 11.4,
    reserve_ratio: 2.68,
    rtt_ms: 31,
    retrans_packets: 2,
    drop_packets: 0,
  },
}, 0);

assert.match(srtReader, /Reader 1/);
assertMetric(srtReader, "TX", "4.25", "Mbit/s");
assertMetric(srtReader, "RTT", "31.00", "ms");
assertMetric(srtReader, "Latency", "1500", "ms");
assertRttAssessment(srtReader, "good", "2%", 5.17);
assert.doesNotMatch(srtReader, /8888/);
assertMetric(srtReader, "Loss", "0.00", "%");
assertMetric(srtReader, "Drop", "0", "pkt");
assert.doesNotMatch(srtReader, /Ping/);
assert.doesNotMatch(srtReader, /9\.99/);

const nullRate = renderStreamLeft({
  source: {type: "rtmpConn", bitrate_mbps: null, details: {}},
});
assertMetric(nullRate, "RX", "—", "Mbit/s");
assert.doesNotMatch(nullRate, /<dd>0\.00<\/dd>/);

const measuredZeroRate = renderStreamLeft({
  source: {type: "rtmpConn", bitrate_mbps: 0, details: {}},
});
assertMetric(measuredZeroRate, "RX", "0.00", "Mbit/s");

const rtspPublisher = renderStreamLeft({
  source: {
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
  },
});
assertMetric(rtspPublisher, "Ping", "12.00", "ms");
assertMetric(rtspPublisher, "Jitter", "3.40", "ms");
assertMetric(rtspPublisher, "Loss", "0", "pkt");
assert.doesNotMatch(rtspPublisher, /metric-label">RTT/);

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

const healthySrtIn = renderStreamLeft({
  source: {
    type: "srtConn",
    transport_rtt_ms: 70,
    srt_latency_ms: 2000,
    details: {},
  },
});
assertMetric(healthySrtIn, "RTT", "70.00", "ms");
assertMetric(healthySrtIn, "Latency", "2000", "ms");
assertRttAssessment(healthySrtIn, "good", "4%", 8.75);

const warningSrtOut = renderReader({
  type: "srtConn",
  srt_latency_ms: 2000,
  details: {msRTT: 600},
});
assertMetric(warningSrtOut, "RTT", "600.00", "ms");
assertMetric(warningSrtOut, "Latency", "2000", "ms");
assertRttAssessment(warningSrtOut, "warning", "30%", 75);

const criticalSrtOut = renderReader({
  type: "srtConn",
  srt_latency_ms: 2000,
  details: {msRTT: 900},
});
assertRttAssessment(criticalSrtOut, "critical", "45%", 100);

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
assertMetric(healthOnly, "Drop", "0", "pkt");

const longLinkValue = renderSrtHealth({
  rx_mbps: 4.22,
  link_capacity_mbps: 3753.47,
}, "rx_mbps");
assertMetric(longLinkValue, "Link", "3753.5", "Mbit/s");
assert.doesNotMatch(longLinkValue, /<dd>3753\.5 Mbit\/s<\/dd>/);
assert.match(rendererStyles, /\.metric dd\s*\{[^}]*font-variant-numeric:\s*tabular-nums;/s);
assert.match(rendererStyles, /\.metric dd\s*\{[^}]*text-align:\s*right;/s);
assert.match(rendererStyles, /\.metric dd\s*\{[^}]*white-space:\s*nowrap;/s);
assert.match(rendererStyles, /\.metric dt\s*\{[^}]*white-space:\s*nowrap;/s);
assert.match(rendererStyles, /\.metric-label\s*\{[^}]*white-space:\s*nowrap;/s);
assert.match(rendererStyles, /\.metric-grid\s*\{[^}]*border:\s*1px solid var\(--border\);/s);
assert.doesNotMatch(rendererStyles, /\.metric\s*\{[^}]*flex-wrap:\s*wrap;/s);
assert.match(rendererStyles, /\.metric-with-assessment\s*\{[^}]*flex-wrap:\s*wrap;/s);
assert.match(rendererStyles, /\.srt-rtt-track\s*\{[^}]*flex:\s*1 1 auto;/s);


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
