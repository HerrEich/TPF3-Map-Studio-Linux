"""Tests fuer den OSM-Kachel-Cache und den parallelen Kachel-Download."""

import gzip
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from src.osm import overpass_client as oc
from src.osm.tile_cache import TileCache


class _Resp:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}


class _Parser:
    def parse(self, data):
        return types.SimpleNamespace(elements=data["elements"])


def _answer(tag):
    return {
        "osm3s": {"timestamp_osm_base": "2026-10-01T00:00:00Z"},
        "elements": [{"type": "node", "id": hash(tag) % 1000, "tag": tag}],
    }


class TileCacheTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.now = [1_000_000.0]
        self.cache = TileCache(self.dir, clock=lambda: self.now[0])

    def tearDown(self):
        self._tmp.cleanup()

    def test_key_depends_on_query(self):
        self.assertEqual(TileCache.key("a"), TileCache.key("a"))
        self.assertNotEqual(TileCache.key("a"), TileCache.key("b"))
        self.assertEqual(len(TileCache.key("a")), 64)

    def test_miss_then_hit(self):
        self.assertIsNone(self.cache.get("q"))
        self.assertTrue(self.cache.put("q", _answer("x")))
        self.assertEqual(self.cache.get("q"), _answer("x"))

    def test_expiry(self):
        import os

        self.cache.put("q", _answer("x"))
        path = self.cache.path_for("q")
        os.utime(path, (self.now[0], self.now[0]))
        self.now[0] += 29 * 24 * 3600
        self.assertIsNotNone(self.cache.get("q"))
        self.now[0] += 2 * 24 * 3600
        self.assertIsNone(self.cache.get("q"))

    def test_corrupt_file_is_discarded(self):
        self.cache.put("q", _answer("x"))
        path = self.cache.path_for("q")
        path.write_bytes(b"das ist kein gzip")
        self.assertIsNone(self.cache.get("q"))
        self.assertFalse(path.exists())

    def test_truncated_gzip_is_discarded(self):
        self.cache.put("q", _answer("x"))
        path = self.cache.path_for("q")
        raw = path.read_bytes()
        path.write_bytes(raw[: len(raw) // 2])
        self.assertIsNone(self.cache.get("q"))
        self.assertFalse(path.exists())

    def test_wrong_content_is_discarded(self):
        path = self.cache.path_for("q")
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wb") as handle:
            handle.write(b"[1, 2, 3]")
        self.assertIsNone(self.cache.get("q"))
        self.assertFalse(path.exists())

    def test_atomic_write_leaves_no_tmp(self):
        self.cache.put("q", _answer("x"))
        names = [p.name for p in self.dir.iterdir()]
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].endswith(".json.gz"))

    def test_failed_write_leaves_no_tmp(self):
        with mock.patch("src.osm.tile_cache.os.replace", side_effect=OSError("voll")):
            self.assertFalse(self.cache.put("q", _answer("x")))
        self.assertEqual(list(self.dir.iterdir()), [])


class ClientTileTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.client = oc.OverpassClient()
        self.client.parser = _Parser()
        self.client.tile_cache = TileCache(self._tmp.name)
        self.client.workers = 1
        # Keine echten Wartezeiten zwischen Wiederholungen.
        self.client._sleep = lambda seconds: None
        self.calls = []

        def fake_fetch(query):
            self.calls.append(query)
            if query in self.failing:
                raise RuntimeError("Server weg")
            return _answer(query)

        self.failing = set()
        self.client._fetch_json = fake_fetch

        self._patches = [
            mock.patch.object(oc, "plan_tiles", return_value=["a", "b", "c"]),
            mock.patch.object(
                oc, "build_query", side_effect=lambda tile, config=None: "Q" + tile
            ),
        ]
        for patcher in self._patches:
            patcher.start()

    def tearDown(self):
        for patcher in self._patches:
            patcher.stop()
        self._tmp.cleanup()

    def test_second_run_comes_from_cache(self):
        self.client.download(None)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.client.last_cache_hits, 0)

        self.calls.clear()
        osm = self.client.download(None)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.client.last_cache_hits, 3)
        self.assertEqual(len(osm.elements), 3)

    def test_use_cache_false_reloads(self):
        self.client.download(None)
        self.calls.clear()
        self.client.use_cache = False
        self.client.download(None)
        self.assertEqual(len(self.calls), 3)

    def test_failure_keeps_finished_tiles_and_resumes(self):
        self.failing = {"Qb"}
        with self.assertRaises(RuntimeError):
            self.client.download(None)

        self.assertIsNotNone(self.client.tile_cache.get("Qa"))
        self.assertIsNone(self.client.tile_cache.get("Qb"))

        self.failing = set()
        self.calls.clear()
        self.client.download(None)
        self.assertNotIn("Qa", self.calls)
        self.assertIn("Qb", self.calls)

    def test_parallel_download_gives_same_result(self):
        self.client.workers = 2
        osm = self.client.download(None)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(osm.elements), 3)

    def test_progress_counts_finished_tiles(self):
        seen = []
        self.client.on_progress = lambda done, total: seen.append((done, total))
        self.client.download(None)
        self.assertEqual(seen[-1], (3, 3))

    def test_overload_reduces_parallelism(self):
        self.client._allowed = 2
        self.client._note_overload(_Resp(429, {"Retry-After": "7"}))
        self.assertEqual(self.client._allowed, 1)
        self.assertEqual(self.client._tls.wait, 7.0)

    def test_other_status_changes_nothing(self):
        self.client._allowed = 2
        self.client._note_overload(_Resp(404))
        self.client._note_overload(_Resp(400))
        self.assertEqual(self.client._allowed, 2)

    def test_server_errors_and_timeouts_reduce_parallelism(self):
        for response in (_Resp(500), _Resp(502), _Resp(503), _Resp(504), None):
            self.client._allowed = 2
            self.client._note_overload(response)
            self.assertEqual(self.client._allowed, 1)

    def test_failing_tile_retries_with_backoff(self):
        waits = []
        self.client._sleep = waits.append
        self.failing = {"Qc"}
        with self.assertRaises(RuntimeError):
            self.client.download(None)
        self.assertEqual(waits, list(oc.BACKOFF_S[: oc.TILE_RETRIES]))
        self.assertEqual(self.calls.count("Qc"), oc.TILE_RETRIES + 1)


class ClientLogTests(unittest.TestCase):

    def test_status_code_is_logged(self):
        import io
        from contextlib import redirect_stdout

        import requests

        client = oc.OverpassClient()
        client.SERVERS = ["https://example.invalid/api"]

        class _Failing:
            status_code = 504
            headers = {}

            def raise_for_status(self):
                raise requests.HTTPError("504", response=self)

        buffer = io.StringIO()

        with mock.patch.object(client, "_post", return_value=_Failing()):
            with redirect_stdout(buffer):
                with self.assertRaises(RuntimeError):
                    client._fetch_json("q")

        self.assertIn("HTTP 504", buffer.getvalue())

    def test_remark_timeout_counts_as_failure_and_is_named(self):
        client = oc.OverpassClient()
        client.SERVERS = ["https://example.invalid/api"]

        class _Remark:
            status_code = 200
            headers = {}

            def raise_for_status(self):
                pass

            def json(self):
                return {"elements": [], "remark": "runtime error: Query timed out"}

        with mock.patch.object(client, "_post", return_value=_Remark()):
            with self.assertRaises(RuntimeError) as ctx:
                client._fetch_json("q")

        self.assertIn("example.invalid", str(ctx.exception))
        self.assertIn("timed out", str(ctx.exception))



if __name__ == "__main__":
    unittest.main()
