import assert from "node:assert/strict";

// Kopfband: Server und Adressen, MediaMTX-Version, Streamzahl; Datenalter mit Uhrzeit.
// Normale Werte ohne Zustandsfarbe; Warnung und stale als Warnung mit Text; unbekannt grau.

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.className = "";
    this.textContent = "";
    this.attributes = {};
  }

  appendChild(child) {
    this.children.push(child);
  }

  setAttribute(name, value) {
    this.attributes[name] = value;
  }

  set innerHTML(value) {
    assert.equal(value, "");
    this.children = [];
  }
}

const elements = {
  "topbar-ctx": new FakeElement("div"),
  "topbar-conn": new FakeElement("div"),
  "foot-version": new FakeElement("span"),
};
globalThis.document = {
  createElement: tagName => new FakeElement(tagName),
  getElementById: id => elements[id] ?? null,
};

const {renderFooterVersion, renderTopBarConnection, renderTopBarContext} = await import("../static/js/topbar.js");

const contextTexts = () => elements["topbar-ctx"].children.map(item =>
  item.children.map(child => child.textContent).join(" "));

renderTopBarContext({systeminfo: {host: "mediamtx-01", server_ips: ["192.0.2.10"]}, mediamtx_version: "1.21.0"}, 2);
assert.deepEqual(contextTexts(), ["Server mediamtx-01 · 192.0.2.10", "MediaMTX v1.21.0", "Streams 2 aktiv"]);

renderTopBarContext({systeminfo: {host: "mediamtx-01",
  server_ips: ["159.69.199.209", "192.168.97.3", "172.16.90.17", "10.0.0.9"]}}, 0);
assert.equal(contextTexts()[0], "Server mediamtx-01 · 159.69.199.209 · 192.168.97.3 · 172.16.90.17");
assert.equal(contextTexts()[1], "MediaMTX unbekannt");
assert.equal(contextTexts()[2], "Streams 0 aktiv");

renderTopBarContext({}, 0);
assert.equal(contextTexts()[0], "Server – · –");

const conn = elements["topbar-conn"];
const connTexts = () => conn.children.map(child => child.textContent);
const now = Date.UTC(2026, 10, 7, 9, 0, 10);

renderTopBarConnection(now / 1000 - 1.2, now);
assert.equal(conn.className, "topbar-conn data-age-fresh");
assert.equal(connTexts()[0], "Datenalter: 1.2 s");
assert.equal(conn.children[0].attributes["aria-live"], "polite");
assert.match(connTexts()[1], /^\d{2}:\d{2}:\d{2}$/);

renderTopBarConnection(now / 1000 - 6.2, now);
assert.equal(conn.className, "topbar-conn data-age-warning");
assert.equal(connTexts()[0], "Datenalter: 6.2 s");

renderTopBarConnection(now / 1000 - 42, now);
assert.equal(conn.className, "topbar-conn data-age-stale");
assert.equal(connTexts()[0], "keine aktuellen Daten · Datenalter: 42.0 s");

renderTopBarConnection(null, now);
assert.equal(conn.className, "topbar-conn data-age-unknown");
assert.deepEqual(connTexts(), ["Datenalter unbekannt", "–"]);

renderFooterVersion("0.8.8");
assert.equal(elements["foot-version"].textContent, "MediaMTX Monitor v0.8.8");
renderFooterVersion(undefined);
assert.equal(elements["foot-version"].textContent, "MediaMTX Monitor");
