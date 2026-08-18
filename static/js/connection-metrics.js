/**
 * MediaMTX Monitor - Shared connection metric selection.
 *
 * Selects directional rates and byte totals from the existing API contract.
 */

import {firstAvailable} from "./format-utils.js";

export function connectionRate(connection, direction) {
  const details = connection?.details || {};
  const health = connection?.srt_health || {};
  const nativeRate = direction === "in"
    ? firstAvailable(health.rx_mbps, details.mbpsReceiveRate)
    : firstAvailable(health.tx_mbps, details.mbpsSendRate);
  return firstAvailable(
    nativeRate,
    direction === "in" ? connection?.common?.rx_mbit_s : connection?.common?.tx_mbit_s,
    connection?.bitrate_mbps,
  );
}

export function connectionTotal(connection, direction, stream) {
  const details = connection?.details || {};
  if (direction === "in") {
    return firstAvailable(
      connection?.common?.total_bytes,
      details.inboundBytes,
      connection?.type === "srtConn" ? details.bytesReceived : null,
      stream?.inboundBytes,
    );
  }
  return firstAvailable(
    connection?.common?.total_bytes,
    details.outboundBytes,
    connection?.type === "srtConn" ? details.bytesSent : null,
  );
}
