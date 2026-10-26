import unittest

import numpy as np

from src.heightmap.slope_overlay import (
    slope_class, slope_overlay_rgba, slope_percent, slope_shares,
)
from src.heightmap.water_level import render_preview
from src.i18n import translate_to


class SlopeOverlayTest(unittest.TestCase):
    def ramp(self, percent):
        x = np.arange(80, dtype=np.float32) * 4.0 * percent / 100.0
        return np.tile(x, (80, 1))

    def test_percent(self):
        p = slope_percent(self.ramp(30), 4.0)
        self.assertAlmostEqual(float(p[40, 40]), 30.0, places=2)

    def test_flat(self):
        self.assertEqual(float(slope_percent(np.zeros((5, 5)), 4.0).max()), 0.0)

    def test_classes(self):
        for pct, cls in ((2, 0), (6, 1), (15, 2), (30, 3)):
            c = slope_class(slope_percent(self.ramp(pct), 4.0))
            self.assertEqual(int(c[40, 40]), cls, pct)

    def test_rgba_flat_transparent(self):
        rgba = slope_overlay_rgba(np.zeros((6, 6)), 4.0)
        self.assertEqual(int(rgba[..., 3].max()), 0)
        steep = slope_overlay_rgba(self.ramp(30), 4.0)
        self.assertGreater(int(steep[40, 40, 3]), 0)

    def test_shares(self):
        s = slope_shares(self.ramp(30), 4.0)
        self.assertAlmostEqual(s["steep"], 100.0)
        self.assertAlmostEqual(s["max"], 30.0, places=1)

    def test_bad_input(self):
        self.assertEqual(slope_percent(np.zeros((0, 0)), 4.0).size, 0)
        self.assertEqual(float(slope_percent(self.ramp(30), 0).max()), 0.0)

    def test_preview_colors_steep(self):
        h = self.ramp(30) + 50.0
        a = np.array(render_preview(h, 0.0, 50.0, 130.0, pixel_size_m=4.0))
        b = np.array(render_preview(h, 0.0, 50.0, 130.0, pixel_size_m=4.0, show_slope=True))
        self.assertFalse(np.array_equal(a, b))

    def test_english(self):
        t = "Steigung in der Vorschau zeigen (gelb ab 4 %, orange ab 10 %, rot ab 24 %)"
        self.assertNotEqual(translate_to(t, "en"), t)


if __name__ == "__main__":
    unittest.main()
