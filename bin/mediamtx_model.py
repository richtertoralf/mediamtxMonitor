"""Pure helpers for the MediaMTX v1.20 monitoring model."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional, Tuple


MINIMUM_MEDIAMTX_VERSION: Tuple[int, int, int] = (1, 20, 0)

DETAIL_ENDPOINTS = {
    "srtConn": "/v3/srtconns/list",
    "rtmpConn": "/v3/rtmpconns/list",
    "rtmpsConn": "/v3/rtmpsconns/list",
    "rtspConn": "/v3/rtspconns/list",
    "rtspSession": "/v3/rtspsessions/list",
    "rtspsConn": "/v3/rtspsconns/list",
    "rtspsSession": "/v3/rtspssessions/list",
    "webRTCSession": "/v3/webrtcsessions/list",
    "hlsSession": "/v3/hlssessions/list",
    "moqSession": "/v3/moqsessions/list",
}

# MediaMTX does not register these routes when the corresponding TLS listener
# is disabled. In that case, a 404 means an empty protocol list.
OPTIONAL_SECURE_ENDPOINTS = {
    "/v3/rtmpsconns/list",
    "/v3/rtspsconns/list",
    "/v3/rtspssessions/list",
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
    parsed = parse_version(value)
    return parsed is not None and parsed >= MINIMUM_MEDIAMTX_VERSION


def index_details(items_by_type: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Index every protocol response by the ID referenced by Path objects."""
    return {
        obj_type: {
            str(item.get("id")): item
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
