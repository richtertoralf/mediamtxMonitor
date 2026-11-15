import json
import unittest
from pathlib import Path
from unittest import mock

from bin import mediamtx_collector
from bin.mediamtx_client import MediaMTXHTTPError, MediaMTXRequestError
from bin.redis_keys import (
    preview_paths_key,
    stream_snapshot_freshness_key,
    stream_snapshot_meta_key,
)
from bin.redis_store import RedisStore
from tests.test_srt_health import FakeRedis


SNAPSHOT_KEY = mediamtx_collector.REDIS_KEY
META_KEY = stream_snapshot_meta_key(SNAPSHOT_KEY)


class RecordingRedis(FakeRedis):
    """Fake Redis that records which keys each pipeline wrote together."""

    def __init__(self):
        super().__init__()
        self.transactions = []

    def pipeline(self):
        redis_client = self

        class Pipeline:
            def __init__(self):
                self.operations = []

            def set(self, key, value, ex=None):
                self.operations.append((key, value, ex))
                return self

            def execute(self):
                redis_client.transactions.append([key for key, _, _ in self.operations])
                for key, value, ex in self.operations:
                    redis_client.set(key, value, ex=ex)

        return Pipeline()


class ContractClient:
    def __init__(self):
        self.paths = ["cam", "master"]
        self.forwards = {"cam": [], "master": []}
        self.failing_forwards = set()
        self.failing_details = False

    def build_url(self, endpoint):
        return f"http://localhost:9997{endpoint}"

    def get_json(self, endpoint, params=None):
        if endpoint == "/v3/info":
            return {"version": "1.21.3", "started": "2026-11-15T08:00:00Z"}
        if endpoint == "/v3/paths/list":
            return {"pageCount": 1, "items": [{
                "name": name, "available": True, "online": True,
                "source": {"type": "srtConn", "id": f"{name}-pub"}, "readers": [],
            } for name in self.paths]}
        if endpoint == "/v3/srt/conns/list":
            if self.failing_details:
                raise MediaMTXRequestError("detail list unavailable")
            return {"items": []}
        if endpoint == "/v3/paths/forward-dests/list":
            name = (params or {}).get("path")
            if name in self.failing_forwards:
                raise MediaMTXHTTPError(self.build_url(endpoint), 500)
            return {"pageCount": 1, "items": self.forwards.get(name, [])}
        return {"items": []}


def srt_forward(forward_id, sent, state="forwarding"):
    return {
        "id": forward_id, "pos": 0, "type": "srt", "state": state,
        "created": "2026-11-15T08:00:00Z", "outboundBytes": sent,
        "typeSpecific": {"remoteAddr": "203.0.113.5:9000", "bytesSent": sent},
    }


