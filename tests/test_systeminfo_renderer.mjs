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
