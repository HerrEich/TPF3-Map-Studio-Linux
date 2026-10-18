import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import src.osm.overpass_client as oc
from src.osm.tile_cache import TileCache


class Quiet(oc.OverpassClient):
    def __init__(self, tmp):
        super().__init__()
        self.tile_cache = TileCache(tmp)
        self.waits = []

    def _wait_retry(self, index, attempt, seconds):
        self.waits.append(seconds)


class PauseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_cooldown_werte(self):
        c = Quiet(self.tmp)
        self.assertEqual(c._cooldown_delay(1), 0.0)
        self.assertEqual(c._cooldown_delay(2), 0.0)
        self.assertEqual(c._cooldown_delay(3), 30.0)
        self.assertEqual(c._cooldown_delay(4), 60.0)
        self.assertEqual(c._cooldown_delay(99), 600.0)

    def test_kachel_wird_uebersprungen_nicht_alles_abgebrochen(self):
        c = Quiet(self.tmp)

        def fail(q):
            raise oc.OverpassUnavailable("x", retryable=True)

        c._fetch_json = fail
        with self.assertRaises(oc._TileGaveUp):
            c._load_tile(0, "q")
        # 11 Fehlrunden (unter GIVE_UP_STREAK 12): nur diese Kachel gibt auf
        self.assertEqual(c._streak, 11)

    def test_pause_waechst_und_erfolg_setzt_zurueck(self):
        c = Quiet(self.tmp)
        n = {"i": 0}

        def flaky(q):
            n["i"] += 1
            if n["i"] <= 5:
                raise oc.OverpassUnavailable("x", retryable=True)
            return {"elements": []}

        c._fetch_json = flaky
        c._load_tile(0, "q")
        self.assertEqual(c._streak, 0)
        # Runden 3..5: Wartezeit mindestens 30, 60, 120 s
        self.assertGreaterEqual(c.waits[2], 30.0)
        self.assertGreaterEqual(c.waits[3], 60.0)
        self.assertGreaterEqual(c.waits[4], 120.0)

    def test_dauerhaft_ausgefallen_beendet_alles(self):
        c = Quiet(self.tmp)

        def fail(q):
            raise oc.OverpassUnavailable("x", retryable=True)

        c._fetch_json = fail
        with self.assertRaises(oc._TileGaveUp):
            c._load_tile(0, "q")
        with self.assertRaises(oc.OverpassUnavailable) as ctx:
            c._load_tile(1, "q")
        self.assertIn("antworten seit längerer Zeit nicht", str(ctx.exception))

    def test_download_laedt_rest_und_meldet_fehlende(self):
        c = Quiet(self.tmp)
        tiles = [SimpleNamespace(n=i) for i in range(3)]
        c._cached_tile = lambda t, cfg, q: (None, None)
        loaded = []

        def load(index, query):
            loaded.append(index)
            if index == 1:
                raise oc._TileGaveUp()
            return {"elements": []}

        c._load_tile = load
        with mock.patch.object(oc, "plan_tiles", lambda s: tiles), \
                mock.patch.object(oc, "build_query", lambda t, cfg: "q%d" % t.n):
            with self.assertRaises(oc.OverpassUnavailable) as ctx:
                c._download_tiled(object(), None)
        self.assertEqual(sorted(loaded), [0, 1, 2])
        self.assertIn("1 von 3 Kacheln", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
