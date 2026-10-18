import tempfile
import threading
import time
import unittest
from collections import Counter
from unittest import mock
from src.osm import overpass_client as oc
from src.osm.tile_cache import TileCache

class Response:
    def __init__(self, code=200, headers=None, data=None):
        self.status_code = code
        self.headers = headers or {}
        self.data = {"elements": []} if data is None else data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise oc.requests.HTTPError(response=self)
    def json(self):
        return self.data

class AutoRetryTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.client = oc.OverpassClient()
        self.client.tile_cache = TileCache(directory.name)
        self.client.SERVERS = ["https://one.invalid/api"]

    def download(self, tiles):
        with mock.patch.object(oc, "plan_tiles", return_value=tiles), mock.patch.object(oc, "build_query", side_effect=lambda tile, config: tile):
            return self.client.download(object())

    def test_same_tile_retries_past_original_limit_then_caches(self):
        c = self.client
        c._sleep = lambda seconds: None
        c._post = mock.Mock(side_effect=[Response(500)] * 7 + [Response()])
        waits = []
        c.on_retry = lambda tile, attempt, seconds: waits.append((tile, attempt, seconds))
        c._load_tile(4, "bad")
        self.assertEqual(c._post.call_count, 8)
        self.assertTrue(all(call.args[1] == "bad" for call in c._post.call_args_list))
        self.assertEqual([next(s for t,a,s in waits if a == n) for n in range(1,8)], [10,30,60,90,180,240,480])
        self.assertIsNotNone(c.tile_cache.get("bad"))
        self.assertEqual(c._active, 0)

    def test_both_failing_workers_keep_their_tiles(self):
        c = self.client
        started = threading.Barrier(2)
        calls = []
        waiting = set()
        guard = threading.Lock()
        def post(server, query):
            with guard:
                calls.append(query)
            started.wait(2)
            return Response(503)
        def lane(lane, tile, state, attempt, seconds):
            if state == "waiting":
                with guard:
                    waiting.add(lane)
                    if len(waiting) == 2:
                        c.cancel()
        c._post = post
        c.on_lane = lane
        with self.assertRaises(oc.OverpassCancelled):
            self.download([str(n) for n in range(100)])
        self.assertEqual(Counter(calls), Counter({"0": 1, "1": 1}))
        self.assertEqual(waiting, {1,2})
        self.assertEqual(c._active, 0)

    def test_healthy_worker_progresses_while_other_waits_after_overload(self):
        c = self.client
        failed = threading.Event()
        sleeping = threading.Event()
        complete = threading.Event()
        calls = Counter()
        guard = threading.Lock()
        def post(server, query):
            with guard:
                calls[query] += 1
                n = calls[query]
            if query == "bad" and n == 1:
                failed.set()
                return Response(500)
            if query != "bad":
                self.assertTrue(sleeping.wait(2))
                if query == "good3":
                    complete.set()
            return Response()
        def sleep(seconds):
            self.assertEqual(c._allowed, 1)
            sleeping.set()
            self.assertTrue(complete.wait(2))
        c._post = post
        c._sleep = sleep
        self.download(["bad", "good1", "good2", "good3"])
        self.assertTrue(failed.is_set())
        self.assertEqual(calls, Counter({"bad":2,"good1":1,"good2":1,"good3":1}))

    def test_healthy_download_has_two_parallel_http_requests(self):
        c = self.client
        barrier = threading.Barrier(2)
        active = 0
        peak = 0
        guard = threading.Lock()
        lanes = set()
        def post(server, query):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
                lanes.add(c._lane_number())
            barrier.wait(2)
            with guard:
                active -= 1
            return Response()
        c._post = post
        self.download(["one", "two"])
        self.assertEqual(peak, 2)
        self.assertEqual(lanes, {1,2})

    def test_retry_counters_are_independent_and_reset_for_next_tile(self):
        c = self.client
        c._sleep = lambda seconds: None
        counts = Counter()
        waits = []
        def post(server, query):
            counts[query] += 1
            return Response(500 if counts[query] <= (2 if query == "a" else 1) else 200)
        c._post = post
        c.on_retry = lambda tile, attempt, seconds: waits.append((tile, attempt, seconds))
        c._load_tile(0, "a")
        c._load_tile(1, "b")
        self.assertIn((1,2,30), waits)
        self.assertIn((2,1,10), waits)
        self.assertFalse(any(tile == 2 and attempt > 1 for tile, attempt, seconds in waits))

    def test_retry_after_longer_than_cap_is_honoured(self):
        c = self.client
        c._post = mock.Mock(side_effect=[Response(429, {"Retry-After":"600"}), Response()])
        c._sleep = lambda seconds: None
        waits = []
        c.on_retry = lambda *args: waits.append(args)
        c._load_tile(0, "q")
        self.assertEqual(waits[0], (1,1,600))

    def test_retry_after_date_and_invalid_headers(self):
        with mock.patch.object(oc.time, "time", return_value=0):
            self.assertEqual(self.client._server_retry_after(Response(headers={"Retry-After":"Thu, 01 Jan 1970 00:05:00 GMT"})), 300)
        for value in ("NaN", "infinity", "-1", "invalid"):
            self.assertEqual(self.client._server_retry_after(Response(headers={"Retry-After":value})), 0)

    def test_permanent_error_stops_without_retry(self):
        c = self.client
        c._post = mock.Mock(return_value=Response(400))
        with self.assertRaises(oc.OverpassUnavailable) as ctx:
            c._load_tile(0, "q")
        self.assertFalse(ctx.exception.retryable)
        self.assertEqual(c._post.call_count, 1)
        self.assertIsNone(c.tile_cache.get("q"))

    def test_original_server_fallback_order_is_retained(self):
        c = self.client
        c.SERVERS = ["https://one.invalid/api", "https://two.invalid/api"]
        c._post = mock.Mock(side_effect=[Response(500), Response()])
        c._sleep = mock.Mock()
        c._load_tile(0, "q")
        self.assertEqual([call.args[0] for call in c._post.call_args_list], c.SERVERS)
        c._sleep.assert_not_called()

    def test_cancel_wait_stops_same_tile_and_does_not_cache(self):
        c = self.client
        c._post = mock.Mock(return_value=Response(503))
        c.on_retry = lambda *args: c.cancel()
        start = time.monotonic()
        with self.assertRaises(oc.OverpassCancelled):
            c._load_tile(0, "q")
        self.assertLess(time.monotonic()-start, 1)
        self.assertEqual(c._post.call_count, 1)
        self.assertIsNone(c.tile_cache.get("q"))
        self.assertEqual(c._active, 0)

    def test_cache_and_single_tile_are_reused(self):
        c = self.client
        c.tile_cache.put("good", {"elements":[]})
        c._post = mock.Mock(return_value=Response())
        self.download(["good", "new"])
        c._post.assert_called_once_with(c.SERVERS[0], "new")
        c._post.reset_mock()
        self.download(["new"])
        c._post.assert_not_called()

    def test_overpass_incomplete_remark_retries_same_tile(self):
        c = self.client
        c._sleep = lambda seconds: None
        c._post = mock.Mock(side_effect=[Response(data={"elements":[],"remark":"runtime error: Query timed out"}), Response()])
        c._load_tile(0, "q")
        self.assertEqual(c._post.call_count, 2)
        self.assertIsNotNone(c.tile_cache.get("q"))

    def test_cancel_restart_waits_for_unfinished_http_in_same_lane(self):
        c = self.client
        started = threading.Event()
        release = threading.Event()
        calls = []
        errors = []
        def actual_post(*args, **kwargs):
            calls.append(1)
            started.set()
            release.wait(2)
            return Response()
        def run():
            try:
                c._post(c.SERVERS[0], "q")
            except oc.OverpassCancelled:
                pass
            except Exception as exc:
                errors.append(exc)
        with mock.patch.object(oc.requests, "post", side_effect=actual_post):
            first = threading.Thread(target=run)
            first.start()
            self.assertTrue(started.wait(1))
            c.cancel()
            first.join(1)
            self.assertFalse(first.is_alive())
            c.reset_cancel()
            second = threading.Thread(target=run)
            second.start()
            time.sleep(.1)
            self.assertEqual(len(calls), 1)
            release.set()
            second.join(1)
            self.assertFalse(second.is_alive())
            self.assertEqual(len(calls), 2)
            self.assertFalse(errors)
