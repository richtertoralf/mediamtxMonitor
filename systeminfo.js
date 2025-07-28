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
    ["CPU-Auslastung", systeminfo.cpu_percent?.toFixed(1) + " %" ?? "–"],
    ["RAM (genutzt)", formatBytes(systeminfo.memory_used_bytes) + " / " + formatBytes(systeminfo.memory_total_bytes)],
    ["Swap", formatBytes(systeminfo.swap_used_bytes) + " / " + formatBytes(systeminfo.swap_total_bytes)],
    ["Festplatte", formatBytes(systeminfo.disk_used_bytes) + " / " + formatBytes(systeminfo.disk_total_bytes)],
    ["Load Average", systeminfo.loadavg?.join(" / ") ?? "–"],
    ["Netzwerk RX", formatBytes(systeminfo.network_rx_bytes) + "/min"],
    ["Netzwerk TX", formatBytes(systeminfo.network_tx_bytes) + "/min"],
    ["Temperatur", systeminfo.temperature_celsius ? systeminfo.temperature_celsius + " °C" : "–"]
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
