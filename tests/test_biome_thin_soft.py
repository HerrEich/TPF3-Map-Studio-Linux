import unittest

import numpy as np

from src.heightmap.biome_mask import thin_forest_by_height


def _ramp(rows=200, cols=300, top=400.0):
    """Hoehe steigt von links (0 m) nach rechts (top m)."""
    row = np.linspace(0.0, top, cols, dtype=np.float32)
    return np.tile(row, (rows, 1))


class SoftThinTest(unittest.TestCase):

    def test_zero_band_is_the_old_hard_line(self):
        index = np.array([[1, 1, 3, 1]], dtype=np.uint8)
        heights = np.array([[10, 400, 500, 340]], dtype=np.float32)
        result = thin_forest_by_height(index, heights, 0.0, 340.0, 0, band_m=0.0)
        self.assertEqual(result.tolist(), [[1, 0, 3, 0]])

    def test_below_band_untouched_above_limit_replaced(self):
        heights = _ramp()
        index = np.ones(heights.shape, dtype=np.uint8)
        result = thin_forest_by_height(
            index, heights, 0.0, 300.0, 0, band_m=60.0, pixel_m=4.0
        )
        self.assertTrue(np.all(result[heights < 240.0] == 1))
        self.assertTrue(np.all(result[heights >= 300.0] == 0))

    def test_share_of_trees_falls_inside_the_band(self):
        heights = _ramp()
        index = np.ones(heights.shape, dtype=np.uint8)
        result = thin_forest_by_height(
            index, heights, 0.0, 300.0, 0, band_m=60.0, pixel_m=4.0,
            patch_m=8.0,
        )
        fractions = []
        for low, high in ((240, 255), (255, 270), (270, 285), (285, 300)):
            zone = (heights >= low) & (heights < high)
            fractions.append(float(np.mean(result[zone] == 0)))
        self.assertLess(fractions[0], fractions[1] + 0.1)
        self.assertLess(fractions[0], fractions[-1])
        self.assertLess(fractions[0], 0.3)
        self.assertGreater(fractions[-1], 0.7)
        # Mitte des Bandes: etwa die Haelfte
        mid = (heights >= 266) & (heights < 274)
        self.assertAlmostEqual(float(np.mean(result[mid] == 0)), 0.5, delta=0.15)

    def test_other_biomes_are_never_touched(self):
        heights = _ramp()
        index = np.full(heights.shape, 3, dtype=np.uint8)
        result = thin_forest_by_height(
            index, heights, 0.0, 300.0, 0, band_m=60.0, pixel_m=4.0
        )
        self.assertTrue(np.all(result == 3))

    def test_deterministic_and_input_untouched(self):
        heights = _ramp()
        index = np.ones(heights.shape, dtype=np.uint8)
        a = thin_forest_by_height(index, heights, 0.0, 300.0, 0, band_m=60.0)
        b = thin_forest_by_height(index, heights, 0.0, 300.0, 0, band_m=60.0)
        np.testing.assert_array_equal(a, b)
        self.assertTrue(np.all(index == 1))

    def test_water_level_and_other_raster_size(self):
        heights = np.tile(np.linspace(500, 900, 40, dtype=np.float32), (20, 1))
        index = np.ones((80, 160), dtype=np.uint8)
        result = thin_forest_by_height(
            index, heights, 500.0, 300.0, 2, band_m=50.0, pixel_m=8.0
        )
        self.assertEqual(result.shape, (80, 160))
        self.assertTrue(np.all(result[:, :100] == 1))
        self.assertTrue(np.all(result[:, 120:] == 2))

    def test_band_larger_than_terrain_height_still_works(self):
        heights = _ramp(top=100.0)
        index = np.ones(heights.shape, dtype=np.uint8)
        result = thin_forest_by_height(
            index, heights, 0.0, 50.0, 0, band_m=500.0, pixel_m=4.0
        )
        self.assertEqual(result.shape, heights.shape)
        self.assertTrue(np.all(result[heights >= 50.0] == 0))


if __name__ == "__main__":
    unittest.main()
