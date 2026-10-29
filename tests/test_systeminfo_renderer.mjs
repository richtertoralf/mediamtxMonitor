import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";


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

const container = new FakeElement("section");
globalThis.document = {
  createElement: tagName => new FakeElement(tagName),
  getElementById: id => {
    assert.equal(id, "systeminfo");
    return container;
  },
};

const source = await readFile(
  new URL("../static/js/systeminfo.js", import.meta.url),
  "utf8",
);
const {renderSystemInfo} = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);

const identityValueFor = serverIps => {
  renderSystemInfo(
    {host: "mediamtx-01", server_ips: serverIps},
    "Datenalter: 6.2 s",
    "data-age-warning",
  );
  return container.children[0].children[0];
};

let identity = identityValueFor(["192.0.2.10"]);
assert.equal(identity.children[0].textContent, "MediaMTX Server");
assert.equal(identity.children[1].textContent, "mediamtx-01 · 192.0.2.10");
assert.equal(identity.children[2].textContent, "Datenalter: 6.2 s");
assert.match(identity.children[2].className, /data-age-warning/);

identity = identityValueFor(["192.168.95.18", "172.16.90.18"]);
assert.equal(
  identity.children[1].textContent,
  "mediamtx-01 · 192.168.95.18 · 172.16.90.18",
);

identity = identityValueFor([
  "159.69.199.209",
  "192.168.97.3",
  "172.16.90.17",
]);
assert.equal(
  identity.children[1].textContent,
  "mediamtx-01 · 159.69.199.209 · 192.168.97.3 · 172.16.90.17",
);

identity = identityValueFor([]);
assert.equal(identity.children[1].textContent, "mediamtx-01 · –");

renderSystemInfo(null);
const fallbackIdentity = container.children[0].children[0];
assert.equal(fallbackIdentity.children[1].textContent, "– · –");
assert.equal(fallbackIdentity.children[2].textContent, "Datenalter: —");

// CPU mit Bezugsbasis, Werten je Kern, getrennter Steal-Zeit, PSI und Hinweisen.
const entries = column => Object.fromEntries(
  column.children.reduce((pairs, child, index, all) =>
    index % 2 === 0
      ? [...pairs, [child.textContent, all[index + 1].textContent.replace(/\s/gu, " ")]]
      : pairs, []),
);
renderSystemInfo({
  host: "mediamtx-01",
  cpu_percent: 87.5,
  cpu: {
    logical_cores: 4,
    per_core: [{busy: 99.4}, {busy: 97.0}, {busy: 98.2}, {busy: 96.1}],
    busy_percent: 97.7, steal_percent: 12.3, iowait_percent: 0.4,
    pressure: {some_avg10: 31.2, some_avg60: 18.0},
    hints: ["saturation", "steal", "pressure", "unbekannt"],
  },
}, "Datenalter: 1.0 s", "data-age-fresh", 3);
const section = container.children[0];
const left = entries(section.children[1]);
const right = entries(section.children[2]);
assert.equal(left["CPU-Auslastung"], "87.5 % von 4 vCPU");
assert.equal(left["Je Kern"], "99 · 97 · 98 · 96 %");
assert.equal(left["Steal / I/O-Wait"], "12.3 % / 0.4 %");
assert.equal(left["CPU-Druck (PSI)"], "10s 31.2 % · 60s 18.0 %");
assert.equal(right["Vorschau-Transcoder"], "3");
const hints = section.children.slice(3).map(child => child.textContent);
assert.equal(hints.length, 3);
assert.match(hints[0], /CPU-Sättigung/);
assert.match(hints[1], /Steal-Zeit/);
assert.match(hints[2], /CPU-Druck/);

// Ohne neue Felder bleibt die bisherige Anzeige erhalten.
renderSystemInfo({cpu_percent: 12});
const plain = entries(container.children[0].children[1]);
assert.equal(plain["CPU-Auslastung"], "12.0 %");
assert.equal(plain["CPU-Druck (PSI)"], "nicht verfügbar");
assert.equal(entries(container.children[0].children[2])["Vorschau-Transcoder"], "–");
assert.equal(container.children[0].children.length, 3);
