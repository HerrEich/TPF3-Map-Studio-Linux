import unittest

from src.heightmap.dgm1_dem import required_dgm1_tiles
from src.map.objects.selection import Selection


def _lat_span(selection):
    lats = [lat for lat, _lon in selection.corners_latlon()]
    return max(lats) - min(lats)


class ScaleBelowOneTest(unittest.TestCase):
    """Stauchfaktor unter 1: das reale Gebiet ist kleiner als die Spielkarte."""

    def test_height_scale_default_is_inverse_factor(self):
        sel = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, scale_factor=0.9)
        self.assertAlmostEqual(sel.height_scale, 1.0 / 0.9, places=6)
        self.assertTrue(sel.is_scaled)

    def test_half_factor_doubles_heights(self):
        sel = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, scale_factor=0.5)
        self.assertAlmostEqual(sel.height_scale, 2.0, places=6)

    def test_corners_shrink_with_factor(self):
        normal = Selection.from_center(50.0, 10.0, 4000.0, 4000.0)
        scaled = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, scale_factor=0.9)
        self.assertAlmostEqual(_lat_span(scaled) / _lat_span(normal), 0.9, places=6)

    def test_dgm1_tiles_not_more_than_unscaled(self):
        normal = Selection.from_center(50.0, 10.0, 4000.0, 4000.0)
        stretched = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, scale_factor=0.5)
        tiles = required_dgm1_tiles(stretched)
        self.assertGreater(len(tiles), 0)
        self.assertLessEqual(len(tiles), len(required_dgm1_tiles(normal)))


if __name__ == "__main__":
    unittest.main()
