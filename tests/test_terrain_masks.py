import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.heightmap.terrain_masks import mask_shares, suggest_masks, write_masks
from src.i18n import translate_to


def _map(n=160):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    # Berg in der Mitte rechts, Becken links unten, Ebene bei 100 m
    h = np.full((n, n), 100.0, dtype=np.float32)
    h += 300.0 * np.exp(-(((x - 0.75 * n) ** 2 + (y - 0.4 * n) ** 2) / (0.12 * n) ** 2))
    h -= 12.0 * np.exp(-(((x - 0.25 * n) ** 2 + (y - 0.75 * n) ** 2) / (0.1 * n) ** 2))
    h[:6, :] = 0.0  # tiefer Streifen (Meer) am Rand
    return h


class TerrainMasksTest(unittest.TestCase):
    def test_shapes_and_mountain_share(self):
        h = _map()
        m = suggest_masks(h, 100.0)
        for k in ("mountains", "lakes", "swamps"):
            self.assertEqual(m[k].shape, h.shape)
            self.assertEqual(m[k].dtype, bool)
        self.assertAlmostEqual(m["mountains"].mean(), 0.35, delta=0.03)

    def test_mountain_is_at_peak(self):
        h = _map()
        m = suggest_masks(h, 100.0)
        n = h.shape[0]
        self.assertTrue(m["mountains"][int(0.4 * n), int(0.75 * n)])
        self.assertFalse(m["mountains"][int(0.9 * n), int(0.1 * n)])

    def test_lakes_swamps_disjoint(self):
        m = suggest_masks(_map(), 100.0)
        self.assertFalse((m["lakes"] & m["swamps"]).any())

    def test_basin_becomes_lake(self):
        h = _map()
        m = suggest_masks(h, 100.0)
        n = h.shape[0]
        self.assertTrue(m["lakes"][int(0.75 * n), int(0.25 * n)])

    def test_sea_not_lake(self):
        m = suggest_masks(_map(), 100.0)
        self.assertFalse(m["lakes"][:4, :].any())

    def test_no_water_depth_no_lakes(self):
        h = _map() + 50.0
        m = suggest_masks(h, h.min())
        self.assertFalse(m["lakes"].any())
        self.assertFalse(m["swamps"].any())

    def test_bad_input(self):
        m = suggest_masks(np.zeros((3, 3)), 0.0)
        self.assertFalse(m["mountains"].any())

    def test_flat_map(self):
        m = suggest_masks(np.full((64, 64), 50.0), 10.0)
        self.assertFalse(m["mountains"].any())

    def test_large_map_is_downscaled(self):
        h = np.tile(np.linspace(0, 500, 2500, dtype=np.float32), (2500, 1))
        m = suggest_masks(h, 50.0)
        self.assertEqual(m["mountains"].shape, (2500, 2500))
        self.assertAlmostEqual(m["mountains"].mean(), 0.35, delta=0.03)

    def test_write(self):
        m = suggest_masks(_map(), 100.0)
        with tempfile.TemporaryDirectory() as d:
            paths = write_masks(m, Path(d) / "test.png")
            self.assertEqual(
                [p.name for p in paths],
                ["test_mountains.png", "test_lakes.png", "test_swamps.png"],
            )
            from PIL import Image
            a = np.array(Image.open(paths[0]))
            self.assertEqual(set(np.unique(a)) <= {0, 255}, True)
            self.assertEqual(a.shape, m["mountains"].shape)

    def test_shares(self):
        s = mask_shares(suggest_masks(_map(), 100.0))
        self.assertEqual(set(s), {"mountains", "lakes", "swamps"})

    def test_english(self):
        t = "Berg-, See- und Sumpf-Masken..."
        self.assertNotEqual(translate_to(t, "en"), t)


if __name__ == "__main__":
    unittest.main()
