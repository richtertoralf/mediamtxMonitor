import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";


const rendererSource = await readFile(
  new URL("../static/js/renderer.js", import.meta.url),
  "utf8",
);
const {
  renderReader,
  renderSrtHealth,
  renderStreamLeft,
} = await import(`data:text/javascript;base64,${Buffer.from(rendererSource).toString("base64")}`);


const publisher = renderSrtHealth({
  rx_mbps: 4.2,
  link_capacity_mbps: 12.8,
  reserve_ratio: 3.047,
  rtt_ms: 28,
  retrans_packets: 3,
  drop_packets: 0,
  belated_packets: 2,
}, "rx_mbps");

assert.match(publisher, /RX: 4\.20 Mbit\/s/);
assert.match(publisher, /Reserve: 3\.0×/);
assert.match(publisher, /Retrans: 3 pkt/);
assert.match(publisher, /Drop: 0 pkt/);
assert.match(publisher, /Belated: 2 pkt/);

const withoutBelated = renderSrtHealth({belated_packets: 0}, "rx_mbps");
assert.doesNotMatch(withoutBelated, /Belated/);
assert.equal(renderSrtHealth({}, "rx_mbps"), "");

const readerWithNativeRate = renderReader({
  type: "srtConn",
  details: {remoteAddr: "192.0.2.1:9000", bytesSent: 999999},
  bitrate_mbps: 9.99,
  srt_health: {
    tx_mbps: 4.25,
    link_capacity_mbps: 11.4,
    reserve_ratio: 2.68,
    rtt_ms: 31,
    retrans_packets: 2,
    drop_packets: 0,
  },
});

assert.match(readerWithNativeRate, /TX: 4\.25 Mbit\/s/);
assert.doesNotMatch(readerWithNativeRate, /9\.99/);
assert.match(readerWithNativeRate, /Reserve: 2\.7×/);
assert.match(readerWithNativeRate, /Gesendet: 976\.5615 KB/);

const readerWithCalculatedRate = renderReader({
  type: "srtConn",
  details: {remoteAddr: "192.0.2.2:9000", bytesSent: 2048},
  bitrate_mbps: 3.5,
  srt_health: {drop_packets: 1},
});

assert.match(readerWithCalculatedRate, /TX: 3\.50 Mbit\/s/);
assert.match(readerWithCalculatedRate, /Drop: 1 pkt/);
assert.match(readerWithCalculatedRate, /Gesendet: 2\.0000 KB/);

const publisherHtml = renderStreamLeft({
  name: "camera/srt",
  source: {
    type: "srtConn",
    bitrate_mbps: 3.75,
    transport_rtt_ms: 24,
    details: {remoteAddr: "192.0.2.3:9000", bytesReceived: 4096},
    srt_health: {link_capacity_mbps: 12.5, retrans_packets: 0},
  },
  media: {},
});

assert.match(publisherHtml, /RX: 3\.75 Mbit\/s/);
assert.match(publisherHtml, /Link: 12\.50 Mbit\/s/);
assert.match(publisherHtml, /RTT: 24 ms/);
assert.match(publisherHtml, /Retrans: 0 pkt/);
assert.match(publisherHtml, /Empfangen: 4\.0000 KB/);

const nonSrtReader = renderReader({
  type: "rtmpConn",
  details: {remoteAddr: "192.0.2.4:1935", outboundBytes: 1024},
  bitrate_mbps: 2.5,
});

assert.match(nonSrtReader, /Rate: 2\.50 Mbps/);
assert.match(nonSrtReader, /Gesendet: 1\.0000 KB/);
assert.doesNotMatch(nonSrtReader, /TX:/);
