/**
 * MediaMTX Monitor - Media track summaries.
 *
 * Formats video, audio, and other tracks without connection rendering.
 */

import {escapeHtml, optionalNumber} from "./format-utils.js";

function formatSampleRate(sampleRate) {
  const value = optionalNumber(sampleRate);
  if (value == null || value <= 0) return null;
  if (value >= 1000) return `${Number((value / 1000).toFixed(1))} kHz`;
  return `${value} Hz`;
}

function formatChannels(channelCount) {
  const value = optionalNumber(channelCount);
  if (value == null || value <= 0) return null;
  if (value === 1) return "Mono";
  if (value === 2) return "Stereo";
  return `${value} Kanäle`;
}

export function renderMedia(stream) {
  const media = stream?.media || {};
  const lines = [];

  for (const track of media.video || []) {
    const parts = [track.displayCodec || track.codec].filter(Boolean);
    if (track.width != null && track.height != null) {
      parts.push(`${track.width}×${track.height}`);
    } else if (track.width != null) {
      parts.push(`${track.width} px breit`);
    } else if (track.height != null) {
      parts.push(`${track.height} px hoch`);
    }
    if (parts.length) lines.push(parts.join(" · "));
  }

  for (const track of media.audio || []) {
    const parts = [track.displayCodec || track.codec].filter(Boolean);
    const sampleRate = formatSampleRate(track.sampleRate);
    const channels = formatChannels(track.channelCount);
    if (sampleRate) parts.push(sampleRate);
    if (channels) parts.push(channels);
    if (parts.length) lines.push(parts.join(" · "));
  }

  for (const track of media.other || []) {
    const codec = track.displayCodec || track.codec;
    if (codec) lines.push(codec);
  }

  if (!lines.length && Array.isArray(stream?.tracks) && stream.tracks.length) {
    lines.push(stream.tracks.join(" · "));
  }

  if (!lines.length) return '<div class="media-empty">Keine Media-Details</div>';
  return `<div class="media-lines">${lines.map(line =>
    `<div>${escapeHtml(line)}</div>`).join("")}</div>`;
}
