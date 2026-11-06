/**
 * MediaMTX Monitor - Kopfband nach dem UI-Standard von RICHTER.PROJECTS.
 *
 * Links Anwendung und Version (renderMonitorTitle), Mitte Server, MediaMTX-
 * Version und Streamzahl, rechts Datenalter mit Uhrzeit der Erfassung.
 * Datenalter: frisch neutral mit Punkt, Warnung bernstein, stale als Warnung
 * mit Text, unbekannt grau. Keine Zustandsfarbe für normale Werte.
 */

import {dataAgeStatusClass, formatDataAge, optionalNumber} from "./format-utils.js";

function formatClock(collectedAt) {
  const seconds = optionalNumber(collectedAt);
  if (seconds == null) return "–";
  return new Date(seconds * 1000).toLocaleTimeString("de-DE", {hour12: false});
}

function item(label, value) {
  const wrapper = document.createElement("span");
  wrapper.className = "topbar-item";
  const labelElement = document.createElement("span");
  labelElement.className = "topbar-label";
  labelElement.textContent = label;
  const valueElement = document.createElement("span");
  valueElement.textContent = value;
  wrapper.appendChild(labelElement);
  wrapper.appendChild(valueElement);
  return wrapper;
}

/** Server, MediaMTX-Version und Streamzahl in der Mitte des Kopfbands. */
export function renderTopBarContext(result = {}, activeStreamCount = 0) {
  const container = document.getElementById("topbar-ctx");
  if (!container) return;
  container.innerHTML = "";
  const info = result?.systeminfo || {};
  const serverIps = Array.isArray(info.server_ips)
    ? info.server_ips.filter(value => typeof value === "string" && value).slice(0, 3)
    : [];
  container.appendChild(item("Server", `${info.host || "–"} · ${serverIps.join(" · ") || "–"}`));
  // MediaMTX reports its version with a leading "v" (e.g. "v1.21.3"); show it once.
  const rawVersion = typeof result?.mediamtx_version === "string" ? result.mediamtx_version.trim() : "";
  const version = rawVersion ? `v${rawVersion.replace(/^v/i, "")}` : "unbekannt";
  container.appendChild(item("MediaMTX", version));
  container.appendChild(item("Streams", `${activeStreamCount} aktiv`));
}

/** Datenalter mit Uhrzeit der Erfassung rechts im Kopfband. */
export function renderTopBarConnection(collectedAt, nowMs = Date.now()) {
  const container = document.getElementById("topbar-conn");
  if (!container) return;
  const statusClass = dataAgeStatusClass(collectedAt, nowMs);
  const ageText = formatDataAge(collectedAt, nowMs);
  container.className = `topbar-conn ${statusClass}`;
  container.innerHTML = "";
  const text = document.createElement("span");
  text.className = "data-age";
  text.setAttribute("aria-live", "polite");
  text.textContent = ageText == null
    ? "Datenalter unbekannt"
    : statusClass === "data-age-stale" ? `keine aktuellen Daten · ${ageText}` : ageText;
  const clock = document.createElement("span");
  clock.className = "topbar-clock";
  clock.textContent = formatClock(collectedAt);
  container.appendChild(text);
  container.appendChild(clock);
}

/** Version in der Fußzeile. */
export function renderFooterVersion(monitorVersion) {
  const element = document.getElementById("foot-version");
  if (!element) return;
  const version = typeof monitorVersion === "string" ? monitorVersion.trim() : "";
  element.textContent = version ? `MediaMTX Monitor v${version}` : "MediaMTX Monitor";
}
