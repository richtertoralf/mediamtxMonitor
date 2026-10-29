"""
MediaMTX Monitor - MediaMTX v1.21+ data model knowledge.

Defines supported versions and Control API endpoints, indexes connection
details referenced by paths, and builds the compact track and media model.

Does not perform HTTP requests, polling, Redis I/O, or metric calculation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional, Tuple


MINIMUM_MEDIAMTX_VERSION: Tuple[int, int, int] = (1, 21, 0)

DETAIL_ENDPOINTS = {
    "srtConn": "/v3/srt/conns/list",
    "rtmpConn": "/v3/rtmp/conns/list",
    "rtmpsConn": "/v3/rtmps/conns/list",
    "rtspConn": "/v3/rtsp/conns/list",
    "rtspSession": "/v3/rtsp/sessions/list",
    "rtspsConn": "/v3/rtsps/conns/list",
    "rtspsSession": "/v3/rtsps/sessions/list",
    "webRTCSession": "/v3/webrtc/sessions/list",
    "hlsSession": "/v3/hls/sessions/list",
    "moqSession": "/v3/moq/sessions/list",
}

HLS_MUXER_ENDPOINT = "/v3/hls/muxers/list"
STATIC_SOURCE_ENDPOINT = "/v3/paths/static-sources/get/"

# Sources that MediaMTX pulls itself. Those with a connection-like transport
# map to the connection type whose native fields their typeSpecific shares.
STATIC_SOURCE_CONNECTION_TYPES: Dict[str, Optional[str]] = {
    "rtspSource": "rtspSession",
    "srtSource": "srtConn",
    "webRTCSource": "webRTCSession",
    "rtmpSource": "rtmpConn",
    "moqSource": "moqSession",
    "hlsSource": None,
    "mpegtsSource": None,
    "rtpSource": None,
    "rpiCameraSource": None,
}

# A URL query can carry user/pass or JWT parameters; marker names guard
# against future native fields with credentials. Neither is ever displayed.
SENSITIVE_DETAIL_FIELDS = frozenset({"query"})
SENSITIVE_FIELD_MARKERS = ("pass", "token", "secret", "jwt", "credential")

# MediaMTX does not register these routes when the corresponding TLS listener
# is disabled. In that case, a 404 means an empty protocol list.
OPTIONAL_SECURE_ENDPOINTS = {
    "/v3/rtmps/conns/list",
    "/v3/rtsps/conns/list",
    "/v3/rtsps/sessions/list",
}

VIDEO_CODECS = {
    "AV1": "AV1",
    "VP9": "VP9",
    "VP8": "VP8",
    "H265": "H.265 / HEVC",
    "H264": "H.264",
    "MPEG-4 Video": "MPEG-4 Video",
    "MPEG-1/2 Video": "MPEG-1/2 Video",
    "M-JPEG": "M-JPEG",
}

AUDIO_CODECS = {
    "Opus": "Opus",
    "FLAC": "FLAC",
    "Vorbis": "Vorbis",
    "MPEG4Audio": "AAC",
    "MPEG-4 Audio": "AAC",
    "MPEG-4 Audio LATM": "AAC-LATM",
    "MPEG-1/2 Audio": "MPEG Audio",
    "AC3": "AC-3",
    "Speex": "Speex",
    "G726": "G.726",
    "G722": "G.722",
    "G711": "G.711",
    "LPCM": "LPCM",
}


def parse_version(value: Any) -> Optional[Tuple[int, int, int]]:
    """Return the numeric SemVer core accepted from ``/v3/info``."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", str(value or ""))
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def is_supported_version(value: Any) -> bool:
    """Return whether a MediaMTX version meets the supported minimum."""
    parsed = parse_version(value)
    return parsed is not None and parsed >= MINIMUM_MEDIAMTX_VERSION


def is_sensitive_field(name: Any) -> bool:
    """Report whether a native field may carry credentials or tokens."""
    lowered = str(name).lower()
    return lowered in SENSITIVE_DETAIL_FIELDS or any(
        marker in lowered for marker in SENSITIVE_FIELD_MARKERS
    )


_URL_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+")
_USERINFO_PATTERN = re.compile(r"\S+:\S*@\S+")
_QUERY_PATTERN = re.compile(r"[?&][^\s=&]+=[^\s&]*")
MAX_ERROR_TEXT_LENGTH = 200


def redact_error_text(text: Any) -> Optional[str]:
    """Return a native error text without URLs, userinfo, or query values.

    Source URLs can contain credentials, so they are replaced; addresses and
    the error reason itself stay readable.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    redacted = _URL_PATTERN.sub("<URL>", text.strip())
    redacted = _USERINFO_PATTERN.sub("<URL>", redacted)
    redacted = _QUERY_PATTERN.sub("", redacted)
    return redacted[:MAX_ERROR_TEXT_LENGTH]


def sanitize_static_source(item: Any) -> Dict[str, Any]:
    """Build source details from one static-source object without secrets."""
    if not isinstance(item, Mapping) or item.get("state") is None:
        return {}
    transport = item.get("typeSpecific")
    details = sanitize_details(transport) if isinstance(transport, Mapping) else {}
    details["state"] = item["state"]
    if item.get("created") is not None:
        details["created"] = item["created"]
    error = redact_error_text(item.get("lastError"))
    if error:
        details["last_error"] = error
    return details


def sanitize_details(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a connection object without fields that may carry secrets."""
    return {key: value for key, value in item.items() if not is_sensitive_field(key)}


def index_details(items_by_type: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Index every protocol response by the ID referenced by Path objects.

    This is the single entry point of connection details into the snapshot,
    so sensitive native fields are removed here before Redis, JSON output, or
    the monitor API can see them.
    """
    return {
        obj_type: {
            str(item.get("id")): sanitize_details(item)
            for item in items
            if isinstance(item, dict) and item.get("id") is not None
        }
        for obj_type, items in items_by_type.items()
    }


def get_details_by_type(
    obj_type: Optional[str], obj_id: Optional[str], details: Mapping[str, Any]
) -> Dict[str, Any]:
    """Resolve a Path source or reader to its protocol session/connection."""
    return details.get(obj_type or "", {}).get(str(obj_id or ""), {})


def track_codecs(tracks2: Any) -> list[str]:
    """Provide the compact codec list expected by the existing renderer."""
    if not isinstance(tracks2, list):
        return []
    return [
        str(track["codec"])
        for track in tracks2
        if isinstance(track, dict) and track.get("codec")
    ]


def build_media_model(tracks2: Any) -> Dict[str, list[Dict[str, Any]]]:
    """Build a compact UI model without discarding unknown track codecs."""
    media: Dict[str, list[Dict[str, Any]]] = {
        "video": [],
        "audio": [],
        "other": [],
    }
    if not isinstance(tracks2, list):
        return media

    for track in tracks2:
        if not isinstance(track, dict) or not track.get("codec"):
            continue

        codec = str(track["codec"])
        props = track.get("codecProps") or {}
        item: Dict[str, Any] = {"codec": codec}

        if codec in VIDEO_CODECS:
            item["displayCodec"] = VIDEO_CODECS[codec]
            for key in ("width", "height", "profile", "level"):
                if props.get(key) is not None:
                    item[key] = props[key]
            media["video"].append(item)
        elif codec in AUDIO_CODECS:
            item["displayCodec"] = AUDIO_CODECS[codec]
            for key in ("sampleRate", "channelCount"):
                if props.get(key) is not None:
                    item[key] = props[key]
            media["audio"].append(item)
        else:
            item["displayCodec"] = codec
            media["other"].append(item)

    return media
