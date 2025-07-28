/**
 * 🖥️ systeminfo.js – Rendert Systeminformationen im Dashboard
 * 
 * Dieses Modul erzeugt dynamisch HTML aus einem JSON-Objekt mit Systeminfos.
 * Ziel ist eine klar strukturierte, semantisch sinnvolle Darstellung.
 * 
 * Autor: snowgames.live
 * Lizenz: MIT
 */

export function renderSystemInfo(systeminfo = {}) {
  const container = document.getElementById("systeminfo");
  container.innerHTML = ""; // vorherigen Inhalt löschen

  if (!systeminfo || Object.keys(systeminfo).length === 0) {
    return;
  }

  const section = document.createElement("section");
  section.className = "systeminfo";

  const dl = document.createElement("dl");

  const entries = [
    ["CPU-Auslastung", formatPercent(systeminfo.cpu_percent)],
    ["RAM (genutzt)", formatBytes(systeminfo.memory?.used) + " / " + formatBytes(systeminfo.memory?.total)],
    ["Swap", formatBytes(systeminfo.swap?.used) + " / " + formatBytes(systeminfo.swap?.total)],
    ["Festplatte", formatBytes(systeminfo.disk?.used) + " / " + formatBytes(systeminfo.disk?.total)],
    ["Load Average", systeminfo.loadavg?.map(n => n.toFixed(2)).join(" / ") ?? "–"],
    ["Netzwerk RX", formatBytes(systeminfo.net_io?.bytes_recv) + "/min"],
    ["Netzwerk TX", formatBytes(systeminfo.net_io?.bytes_sent) + "/min"],
    ["Temperatur", (systeminfo.temperature?.celsius ?? "–") + " °C"]
  ];

  for (const [label, value] of entries) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    dl.appendChild(dt);
    dl.appendChild(dd);
  }

  section.appendChild(dl);
  container.appendChild(section);
}

function formatBytes(bytes) {
  if (!bytes || isNaN(bytes)) return "–";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return bytes.toFixed(1) + " " + units[i];
}

function formatPercent(val) {
  return (typeof val === "number" && !isNaN(val)) ? val.toFixed(1) + " %" : "–";
}
