import math
import unittest
from pathlib import Path

import numpy as np

from src.heightmap import heightmap_exporter as hx
from src.heightmap.dgm1_dem import Dgm1Error
from src.map.objects.selection import Selection
from src.tpf2.tpf2_geometry import TPF2Geometry


def _dist_m(a, b, lat0):
    dy = (a[0] - b[0]) * 111320.0
    dx = (a[1] - b[1]) * 111320.0 * math.cos(math.radians(lat0))
    return math.hypot(dx, dy)


class EastMosaic:
    # Liefert je Punkt den Ost-Abstand zur Kartenmitte in Metern.

    def __init__(self, lon0, lon_scale):
        self.lon0 = lon0
        self.lon_scale = lon_scale

    def sample_grid(self, lat, lon):
        return ((lon - self.lon0) * self.lon_scale).astype(np.float32)


class SelectionScaleTest(unittest.TestCase):

    def test_default_is_unscaled(self):
        sel = Selection.from_center(50.0, 10.0, 3584.0, 3584.0, 0.0, 0.0)
        self.assertEqual(sel.scale_factor, 1.0)
        self.assertEqual(sel.height_scale, 1.0)
        self.assertEqual(sel.real_width_m, 3584.0)
        self.assertFalse(sel.is_scaled)

    def test_real_extent_grows_with_factor(self):
        sel = Selection.from_center(50.0, 10.0, 3584.0, 3584.0, 0.0, 0.0, scale_factor=5.0)
        corners = sel.corners_latlon()
        width = _dist_m(corners[0], corners[1], 50.0)
        height = _dist_m(corners[1], corners[2], 50.0)
        self.assertAlmostEqual(width / (5 * 3584.0), 1.0, delta=0.01)
        self.assertAlmostEqual(height / (5 * 3584.0), 1.0, delta=0.01)
        self.assertEqual(sel.width_m, 3584.0)
        self.assertEqual(sel.real_width_m, 5 * 3584.0)
        self.assertTrue(sel.is_scaled)

    def test_bbox_covers_real_area(self):
        sel = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, 0.0, 0.0, scale_factor=10.0)
        span_m = (sel.max_lat - sel.min_lat) * 111320.0
        self.assertAlmostEqual(span_m / 40000.0, 1.0, delta=0.01)

    def test_height_scale_defaults_to_inverse(self):
        sel = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, 0.0, 0.0, scale_factor=4.0)
        self.assertAlmostEqual(sel.height_scale, 0.25)

    def test_explicit_height_scale_kept(self):
        sel = Selection.from_center(
            50.0, 10.0, 4000.0, 4000.0, 0.0, 0.0, scale_factor=4.0, height_scale=0.5
        )
        self.assertEqual(sel.height_scale, 0.5)

    def test_invalid_factor_rejected(self):
        with self.assertRaises(ValueError):
            Selection.from_center(50.0, 10.0, 4000.0, 4000.0, scale_factor=0.0)


class GeometryScaleTest(unittest.TestCase):

    def test_default_is_unchanged(self):
        a = TPF2Geometry(50.0, 10.0, 30.0)
        b = TPF2Geometry(50.0, 10.0, 30.0, 1.0)
        self.assertEqual(a.convert(50.01, 10.02), b.convert(50.01, 10.02))

    def test_convert_divides_by_scale(self):
        g1 = TPF2Geometry(50.0, 10.0, 0.0)
        g10 = TPF2Geometry(50.0, 10.0, 0.0, 10.0)
        x1, y1 = g1.convert(50.02, 10.03)
        x10, y10 = g10.convert(50.02, 10.03)
        self.assertAlmostEqual(x10, x1 / 10.0, places=6)
        self.assertAlmostEqual(y10, y1 / 10.0, places=6)

    def test_roundtrip_with_rotation_and_scale(self):
        g = TPF2Geometry(50.0, 10.0, 33.0, 7.0)
        lat, lon = g.inverse(*g.convert(50.05, 10.07))
        self.assertAlmostEqual(lat, 50.05, places=9)
        self.assertAlmostEqual(lon, 10.07, places=9)


class ExporterScaleTest(unittest.TestCase):

    def test_height_scale_helper(self):
        sel = Selection.from_center(50.0, 10.0, 400.0, 400.0, scale_factor=4.0)
        arr = np.array([[100.0, -20.0]], dtype=np.float32)
        out = hx._apply_height_scale(arr, sel)
        np.testing.assert_allclose(out, [[25.0, -5.0]])
        self.assertEqual(out.dtype, np.float32)
        same = hx._apply_height_scale(arr, Selection.from_center(50.0, 10.0, 400.0, 400.0))
        self.assertIs(same, arr)

    def test_oversample_levels(self):
        def sel(k):
            return Selection.from_center(50.0, 10.0, 400.0, 400.0, scale_factor=k)

        self.assertEqual(hx.oversample_for_selection(sel(1.0)), 1)
        self.assertEqual(hx.oversample_for_selection(sel(5.0)), 1)
        self.assertEqual(hx.oversample_for_selection(sel(10.0)), 2)
        self.assertEqual(hx.oversample_for_selection(sel(100.0)), hx.MAX_OVERSAMPLE)

    def _grid(self, k, oversample=1):
        sel = Selection.from_center(50.0, 10.0, 400.0, 200.0, 0.0, 0.0, scale_factor=k)
        g = TPF2Geometry(50.0, 10.0)
        mosaic = EastMosaic(10.0, g.longitude_scale)
        w_px, h_px = hx.pixel_size_for_selection(sel)
        return hx._sample_grid(sel, mosaic, w_px, h_px, oversample=oversample), w_px

    def test_unscaled_grid_unchanged(self):
        out, w_px = self._grid(1.0)
        pitch = 400.0 / w_px
        self.assertAlmostEqual(float(out[0, 0]), -200.0 + 0.5 * pitch, delta=0.05)
        self.assertAlmostEqual(float(out[0, -1]), 200.0 - 0.5 * pitch, delta=0.05)

    def test_scaled_grid_samples_real_extent(self):
        out, w_px = self._grid(4.0)
        pitch = 400.0 / w_px
        self.assertAlmostEqual(float(out[0, 0]), 4 * (-200.0 + 0.5 * pitch), delta=0.1)
        self.assertAlmostEqual(float(out[0, -1]), 4 * (200.0 - 0.5 * pitch), delta=0.1)
        np.testing.assert_allclose(out[0], out[-1], atol=0.05)

    def test_oversampling_keeps_linear_field(self):
        flat, _ = self._grid(4.0, oversample=1)
        fine, _ = self._grid(4.0, oversample=3)
        np.testing.assert_allclose(flat, fine, atol=0.1)

    def test_other_sources_rejected_when_scaled(self):
        sel = Selection.from_center(50.0, 10.0, 400.0, 400.0, scale_factor=2.0)
        with self.assertRaises(Dgm1Error):
            hx.build_heightmap_array_ex(sel, Path("."), source=hx.SOURCE_DGM1_DE)


if __name__ == "__main__":
    unittest.main()
