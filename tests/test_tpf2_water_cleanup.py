import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from src.heightmap.tpf2_heightmap_import import raw_to_meters
from src.heightmap.tpf2_water_cleanup import (
    clean_water,
    remove_puddles,
    save_heightmap,
)

LOW, HIGH, WATER = 0.0, 100.0, 50.0


def _raw(meters: np.ndarray) -> np.ndarray:
    return np.rint(meters / (HIGH - LOW) * 65535).astype(np.uint16)


def _m(raw: np.ndarray) -> np.ndarray:
    return raw_to_meters(raw, LOW, HIGH)


class RemovePuddlesTest(unittest.TestCase):
    def test_kleine_flecken_weg_grosse_bleiben(self):
        w = np.zeros((40, 40), dtype=bool)
        w[2:4, 2:4] = True        # 4 Pixel
        w[10:30, 10:30] = True    # 400 Pixel
        out, n, px = remove_puddles(w, 50)
        self.assertEqual(n, 1)
        self.assertEqual(px, 4)
        self.assertFalse(out[2:4, 2:4].any())
        self.assertTrue(out[10:30, 10:30].all())

    def test_ohne_wasser(self):
        out, n, px = remove_puddles(np.zeros((5, 5), dtype=bool), 50)
        self.assertEqual((n, px), (0, 0))
        self.assertFalse(out.any())


class CleanWaterTest(unittest.TestCase):
    def _flussaue(self):
        """See (40 m) mitten in flacher Aue knapp ueber Wasser (50,3 m),
        dazu eine kleine Pfuetze (49,8 m) und ein Huegel (80 m)."""
        m = np.full((60, 60), 50.3, dtype=np.float32)
        m[20:40, 20:40] = 40.0            # See, 400 px
        m[5:7, 5:7] = 49.8                # Pfuetze, 4 px
        m[50:58, 50:58] = 80.0            # Huegel
        return _raw(m)

    def test_pfuetze_weg_see_bleibt(self):
        res = clean_water(self._flussaue(), LOW, HIGH, WATER, min_area_px=50)
        m = _m(res.raw)
        self.assertEqual(res.puddles_removed, 1)
        self.assertTrue((m[5:7, 5:7] > WATER).all())
        self.assertTrue((m[20:40, 20:40] < WATER).all())

    def test_aue_angehoben_mit_abstand(self):
        res = clean_water(self._flussaue(), LOW, HIGH, WATER,
                          margin_m=1.5, min_area_px=50, ramp_px=3)
        m = _m(res.raw)
        # weit weg vom See: volle 1,5 m Abstand
        self.assertAlmostEqual(float(m[0, 59]), WATER + 1.5, delta=0.01)
        # direkt am Ufer: ueber Wasser, aber weniger als voller Abstand
        self.assertGreater(float(m[19, 30]), WATER)
        self.assertLess(float(m[19, 30]), WATER + 1.5)

    def test_huegel_und_seegrund_unveraendert(self):
        raw = self._flussaue()
        res = clean_water(raw, LOW, HIGH, WATER, depth_m=2.0, min_area_px=50)
        self.assertTrue((res.raw[50:58, 50:58] == raw[50:58, 50:58]).all())
        self.assertTrue((res.raw[25:35, 25:35] == raw[25:35, 25:35]).all())

    def test_flaches_wasser_wird_vertieft(self):
        m = np.full((40, 40), 60.0, dtype=np.float32)
        m[10:30, 10:30] = 49.9            # nur 0,1 m tief
        res = clean_water(_raw(m), LOW, HIGH, WATER, depth_m=2.0,
                          min_area_px=10, ramp_px=3)
        out = _m(res.raw)
        self.assertAlmostEqual(float(out[20, 20]), WATER - 2.0, delta=0.01)
        self.assertLess(float(out[10, 20]), WATER)
        self.assertGreater(float(out[10, 20]), WATER - 2.0)
        self.assertGreater(res.lowered_px, 0)

    def test_wasserflaeche_bleibt_gleich_ohne_pfuetzen(self):
        raw = self._flussaue()
        res = clean_water(raw, LOW, HIGH, WATER, min_area_px=1)
        before = int((_m(raw) < WATER).sum())
        after = int((_m(res.raw) < WATER).sum())
        self.assertEqual(before, after)
        self.assertEqual(res.water_px, after)

    def test_falsche_wasserhoehe(self):
        with self.assertRaises(ValueError):
            clean_water(self._flussaue(), LOW, HIGH, 150.0)


class FillToRimTest(unittest.TestCase):
    def test_mulde_im_huegel_wird_aufgefuellt(self):
        m = np.full((40, 40), 80.0, dtype=np.float32)
        m[20:23, 20:23] = 49.8              # kleine Mulde unter Wasser
        res = clean_water(_raw(m), LOW, HIGH, WATER, min_area_px=50)
        out = _m(res.raw)
        self.assertEqual(res.puddles_removed, 1)
        self.assertTrue(np.allclose(out[20:23, 20:23], 80.0, atol=0.01))

    def test_zwischen_tiefstem_und_hoechstem_rand(self):
        m = np.full((30, 30), 90.0, dtype=np.float32)
        m[10:20, 9] = 60.0                  # niedrige Seite
        m[10:12, 10:12] = 49.0
        res = clean_water(_raw(m), LOW, HIGH, WATER, min_area_px=50)
        out = _m(res.raw)[10:12, 10:12]
        self.assertTrue((out > 60.0).all())
        self.assertTrue((out < 90.0).all())

    def test_am_hang_ohne_stufe(self):
        y, x = np.mgrid[0:40, 0:40].astype(np.float32)
        m = 60.0 + 1.0 * y                  # gleichmaessiger Hang
        m[18:24, 18:24] = 49.0              # Mulde unter Wasser
        res = clean_water(_raw(m), LOW, HIGH, WATER, min_area_px=50)
        out = _m(res.raw)
        # aufgefuellte Stelle folgt dem Hang (Abweichung < 0,5 m)
        hang = 60.0 + y[18:24, 18:24]
        self.assertLess(float(np.abs(out[18:24, 18:24] - hang).max()), 0.5)

    def test_grosser_see_bleibt(self):
        m = np.full((60, 60), 80.0, dtype=np.float32)
        m[10:50, 10:50] = 40.0
        res = clean_water(_raw(m), LOW, HIGH, WATER, min_area_px=50)
        self.assertTrue((_m(res.raw)[15:45, 15:45] < WATER).all())


class SaveTest(unittest.TestCase):
    def test_16bit(self):
        raw = np.array([[0, 65535], [1234, 40000]], dtype=np.uint16)
        with tempfile.TemporaryDirectory() as d:
            p = save_heightmap(Path(d) / "hm.png", raw)
            with Image.open(p) as im:
                self.assertEqual(im.mode, "I;16")
                self.assertEqual(np.array(im).tolist(), raw.tolist())


if __name__ == "__main__":
    unittest.main()
