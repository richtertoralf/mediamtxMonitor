import json
import unittest
from pathlib import Path
from unittest import mock

from bin import mediamtx_collector
from bin.mediamtx_model import index_details, sanitize_details
from bin.redis_store import RedisStore
from tests.test_protocol_monitoring import ProtocolRedis


SECRET = "geheim-123"
JWT = "eyJhbGciOiJIUzI1NiJ9.e30.signatur"


class PagedClient:
    """Fake Control API with MediaMTX pagination (100 items per page)."""

    page_size = 100

    def __init__(self, path_count=101, session_count=101):
        self.requests = []
        self.paths = [
            {
                "name": f"cam-{index:03d}",
                "available": True,
                "online": True,
                "source": {"type": "rtmpConn", "id": f"pub-{index}"},
                "readers": (
                    [{"type": "webRTCSession", "id": f"rd-{reader}"}
                     for reader in range(session_count)]
                    if index == 0 else []
                ),
            }
            for index in range(path_count)
        ]
        self.lists = {
            "/v3/rtmp/conns/list": [
                {"id": f"pub-{index}", "remoteAddr": f"192.0.2.1:{index}",
                 "inboundBytes": 0, "state": "publish",
                 "query": f"user=a&pass={SECRET}"}
                for index in range(path_count)
            ],
            "/v3/webrtc/sessions/list": [
                {"id": f"rd-{index}", "remoteAddr": f"198.51.100.1:{index}",
                 "outboundBytes": 0, "state": "read",
                 "query": f"jwt={JWT}", "bearerToken": SECRET}
                for index in range(session_count)
            ],
            "/v3/paths/list": self.paths,
        }

    def build_url(self, endpoint):
        return f"http://localhost:9997{endpoint}"

    def get_json(self, endpoint, params=None):
        self.requests.append((endpoint, dict(params or {})))
        if endpoint == "/v3/info":
            return {"version": "1.21.3"}
        items = self.lists.get(endpoint, [])
        page = int((params or {}).get("page", 0))
        start = page * self.page_size
        page_count = (len(items) + self.page_size - 1) // self.page_size
        return {
            "itemCount": len(items),
            "pageCount": page_count,
            "items": items[start:start + self.page_size],
        }

    def count(self, endpoint):
        return sum(1 for name, _ in self.requests if name == endpoint)


class PaginationTests(unittest.TestCase):
    def collect(self, client):
        redis = ProtocolRedis()
        mediamtx_collector.r = redis
        mediamtx_collector.snapshot_store = RedisStore(redis)
        mediamtx_collector.mediamtx_client = client
        mediamtx_collector.reset_poll_cache()
        written = []
        with (
            mock.patch.object(Path, "write_text",
                              side_effect=lambda text, **_: written.append(text)),
            mock.patch.object(mediamtx_collector.time, "time", return_value=100.0),
        ):
            mediamtx_collector.collect_and_store()
        return redis, written

    def test_all_paths_and_sessions_beyond_first_page_are_collected(self):
        client = PagedClient(path_count=101, session_count=101)
        redis, _ = self.collect(client)
        snapshot = json.loads(redis.values[mediamtx_collector.REDIS_KEY])

        self.assertEqual(len(snapshot), 101)
        self.assertEqual(snapshot[-1]["name"], "cam-100")
        self.assertEqual(snapshot[-1]["source"]["details"]["id"], "pub-100")
        readers = snapshot[0]["readers"]
        self.assertEqual(len(readers), 101)
        self.assertTrue(all(reader["details"] for reader in readers))
        self.assertEqual(client.count("/v3/paths/list"), 2)
        self.assertEqual(client.count("/v3/webrtc/sessions/list"), 2)

    def test_preview_paths_are_counted_but_not_shown_as_streams(self):
        client = PagedClient(path_count=2, session_count=0)
        client.paths.append({
            "name": "__preview__/cam-000", "available": True, "online": True,
            "source": {"type": "rtspSession", "id": "t"}, "readers": [],
        })
        redis, _ = self.collect(client)
        snapshot = json.loads(redis.values[mediamtx_collector.REDIS_KEY])
        self.assertEqual([item["name"] for item in snapshot], ["cam-000", "cam-001"])
        count_key = f"{mediamtx_collector.REDIS_KEY}:preview_paths"
        self.assertEqual(json.loads(redis.values[count_key]), 1)

    def test_single_page_needs_no_additional_request(self):
        client = PagedClient(path_count=100, session_count=100)
        self.collect(client)
        for endpoint in (
            "/v3/paths/list", "/v3/rtmp/conns/list", "/v3/webrtc/sessions/list",
        ):
            self.assertEqual(client.count(endpoint), 1, endpoint)

    def test_paths_shifting_between_pages_are_not_duplicated(self):
        client = PagedClient(path_count=101, session_count=0)
        original = client.get_json

        def shifting(endpoint, params=None):
            data = original(endpoint, params)
            if endpoint == "/v3/paths/list" and (params or {}).get("page") == "1":
                data["items"] = [client.paths[99], *data["items"]]
            return data

        client.get_json = shifting
        redis, _ = self.collect(client)
        names = [item["name"] for item in json.loads(
            redis.values[mediamtx_collector.REDIS_KEY])]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 101)


class SensitiveDetailTests(unittest.TestCase):
    def test_query_and_credential_fields_are_removed(self):
        details = sanitize_details({
            "id": "a", "remoteAddr": "192.0.2.1:1", "userAgent": "Player",
            "query": f"jwt={JWT}", "password": SECRET, "accessToken": SECRET,
            "inboundRTPPacketsLost": 3,
        })
        self.assertEqual(details, {
            "id": "a", "remoteAddr": "192.0.2.1:1", "userAgent": "Player",
            "inboundRTPPacketsLost": 3,
        })

    def test_index_details_never_keeps_the_raw_object(self):
        raw = {"id": "a", "query": "pass=x"}
        indexed = index_details({"rtmpConn": [raw]})
        self.assertEqual(indexed, {"rtmpConn": {"a": {"id": "a"}}})
        self.assertIn("query", raw)

    def test_secrets_reach_neither_redis_nor_json_output(self):
        redis, written = PaginationTests().collect(PagedClient(3, 3))
        stored = "\n".join(str(value) for value in redis.values.values())
        for text in (stored, *written):
            self.assertNotIn(SECRET, text)
            self.assertNotIn(JWT, text)
            self.assertNotIn('"query"', text)
        self.assertTrue(written)


if __name__ == "__main__":
    unittest.main()
