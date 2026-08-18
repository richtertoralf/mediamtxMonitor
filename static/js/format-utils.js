/**
 * MediaMTX Monitor - Shared formatting utilities.
 *
 * Provides side-effect-free value formatting and safe HTML string handling.
 */

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

export function optionalNumber(value) {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function firstAvailable(...values) {
  return values.find(value => value !== null && value !== undefined) ?? null;
}

export function formatNumber(value, digits) {
  const number = optionalNumber(value);
  return number == null ? null : number.toFixed(digits);
}

export function formatCount(value) {
  const number = optionalNumber(value);
  return number == null ? null : `${number}`;
}

export function formatBytes(bytes) {
  let value = optionalNumber(bytes);
  if (value == null) return null;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let unitIndex = 0;
  while (Math.abs(value) >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex++;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 2)} ${units[unitIndex]}`;
}

export function formatConnectionAge(created, nowMs = Date.now()) {
  if (!created) return null;
  const createdAt = Date.parse(created);
  if (!Number.isFinite(createdAt)) return null;
  const seconds = Math.max(0, Math.floor((nowMs - createdAt) / 1000));
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h`;
  return `${Math.floor(seconds / 86400)} d`;
}

export function formatRelativeTime(value, nowMs = Date.now()) {
  if (!value) return null;
  const timestamp = Date.parse(value);
  const currentTime = optionalNumber(nowMs);
  if (!Number.isFinite(timestamp) || currentTime == null) return null;
  const seconds = Math.max(0, Math.floor((currentTime - timestamp) / 1000));
  if (seconds < 60) return `vor ${seconds} s`;
  if (seconds < 3600) return `vor ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `vor ${Math.floor(seconds / 3600)} h`;
  return `vor ${Math.floor(seconds / 86400)} d`;
}

export function formatDataAge(collectedAt, nowMs = Date.now()) {
  const timestamp = optionalNumber(collectedAt);
  const currentTime = optionalNumber(nowMs);
  if (timestamp == null || currentTime == null) return null;
  const ageSeconds = Math.max(0, currentTime / 1000 - timestamp);
  return `Datenalter: ${ageSeconds.toFixed(1)} s`;
}

export function dataAgeStatusClass(collectedAt, nowMs = Date.now()) {
  const timestamp = optionalNumber(collectedAt);
  const currentTime = optionalNumber(nowMs);
  if (timestamp == null || currentTime == null) return "data-age-unknown";
  const ageSeconds = Math.max(0, currentTime / 1000 - timestamp);
  if (ageSeconds < 3) return "data-age-fresh";
  if (ageSeconds <= 10) return "data-age-warning";
  return "data-age-stale";
}
