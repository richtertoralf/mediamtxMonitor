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

export function renderSystemInfo(
  systeminfo = {},
  dataAgeText = "Datenalter: —",
  dataAgeClass = "data-age-unknown",
) {
  const container = document.getElementById("systeminfo");
  container.innerHTML = ""; // vorherigen Inhalt löschen
  const info = systeminfo || {};

  // 🧱 Haupt-Wrapper
  const section = document.createElement("section");
  section.className = "systeminfo";

  const identity = document.createElement("div");
  identity.className = "system-identity";
  const identityLabel = document.createElement("span");
  identityLabel.className = "system-identity-label";
  identityLabel.textContent = "MediaMTX Server";
  const identityValue = document.createElement("span");
  identityValue.className = "system-identity-value";
  const serverIps = Array.isArray(info.server_ips)
    ? info.server_ips.filter(value => typeof value === "string" && value).slice(0, 3)
    : [];
  identityValue.textContent = `${info.host || "–"} · ${serverIps.join(" · ") || "–"}`;
  const dataAge = document.createElement("span");
  dataAge.className = `data-age ${dataAgeClass}`;
  dataAge.setAttribute("aria-live", "polite");
  dataAge.textContent = dataAgeText;
  identity.appendChild(identityLabel);
  identity.appendChild(identityValue);
  identity.appendChild(dataAge);

  // 🔹 Linke Spalte – CPU, Load, RAM, Swap
  const leftColumn = document.createElement("div");
  leftColumn.className = "info-column left";

  const leftEntries = [
    ["CPU-Auslastung", formatPercent(info.cpu_percent)],
    ["Load Average", info.loadavg?.map(n => n.toFixed(2)).join(" / ") ?? "–"],
    ["RAM (genutzt)", formatBytes(info.memory?.used) + " / " + formatBytes(info.memory?.total)],
    ["Swap", formatBytes(info.swap?.used) + " / " + formatBytes(info.swap?.total)],
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
    ["Festplatte", formatBytes(info.disk?.used) + " / " + formatBytes(info.disk?.total)],
    ["Netzwerk RX", formatMbit(info.net_mbit_rx)],
    ["Netzwerk TX", formatMbit(info.net_mbit_tx)],
    ["Temperatur", (info.temperature_celsius ?? "–") + " °C"]
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
  section.appendChild(identity);
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
