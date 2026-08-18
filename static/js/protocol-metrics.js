/**
 * MediaMTX Monitor - Non-SRT protocol metrics.
 *
 * Presents RTMP(S), RTSP(S), WebRTC, MoQ, HLS, and path counters.
 */

import {connectionRate} from "./connection-metrics.js";
import {firstAvailable, formatBytes, formatConnectionAge, formatCount, formatNumber, formatRelativeTime, optionalNumber} from "./format-utils.js";
import {metric, metricFullRow, renderMetrics} from "./metric-grid.js";
import {renderJitterTrend, renderRateTrend} from "./sparkline-charts.js";

function renderCounterWindows(label, windows, field, unit = null) {
  const recent = windows?.["10s"]?.[field];
  const minute = windows?.["60s"]?.[field];
  if (recent == null && minute == null) return null;
  return metric(
    label,
    `10s ${formatCount(recent) ?? "—"} · 60s ${formatCount(minute) ?? "—"}`,
    unit,
  );
}

function renderConnectionStability(connection) {
  const stability = connection?.connection_stability;
  if (!stability) return "";
  const changes = optionalNumber(stability.changes_60s);
  const seconds = optionalNumber(stability.seconds_since_last_change);
  const value = changes == null || changes === 0
    ? "stable"
    : changes === 1 && seconds != null
      ? `changed ${Math.max(0, Math.floor(seconds))} s ago`
      : `${formatCount(changes)} changes / 60s`;
  return metric("Connection", value);
}

function renderFrameDiscardWindows(connection) {
  const windows = connection?.window_metrics?.frame_discard || {};
  const recent = windows["10s"];
  const minute = windows["60s"];
  if (recent == null && minute == null) {
    return null;
  }
  return metric(
    "Frame Discard",
    `10s ${formatCount(recent) ?? "—"} · 60s ${formatCount(minute) ?? "—"}`,
  );
}

function formatIceCandidate(candidate) {
  if (candidate == null) return null;
  if (typeof candidate !== "object") {
    const raw = String(candidate).trim();
    if (!raw) return null;
    const [type, protocol, address, port] = raw.split("/");
    if (type && protocol && address && port) {
      return `${type} · ${protocol.toUpperCase()} · ${address}:${port}`;
    }
    return raw;
  }
  const address = firstAvailable(candidate.address, candidate.ip);
  const endpoint = address == null
    ? null
    : candidate.port == null ? String(address) : `${address}:${candidate.port}`;
  const protocol = candidate.protocol == null
    ? null
    : String(candidate.protocol).toUpperCase();
  const parts = [candidate.type, protocol, endpoint].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

function iceMetric(metadata) {
  const local = formatIceCandidate(metadata.local_candidate);
  const remote = formatIceCandidate(metadata.remote_candidate);
  if (local && remote) return metric("ICE", `${local} ↔ ${remote}`);
  if (local) return metric("ICE Local", local);
  if (remote) return metric("ICE Remote", remote);
  return null;
}

export function renderNonSrtMetrics(connection, direction, totalBytes) {
  const details = connection?.details || {};
  const type = connection?.type;
  const rateLabel = direction === "in" ? "RX" : "TX";
  const rate = connectionRate(connection, direction);
  const protocol = connection?.protocol_metrics || {};
  const metadata = protocol.metadata || {};
  const gauges = protocol.gauges || {};
  const counterWindows = connection?.window_metrics?.protocol_counters || {};
  const metrics = [
    type === "hlsSession" && connection?.rate_metrics?.["10s"]?.average_mbps != null
      ? metric(
        `${rateLabel} Ø10s`,
        formatNumber(connection.rate_metrics["10s"].average_mbps, 2),
        "Mbit/s",
        null,
        null,
        rate == null ? null : `Aktuell: ${formatNumber(rate, 2)} Mbit/s`,
      )
      : metric(
        type === "hlsSession" ? `${rateLabel} aktuell` : rateLabel,
        rate == null ? "—" : formatNumber(rate, 2),
        "Mbit/s",
      ),
    metric("Total", formatBytes(totalBytes)),
  ];

  if (type === "rtmpConn" || type === "rtmpsConn") {
    metrics.push(metricFullRow(renderRateTrend(connection, direction)));
  }

  if (type === "rtspSession" || type === "rtspsSession") {
    if (direction === "in") {
      metrics.push(
        metric("Jitter", formatNumber(gauges.jitter_ms, 2), "ms"),
        metricFullRow(renderJitterTrend(connection)),
        renderCounterWindows("Loss", counterWindows, "loss", "pkt"),
        renderCounterWindows("RTP Error", counterWindows, "rtp_error"),
        renderCounterWindows("RTCP Error", counterWindows, "rtcp_error"),
      );
    } else {
      metrics.push(
        renderCounterWindows("Reported Loss", counterWindows, "reported_loss", "pkt"),
        renderCounterWindows("Discard", counterWindows, "discard"),
        renderCounterWindows("RTCP Error", counterWindows, "rtcp_error"),
      );
    }
  }

  if (type === "webRTCSession") {
    if (direction === "in") {
      metrics.push(
        metric("Jitter", formatNumber(gauges.jitter_ms, 2), "ms"),
        metricFullRow(renderJitterTrend(connection)),
        renderCounterWindows("RTP Loss", counterWindows, "rtp_loss", "pkt"),
      );
    } else {
      metrics.push(renderCounterWindows(
        "Frame Discard", counterWindows, "frame_discard",
      ));
    }
    const peer = metadata.peer_connection_established;
    metrics.push(
      metric("Peer", peer == null ? metadata.state : peer ? "established" : "not established"),
      iceMetric(metadata),
    );
  }

  if ((type === "rtmpConn" || type === "rtmpsConn") && direction === "out") {
    metrics.push(renderFrameDiscardWindows(connection));
  }

  if (type === "rtmpConn" || type === "rtmpsConn") {
    metrics.push(renderConnectionStability(connection) || metric("Connection", metadata.state));
  }
  if (type === "moqSession") {
    metrics.push(
      metric("Transport", metadata.transport),
      metric("Version", metadata.version),
      metric("State", metadata.state),
    );
  }
  metrics.push(metric("Age", formatConnectionAge(details.created)));
  return renderMetrics(metrics);
}

export function renderPathMetrics(stream) {
  const windows = stream?.path_metrics?.window_metrics?.protocol_counters || {};
  const item = renderCounterWindows("Path Frame Error", windows, "frame_error");
  return item ? renderMetrics([item]) : "";
}

export function renderHlsMuxer(stream) {
  const muxer = stream?.hls_muxer;
  if (!muxer) return "";
  const windows = muxer?.window_metrics?.protocol_counters || {};
  return `
    <section class="reader-block hls-muxer-block">
      <h3>HLS Muxer</h3>
      ${renderMetrics([
        renderCounterWindows("Mux Discard", windows, "mux_discard"),
        metric(
          "Last Request",
          formatRelativeTime(muxer.lastRequest),
          null,
          null,
          null,
          muxer.lastRequest,
        ),
      ])}
    </section>
  `;
}
