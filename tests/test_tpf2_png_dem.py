import math
import unittest
from types import SimpleNamespace

import numpy as np

from src.heightmap.tpf2_png_dem import Tpf2PngMosaic


def geo(rot_deg):
    t = math.radians(rot_deg)
    return SimpleNamespace(
        METERS_PER_DEGREE_LAT=111_320.0, longitude_scale=70_000.0,
        right_vector=(math.cos(t), math.sin(t)),
        up_vector=(-math.sin(t), math.cos(t)))


def grid(g, w_px, h_px, width, height):
    """Dieselbe Abtastung wie _sample_grid (scale 1, kein Oversampling)."""
    px, py = width / w_px, height / h_px
    x = -width / 2 + (np.arange(w_px) + 0.5) * px
    y = height / 2 - (np.arange(h_px) + 0.5) * py
    xl, yl = np.meshgrid(x, y)
    e = g.right_vector[0] * xl + g.up_vector[0] * yl
    n = g.right_vector[1] * xl + g.up_vector[1] * yl
    return (51.0 + n / g.METERS_PER_DEGREE_LAT,
            12.0 + e / g.longitude_scale)


class PngMosaicTest(unittest.TestCase):
    def _raw(self):
        rng = np.random.default_rng(1)
        return rng.integers(0, 65536, (30, 50)).astype(np.uint16)

    def test_identitaet_mit_und_ohne_drehung(self):
        raw = self._raw()
        for rot in (0, 33, 90, 200):
            g = geo(rot)
            m = Tpf2PngMosaic(raw, 0, 100, g, (51.0, 12.0), 200.0, 120.0)
            lat, lon = grid(g, 50, 30, 200.0, 120.0)
            out = m.sample_grid(lat, lon)
            self.assertTrue(np.allclose(out, raw / 65535 * 100, atol=0.02), rot)

    def test_ausserhalb_ist_nan(self):
        g = geo(0)
        m = Tpf2PngMosaic(self._raw(), 0, 100, g, (51.0, 12.0), 200.0, 120.0)
        out = m.sample_grid(np.array([52.0]), np.array([12.0]))
        self.assertTrue(np.isnan(out).all())

    def test_min_max_pruefung(self):
        with self.assertRaises(ValueError):
            Tpf2PngMosaic(self._raw(), 5, 5, geo(0), (51.0, 12.0), 200.0, 120.0)


if __name__ == "__main__":
    unittest.main()
