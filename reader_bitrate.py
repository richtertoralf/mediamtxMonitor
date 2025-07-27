# /opt/mediamtx-monitoring-backend/bin/reader_bitrate.py
import time
import logging

def calculate_reader_bitrate(r, reader_id, reader_bytes, now=None):
    """
    Berechnet die Bitrate eines Readers basierend auf Redis-Zwischenspeicher bzw.
    der gesendeten Bytes. Gibt Mbps zurück oder None bei Fehler.

    Args:
        r: Redis-Verbindung
        reader_id: eindeutige Reader-ID (z. B. SRT, RTMP, HLS)
        reader_bytes: aktueller bytesSent-Wert aus API
        now: aktueller Zeitstempel (float, Sekunden) – optional (für Tests)

    Returns:
        float | None: berechnete Bitrate in Mbps (gerundet), oder None bei Fehler
    """
    now = now or time.time()
    try:
        prev_bytes = int(r.get(f"mediamtx:readers:prev_bytes:{reader_id}") or 0)
        prev_ts = float(r.get(f"mediamtx:readers:prev_ts:{reader_id}") or now)
        time_diff = now - prev_ts
        if time_diff > 0:
            bitrate_bps = (reader_bytes - prev_bytes) * 8 / time_diff
            bitrate_mbps = round(bitrate_bps / 1_000_000, 2)
            logging.debug(f"[Reader {reader_id}] Δbytes={reader_bytes - prev_bytes}, Δt={time_diff:.2f}s → {bitrate_mbps} Mbps")
            return bitrate_mbps
    except Exception as e:
        logging.warning(f"⚠️ Fehler bei Reader-Bitrate für {reader_id}: {e}")
    return None


def store_reader_state(r, reader_id, reader_bytes, now=None):
    """
    Speichert den aktuellen Zustand des Readers für die nächste Berechnung.
    """
    now = now or time.time()
    try:
        r.set(f"mediamtx:readers:prev_bytes:{reader_id}", reader_bytes)
        r.set(f"mediamtx:readers:prev_ts:{reader_id}", now)
    except Exception as e:
        logging.error(f"❌ Redis-Speicherfehler für Reader {reader_id}: {e}")
