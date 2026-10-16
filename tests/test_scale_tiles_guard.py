import unittest

from src.heightmap.dgm1_dem import required_dgm1_tiles
from src.heightmap.swissalti3d_dem import required_swiss_tiles
from src.map.objects.selection import Selection


class TileGuardTest(unittest.TestCase):

    def test_dgm1_tiles_grow_when_scaled(self):
        normal = Selection.from_center(50.0, 10.0, 4000.0, 4000.0)
        scaled = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, scale_factor=4.0)
        self.assertGreater(len(required_dgm1_tiles(scaled)), len(required_dgm1_tiles(normal)))

    def test_swiss_tiles_grow_when_scaled(self):
        normal = Selection.from_center(46.95, 7.44, 4000.0, 4000.0)
        scaled = Selection.from_center(46.95, 7.44, 4000.0, 4000.0, scale_factor=4.0)
        self.assertGreater(len(required_swiss_tiles(scaled)), len(required_swiss_tiles(normal)))

    def test_unscaled_still_works(self):
        sel = Selection.from_center(50.0, 10.0, 4000.0, 4000.0)
        self.assertTrue(len(required_dgm1_tiles(sel)) > 0)


if __name__ == "__main__":
    unittest.main()
