# /opt/mediamtx-monitoring-backend/bin/bitrate.py
"""
bitrate.py – Einfache, generische Bitratenberechnung (Publisher & Reader)

Dieses Modul berechnet eine Bitrate (in Mbit/s) aus kumulierten Byte-Zählern
(z. B. bytesReceived/bytesSent) mittels Delta über die Zeit (ΔBytes / Δt).
Der Zustand (letzter Zählerstand und Zeitstempel) wird in Redis gehalten.

Einsatz:
- Einheitliche Berechnung für eingehende Verbindungen (Publisher/Source)
  und ausgehende Verbindungen (Reader).
- API‑Werte (z. B. SRT mbpsSendRate/mbpsReceiveRate) können im Collector
  bevorzugt werden; dieses Modul liefert nur die Delta‑Berechnung.

Persistenz in Redis:
- <key>:prev_bytes  → letzter bekannter Byte‑Zähler (int)
- <key>:prev_ts     → zugehöriger Zeitstempel (float, Sekunden seit Epoch)
- <key>:ewma_mbps   → optionaler geglätteter Mbit/s‑Wert (float)

Empfehlung:
- Im Collector den Schlüssel-Namespace unterscheiden:
  "pub:<stream>:<type>:<connID>" für Publisher
  "rd:<stream>:<type>:<id>"     für Reader
"""

from __future__ import annotations

import time
import logging
from typing import Optional


def calc_bitrate(
    r,
    key: str,
    bytes_now: int,
    now: Optional[float] = None,
    min_dt: float = 0.5,
    smooth_alpha: Optional[float] = None,
    ttl: int = 300,
) -> Optional[float]:
    """
    Berechnet die Bitrate in Mbit/s aus einem kumulierten Byte-Zähler.

    Das Verfahren nutzt den zuletzt in Redis gespeicherten Zustand (<key>:prev_bytes,
    <key>:prev_ts). Nach der Berechnung wird der Zustand aktualisiert. Optional kann
    eine EWMA-Glättung (Exponentially Weighted Moving Average) angewendet werden.

    Parameter
    ---------
    r : redis.Redis
        Offene Redis-Verbindung (decode_responses=True empfohlen).
    key : str
        Eindeutiger Schlüssel je Verbindung, z. B. "pub:stream:rtmpConn:abc123".
    bytes_now : int
        Aktueller kumulierter Byte-Zähler (z. B. bytesReceived/bytesSent).
    now : float | None
        Aktueller Zeitstempel in Sekunden (time.time()). Wird None übergeben,
        wird time.time() verwendet (Standard).
    min_dt : float
        Minimales Δt in Sekunden. Liegt die Zeitdifferenz darunter, wird None
        zurückgegeben (Messung zu kurz/instabil).
    smooth_alpha : float | None
        Alpha (0..1) für EWMA-Glättung. None deaktiviert die Glättung.
        Typisch: 0.3..0.7 (z. B. 0.5).
    ttl : int
        Ablaufzeit (Sekunden) für die gespeicherten Redis-Keys, verhindert Altlasten.

    Rückgabewert
    ------------
    float | None
        Bitrate in Mbit/s, auf zwei Nachkommastellen gerundet, oder None, wenn
        keine valide Berechnung möglich war (zu kleines Δt, Reset, Fehler).

    Hinweise
    --------
    - Negative Deltas (Zähler-Reset/Neuverbindung) werden verworfen (None).
    - Die Funktion ist zustandsbehaftet über Redis (prev_bytes/prev_ts).
    - API-Bitratenschätzer (z. B. SRT mbps*Rate) sollten im Collector bevorzugt
      verwendet werden; diese Funktion liefert nur die Delta-Schätzung.
    """
    # Eingangsvalidierung
    if key is None or key == "":
        logging.debug("calc_bitrate: leerer Schlüssel")
        return None
    if bytes_now is None:
        logging.debug("calc_bitrate: bytes_now ist None")
        return None

    now = time.time() if now is None else float(now)

    try:
        # Vorzustand lesen
        prev_bytes_str = r.get(f"{key}:prev_bytes")
        prev_ts_str = r.get(f"{key}:prev_ts")

        # Wenn noch kein Zustand existiert, initialisieren und keine Rate liefern
        if prev_bytes_str is None or prev_ts_str is None:
            _store_state(r, key, int(bytes_now), now, ttl)
            return None

        prev_bytes = int(prev_bytes_str)
        prev_ts = float(prev_ts_str)
        dt = now - prev_ts

        # Zu kurze Messintervalle vermeiden
        if dt < min_dt:
            return None

        delta = int(bytes_now) - prev_bytes
        # Counter-Reset / Neuverbindung → keine negative Rate melden
        if delta < 0:
            _store_state(r, key, int(bytes_now), now, ttl)
            return None

        # Bitrate in Mbit/s
        mbps = (delta * 8) / (dt * 1_000_000)

        # Optionale EWMA-Glättung
        if smooth_alpha is not None:
            try:
                prev_mbps_str = r.get(f"{key}:ewma_mbps")
                if prev_mbps_str is not None:
                    prev_mbps = float(prev_mbps_str)
                    alpha = float(smooth_alpha)
                    # EWMA: aktueller Wert stärker gewichten je nach alpha
                    mbps = alpha * mbps + (1.0 - alpha) * prev_mbps
                # Geglätteten Wert speichern
                r.set(f"{key}:ewma_mbps", mbps, ex=ttl)
            except Exception as e:
                # Glättung ist optional – bei Fehlern nur protokollieren
                logging.debug(f"calc_bitrate: EWMA-Fehler für {key}: {e}")

        # Zustand aktualisieren (prev_bytes/prev_ts)
        _store_state(r, key, int(bytes_now), now, ttl)

        # Zwei Nachkommastellen genügen für Anzeige/Logging
        return round(mbps, 2)

    except Exception as e:
        logging.debug(f"calc_bitrate: Fehler bei {key}: {e}")
        # Bei Fehlern Zustand dennoch aktualisieren, damit sich das System fängt
        try:
            _store_state(r, key, int(bytes_now), now, ttl)
        except Exception:
            # Sekundärfehler beim Speichern ignorieren, aber nicht verschlucken
            logging.debug("calc_bitrate: zusätzlicher Fehler beim Speichern des Zustands", exc_info=True)
        return None


def reset_state(r, key: str) -> None:
    """
    Löscht den gespeicherten Zustand (prev_bytes/prev_ts/ewma_mbps) für einen Schlüssel.

    Nützlich bei manuellen Resets, Tests oder wenn Verbindungen bewusst neu gestartet werden.
    """
    try:
        r.delete(f"{key}:prev_bytes")
        r.delete(f"{key}:prev_ts")
        r.delete(f"{key}:ewma_mbps")
    except Exception as e:
        logging.debug(f"reset_state: Fehler beim Löschen des Zustands für {key}: {e}")


def _store_state(r, key: str, bytes_now: int, ts: float, ttl: int) -> None:
    """
    Interne Hilfsfunktion: speichert prev_bytes/prev_ts atomar (Pipeline) mit TTL.
    """
    try:
        pipe = r.pipeline()
        pipe.set(f"{key}:prev_bytes", bytes_now, ex=ttl)
        pipe.set(f"{key}:prev_ts", ts, ex=ttl)
        pipe.execute()
    except Exception as e:
        logging.debug(f"_store_state: Fehler beim Speichern des Zustands für {key}: {e}")
