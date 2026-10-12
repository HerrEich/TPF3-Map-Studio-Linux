import unittest

from src.map.objects.selection import Selection
from src.osm import overpass_client as oc


class TilePlanTest(unittest.TestCase):

    def test_small_selection_not_tiled(self):
        sel = Selection.from_center(50.0, 8.0, 10000, 10000)
        self.assertEqual(len(oc.plan_tiles(sel)), 1)

    def test_80km_gives_16_tiles(self):
        sel = Selection.from_center(50.0, 8.0, 80000, 80000, rotation_deg=30)
        self.assertEqual(len(oc.plan_tiles(sel)), 16)

    def test_narrow_band_tiles_only_long_side(self):
        sel = Selection.from_center(50.0, 8.0, 10752, 53760, rotation_deg=20)
        self.assertEqual(len(oc.plan_tiles(sel)), 3)

    def test_tiles_inside_selection_box(self):
        sel = Selection.from_center(50.0, 8.0, 60000, 60000, margin_m=2000)
        for tile in oc.plan_tiles(sel):
            self.assertGreater(tile.min_lat, sel.min_lat - 0.05)
            self.assertLess(tile.max_lat, sel.max_lat + 0.05)


if __name__ == "__main__":
    unittest.main()