class RedisContractTests(unittest.TestCase):
    def setUp(self):
        self.redis = RecordingRedis()
        self.client = ContractClient()
        mediamtx_collector.r = self.redis
        mediamtx_collector.snapshot_store = RedisStore(self.redis)
        mediamtx_collector.mediamtx_client = self.client
        mediamtx_collector.reset_poll_cache()

    def collect(self, timestamp):
        with (
            mock.patch.object(Path, "write_text"),
            mock.patch.object(mediamtx_collector.time, "time", return_value=timestamp),
        ):
            mediamtx_collector.collect_and_store()
        snapshot = json.loads(self.redis.values[SNAPSHOT_KEY])
        meta = json.loads(self.redis.values[META_KEY])
        return {entry["name"]: entry for entry in snapshot}, meta

    def test_meta_names_contract_node_generation_and_validity(self):
        _, meta = self.collect(100.0)
        self.assertEqual(meta["contract_version"], 1)
        self.assertEqual(meta["node_id"], "local")
        self.assertEqual(meta["sequence"], 1)
        self.assertEqual(meta["collected_at"], 100.0)
        self.assertEqual(meta["valid_until"], 103.0)
        self.assertEqual(
            meta["mediamtx"],
            {"version": "1.21.3", "started": "2026-11-15T08:00:00Z"},
        )
        self.assertEqual(set(meta["sections"]), {"paths", "details", "forwards"})
        self.assertEqual(meta["sections"]["paths"]["measured_at"], 100.0)

        _, later = self.collect(101.0)
        self.assertEqual(later["generation"], meta["generation"])
        self.assertEqual(later["sequence"], 2)

    def test_snapshot_and_meta_are_written_in_one_transaction(self):
        self.collect(100.0)
        self.assertIn(
            sorted([
                SNAPSHOT_KEY,
                stream_snapshot_freshness_key(SNAPSHOT_KEY),
                preview_paths_key(SNAPSHOT_KEY),
                META_KEY,
            ]),
            [sorted(keys) for keys in self.redis.transactions],
        )

    def test_cached_forwards_keep_their_own_measurement_time(self):
        self.collect(100.0)
        streams, meta = self.collect(102.0)
        self.assertEqual(meta["collected_at"], 102.0)
        self.assertEqual(meta["sections"]["forwards"]["measured_at"], 100.0)
        self.assertEqual(meta["sections"]["forwards"]["valid_until"], 115.0)
        self.assertEqual(
            streams["cam"]["forward_observation"],
            {"status": "ok", "measured_at": 100.0, "valid_until": 115.0},
        )

    def test_empty_successful_query_is_authoritative(self):
        streams, meta = self.collect(100.0)
        self.assertEqual(streams["cam"]["forwardDestinations"], [])
        self.assertEqual(streams["cam"]["forward_observation"]["status"], "ok")
        self.assertEqual(meta["sections"]["forwards"]["status"], "ok")

    def test_failed_query_is_distinguishable_from_an_empty_list(self):
        self.client.forwards["master"] = [srt_forward("f1", 1_000)]
        self.client.failing_forwards = {"master"}
        streams, meta = self.collect(100.0)
        self.assertEqual(streams["master"]["forwardDestinations"], [])
        self.assertEqual(
            streams["master"]["forward_observation"],
            {"status": "error", "measured_at": None, "valid_until": None},
        )
        self.assertEqual(streams["cam"]["forward_observation"]["status"], "ok")
        self.assertEqual(meta["sections"]["forwards"]["status"], "incomplete")
        # The rest of the snapshot stays fresh.
        self.assertEqual(meta["sections"]["paths"]["status"], "ok")

    def test_path_seen_between_refreshes_is_pending(self):
        self.collect(100.0)
        self.client.paths.append("late")
        streams, meta = self.collect(101.0)
        self.assertEqual(streams["late"]["forward_observation"]["status"], "pending")
        self.assertEqual(meta["sections"]["forwards"]["status"], "incomplete")

    def test_failed_detail_list_marks_details_incomplete(self):
        self.client.failing_details = True
        _, meta = self.collect(100.0)
        self.assertEqual(meta["sections"]["details"]["status"], "incomplete")
        self.assertEqual(meta["sections"]["details"]["failed"], ["/v3/srt/conns/list"])
        self.assertEqual(meta["sections"]["paths"]["status"], "ok")

    def test_transmission_evidence_reaches_the_snapshot(self):
        self.client.forwards["master"] = [srt_forward("f1", 0)]
        streams, _ = self.collect(100.0)
        first = streams["master"]["forwardDestinations"][0]["transmission"]
        self.assertEqual((first["status"], first["reason"]), ("unknown", "first_sample"))

        self.client.forwards["master"] = [srt_forward("f1", 2_000_000)]
        streams, _ = self.collect(105.0)
        sending = streams["master"]["forwardDestinations"][0]["transmission"]
        self.assertEqual(sending["status"], "sending")
        self.assertEqual((sending["since"], sending["since_observed"]), (105.0, True))

        self.client.forwards["master"] = [srt_forward("f1", 2_000_000, state="idle")]
        streams, _ = self.collect(110.0)
        ended = streams["master"]["forwardDestinations"][0]["transmission"]
        self.assertEqual((ended["status"], ended["reason"]), ("not_sending", "state_idle"))
        self.assertEqual(ended["ended_at"], 110.0)
        self.assertEqual(ended["last_growth_at"], 105.0)

    def test_failed_query_keeps_state_for_the_next_comparison(self):
        self.client.forwards["master"] = [srt_forward("f1", 0)]
        self.collect(100.0)
        self.client.failing_forwards = {"master"}
        self.collect(105.0)
        self.client.failing_forwards = set()
        self.client.forwards["master"] = [srt_forward("f1", 1_000)]
        streams, _ = self.collect(110.0)
        transmission = streams["master"]["forwardDestinations"][0]["transmission"]
        self.assertEqual(transmission["status"], "sending")

    def test_removed_forward_is_absent_from_an_authoritative_list(self):
        self.client.forwards["master"] = [srt_forward("f1", 0)]
        self.collect(100.0)
        self.client.forwards["master"] = []
        streams, _ = self.collect(105.0)
        self.assertEqual(streams["master"]["forwardDestinations"], [])
        self.assertEqual(streams["master"]["forward_observation"]["status"], "ok")
        self.assertEqual(mediamtx_collector.poll_cache.forward_transmissions, {})

    def test_new_generation_starts_without_evidence(self):
        self.client.forwards["master"] = [srt_forward("f1", 0)]
        _, before = self.collect(100.0)
        self.client.forwards["master"] = [srt_forward("f1", 1_000)]
        mediamtx_collector.reset_poll_cache()
        streams, after = self.collect(105.0)
        self.assertNotEqual(after["generation"], before["generation"])
        self.assertEqual(after["sequence"], 1)
        transmission = streams["master"]["forwardDestinations"][0]["transmission"]
        self.assertEqual(transmission["reason"], "first_sample")

    def test_failed_path_list_leaves_the_old_state_to_expire(self):
        self.collect(100.0)

        class Broken(ContractClient):
            def get_json(self, endpoint, params=None):
                if endpoint == "/v3/paths/list":
                    raise MediaMTXRequestError("paths unavailable")
                return super().get_json(endpoint, params)

        mediamtx_collector.mediamtx_client = Broken()
        with self.assertLogs(level="WARNING"):
            _, meta = self.collect(110.0)
        # Nothing new was written; the old meta is past its validity.
        self.assertEqual(meta["collected_at"], 100.0)
        self.assertLess(meta["valid_until"], 110.0)


if __name__ == "__main__":
    unittest.main()
