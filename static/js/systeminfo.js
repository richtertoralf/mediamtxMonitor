/**
 * 🖥️ systeminfo.js – Rendert Systeminformationen im Dashboard
 *
 * Dieses Modul erzeugt eine zweispaltige Anzeige mit technischen Systemwerten:
 * - Spalte links: CPU, Load, RAM, Swap
 * - Spalte rechts: Festplatte, Netzwerk, Temperatur
 *
 * Autor: snowgames.live
 * Lizenz: MIT
 */

export function renderSystemInfo(systeminfo = {}) {
  const container = document.getElementById("systeminfo");
  container.innerHTML = ""; // vorherigen Inhalt löschen

  // Leere Daten? → nichts anzeigen
  if (!systeminfo || Object.keys(systeminfo).length === 0) {
    return;
  }

  // 🧱 Haupt-Wrapper
  const section = document.createElement("section");
  section.className = "systeminfo";

  // 🔹 Linke Spalte – CPU, Load, RAM, Swap
  const leftColumn = document.createElement("div");
  leftColumn.className = "info-column left";

  const leftEntries = [
    ["CPU-Auslastung", formatPercent(systeminfo.cpu_percent)],
    ["Load Average", systeminfo.loadavg?.map(n => n.toFixed(2)).join(" / ") ?? "–"],
    ["RAM (genutzt)", formatBytes(systeminfo.memory?.used) + " / " + formatBytes(systeminfo.memory?.total)],
    ["Swap", formatBytes(systeminfo.swap?.used) + " / " + formatBytes(systeminfo.swap?.total)],
  ];

  for (const [label, value] of leftEntries) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    leftColumn.appendChild(dt);
    leftColumn.appendChild(dd);
  }

  // 🔸 Rechte Spalte – Festplatte, Netzwerk, Temperatur
  const rightColumn = document.createElement("div");
  rightColumn.className = "info-column right";

  const rightEntries = [
    ["Festplatte", formatBytes(systeminfo.disk?.used) + " / " + formatBytes(systeminfo.disk?.total)],
    ["Netzwerk RX", formatMbit(systeminfo.net_mbit_rx)],
    ["Netzwerk TX", formatMbit(systeminfo.net_mbit_tx)],
    ["Temperatur", (systeminfo.temperature?.celsius ?? "–") + " °C"]
  ];

  for (const [label, value] of rightEntries) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    rightColumn.appendChild(dt);
    rightColumn.appendChild(dd);
  }

  // 📦 Spalten zusammenführen
  section.appendChild(leftColumn);
  section.appendChild(rightColumn);
  container.appendChild(section);
}

// 📐 Formatierungsfunktionen

function formatMbit(val) {
  return (typeof val === "number" && !isNaN(val)) ? val.toFixed(2) + " Mbit/s" : "–";
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
