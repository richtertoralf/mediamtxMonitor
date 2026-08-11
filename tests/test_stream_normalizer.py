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
        self.assertIs(publisher["details"], self.srt_publisher)

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
        forwards = [{"target": "backup"}]

        stream = normalize_stream(path, self.details, "1.20.0", forwards)

        self.assertEqual(stream["name"], "camera/main")
        self.assertEqual(stream["mediamtxVersion"], "1.20.0")
        self.assertEqual(stream["tracks2"], tracks)
        self.assertEqual(stream["tracks"], ["H264", "Opus", "FutureCodec"])
        self.assertEqual(stream["media"]["video"][0]["width"], 1920)
        self.assertEqual(stream["media"]["audio"][0]["sampleRate"], 48000)
        self.assertEqual(
            stream["media"]["other"][0]["displayCodec"], "FutureCodec"
        )
        self.assertEqual(stream["forwardDestinations"], forwards)
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


if __name__ == "__main__":
    unittest.main()
