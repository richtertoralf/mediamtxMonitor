import unittest

from bin.mediamtx_model import index_details
from bin.stream_normalizer import (
    connection_identity,
    normalize_publisher,
    normalize_reader,
    normalize_stream,
)


class StreamNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.srt_publisher = {
            "id": "srt-publisher",
            "remoteAddr": "192.0.2.10:9000",
            "mbpsReceiveRate": 4.0,
        }
        self.srt_reader = {
            "id": "srt-reader",
            "remoteAddr": "192.0.2.11:9000",
        }
        self.rtmp_reader = {
            "id": "rtmp-reader",
            "remoteAddr": "192.0.2.12:1935",
        }
        self.details = index_details(
            {
                "srtConn": [self.srt_publisher, self.srt_reader],
                "rtmpConn": [self.rtmp_reader],
            }
        )

    def test_normalizes_srt_publisher_with_unchanged_raw_details(self):
        publisher = normalize_publisher(
            {"type": "srtConn", "id": "srt-publisher"}, self.details
        )

        self.assertEqual(
            publisher,
            {
                "type": "srtConn",
                "id": "srt-publisher",
                "details": self.srt_publisher,
            },
        )

    def test_normalizes_another_protocol_and_missing_publisher(self):
        rtmp = normalize_publisher(
            {"type": "rtmpConn", "id": "rtmp-reader"}, self.details
        )
        missing = normalize_publisher({}, self.details)

        self.assertEqual(rtmp["details"], self.rtmp_reader)
        self.assertEqual(missing, {"type": None, "id": None, "details": {}})

    def test_connection_identity_preserves_id_remote_and_na_fallbacks(self):
        self.assertEqual(
            connection_identity({"id": "connection-id", "details": {}}),
            "connection-id",
        )
        self.assertEqual(
            connection_identity(
                {"id": None, "details": {"remoteAddr": "[2001:db8::1]:9000"}}
            ),
            "[2001:db8::1]:9000",
        )
        self.assertEqual(connection_identity({"id": None, "details": {}}), "n/a")

    def test_normalizes_two_reader_types_and_missing_details(self):
        readers = [
            normalize_reader(
                {"type": "srtConn", "id": "srt-reader"}, self.details
            ),
            normalize_reader(
                {"type": "rtmpConn", "id": "rtmp-reader"}, self.details
            ),
            normalize_reader(
                {"type": "unknownConn", "id": "missing"}, self.details
            ),
        ]

        self.assertEqual(readers[0]["details"], self.srt_reader)
        self.assertEqual(readers[1]["details"], self.rtmp_reader)
        self.assertEqual(
            readers[2],
            {"type": "unknownConn", "id": "missing", "details": {}},
        )

    def test_normalizes_complete_base_stream_and_media(self):
        tracks = [
            {
                "codec": "H264",
                "codecProps": {"width": 1920, "height": 1080, "profile": "High"},
            },
            {
                "codec": "Opus",
                "codecProps": {"sampleRate": 48000, "channelCount": 2},
            },
            {"codec": "FutureCodec", "codecProps": {}},
        ]
        path = {
            "name": "camera/main",
            "available": False,
            "online": False,
            "source": {"type": "srtConn", "id": "srt-publisher"},
            "readers": [
                {"type": "srtConn", "id": "srt-reader"},
                {"type": "rtmpConn", "id": "rtmp-reader"},
            ],
            "tracks2": tracks,
            "inboundBytes": 123,
            "outboundBytes": 456,
            "inboundFramesInError": 7,
        }
        forwards = [{"id": "dest-1", "type": "rtmp", "state": "forwarding", "conf": {"dest": "rtmp://secret"}}]

        stream = normalize_stream(path, self.details, "1.21.0", forwards)

        self.assertEqual(stream["name"], "camera/main")
        self.assertFalse(stream["available"])
        self.assertFalse(stream["online"])
        self.assertEqual(stream["mediamtxVersion"], "1.21.0")
        self.assertEqual(stream["tracks2"], tracks)
        self.assertEqual(stream["tracks"], ["H264", "Opus", "FutureCodec"])
        self.assertEqual(stream["media"]["video"][0]["width"], 1920)
        self.assertEqual(stream["media"]["audio"][0]["sampleRate"], 48000)
        self.assertEqual(
            stream["media"]["other"][0]["displayCodec"], "FutureCodec"
        )
        self.assertEqual(
            stream["forwardDestinations"],
            [{"id": "dest-1", "type": "rtmp", "state": "forwarding"}],
        )
        self.assertEqual(
            [reader["type"] for reader in stream["readers"]],
            ["srtConn", "rtmpConn"],
        )
        self.assertEqual(stream["inboundBytes"], 123)
        self.assertEqual(stream["outboundBytes"], 456)
        self.assertEqual(stream["inboundFramesInError"], 7)

    def test_empty_path_preserves_existing_fallback_shape(self):
        self.assertEqual(
            normalize_stream({}, {}, None, []),
            {
                "name": "",
                "mediamtxVersion": None,
                "source": {"type": None, "id": None, "details": {}},
                "tracks2": [],
                "tracks": [],
                "media": {"video": [], "audio": [], "other": []},
                "inboundBytes": 0,
                "outboundBytes": 0,
                "inboundFramesInError": 0,
                "forwardDestinations": [],
                "readers": [],
            },
        )


class StatusFieldTests(unittest.TestCase):
    def test_native_status_fields_are_kept_and_missing_ones_omitted(self):
        stream = normalize_stream({
            "name": "cam/1",
            "available": True,
            "online": True,
            "availableTime": "2026-10-29T10:00:00.5+01:00",
            "onlineTime": "2026-10-29T09:59:59+01:00",
            "confName": "~^cam/.*$",
            "source": None,
            "readers": [],
        }, {}, "1.21.3", [])
        self.assertEqual(stream["availableTime"], "2026-10-29T10:00:00.5+01:00")
        self.assertEqual(stream["onlineTime"], "2026-10-29T09:59:59+01:00")
        self.assertEqual(stream["confName"], "~^cam/.*$")

        # MediaMTX returns null times while a path is not available/online.
        idle = normalize_stream({
            "name": "idle", "availableTime": None, "onlineTime": None,
            "source": None, "readers": [],
        }, {}, "1.21.3", [])
        for field in ("availableTime", "onlineTime", "confName"):
            self.assertNotIn(field, idle)


if __name__ == "__main__":
    unittest.main()
