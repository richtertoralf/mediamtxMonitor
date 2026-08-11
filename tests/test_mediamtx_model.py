import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))

from mediamtx_model import (  # noqa: E402
    DETAIL_ENDPOINTS,
    OPTIONAL_SECURE_ENDPOINTS,
    build_media_model,
    get_details_by_type,
    index_details,
    is_supported_version,
    parse_version,
    track_codecs,
)


class VersionTests(unittest.TestCase):
    def test_minimum_and_newer_versions_are_supported(self):
        self.assertTrue(is_supported_version("v1.20.0"))
        self.assertTrue(is_supported_version("1.21.3"))
        self.assertTrue(is_supported_version("2.0.0"))

    def test_older_or_invalid_versions_are_rejected(self):
        self.assertFalse(is_supported_version("1.19.9"))
        self.assertFalse(is_supported_version("unknown"))
        self.assertIsNone(parse_version(None))


class ModelTests(unittest.TestCase):
    def test_all_required_protocol_endpoints_are_present(self):
        self.assertEqual(DETAIL_ENDPOINTS, {
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
        })

    def test_disabled_secure_listeners_can_have_absent_routes(self):
        self.assertEqual(OPTIONAL_SECURE_ENDPOINTS, {
            "/v3/rtmpsconns/list",
            "/v3/rtspsconns/list",
            "/v3/rtspssessions/list",
        })

    def test_rtsp_details_are_indexed_by_session_id(self):
        session = {"id": "session-1", "inboundRTPPacketsLost": 2}
        details = index_details({"rtspSession": [session]})
        self.assertIs(
            get_details_by_type("rtspSession", "session-1", details), session
        )

    def test_tracks2_is_reduced_for_the_existing_ui(self):
        tracks = [{"codec": "H264", "codecProps": {"width": 1920}}, {"codec": "Opus"}]
        self.assertEqual(track_codecs(tracks), ["H264", "Opus"])


class MediaModelTests(unittest.TestCase):
    def test_h264_with_full_hd_dimensions(self):
        media = build_media_model([{
            "codec": "H264",
            "codecProps": {
                "width": 1920, "height": 1080,
                "profile": "High", "level": "4.2",
            },
        }])
        self.assertEqual(media["video"], [{
            "codec": "H264", "displayCodec": "H.264",
            "width": 1920, "height": 1080,
            "profile": "High", "level": "4.2",
        }])

    def test_aac_48_khz_stereo(self):
        media = build_media_model([{
            "codec": "MPEG4Audio",
            "codecProps": {"sampleRate": 48000, "channelCount": 2},
        }])
        self.assertEqual(media["audio"], [{
            "codec": "MPEG4Audio", "displayCodec": "AAC",
            "sampleRate": 48000, "channelCount": 2,
        }])

    def test_opus_without_codec_properties(self):
        media = build_media_model([{"codec": "Opus"}])
        self.assertEqual(
            media["audio"], [{"codec": "Opus", "displayCodec": "Opus"}]
        )

    def test_missing_codec_props_does_not_add_placeholders(self):
        media = build_media_model([{"codec": "H265", "codecProps": None}])
        self.assertEqual(media["video"], [{
            "codec": "H265", "displayCodec": "H.265 / HEVC",
        }])

    def test_unknown_codec_is_preserved(self):
        media = build_media_model([{"codec": "FutureCodec", "codecProps": {}}])
        self.assertEqual(media["other"], [{
            "codec": "FutureCodec", "displayCodec": "FutureCodec",
        }])


if __name__ == "__main__":
    unittest.main()
