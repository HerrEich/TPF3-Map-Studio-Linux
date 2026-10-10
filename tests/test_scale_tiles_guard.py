import unittest

from src.heightmap.dgm1_dem import Dgm1Error, required_dgm1_tiles
from src.heightmap.swissalti3d_dem import required_swiss_tiles
from src.map.objects.selection import Selection


class TileGuardTest(unittest.TestCase):

    def test_dgm1_tiles_rejected_when_scaled(self):
        sel = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, scale_factor=4.0)
        with self.assertRaises(Dgm1Error):
            required_dgm1_tiles(sel)

    def test_swiss_tiles_rejected_when_scaled(self):
        sel = Selection.from_center(46.95, 7.44, 4000.0, 4000.0, scale_factor=4.0)
        with self.assertRaises(Dgm1Error):
            required_swiss_tiles(sel)

    def test_unscaled_still_works(self):
        sel = Selection.from_center(50.0, 10.0, 4000.0, 4000.0)
        self.assertTrue(len(required_dgm1_tiles(sel)) > 0)


if __name__ == "__main__":
    unittest.main()
