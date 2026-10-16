import unittest

from src.map.objects.selection import Selection
from src.osm import overpass_client as oc
from src.osm.overpass_query_builder import area_filter


class TilePlanTest(unittest.TestCase):

    def test_small_selection_not_tiled(self):
        sel = Selection.from_center(50.0, 8.0, 10000, 10000)
        self.assertEqual(len(oc.plan_tiles(sel)), 1)

    def test_large_selection_uses_world_grid(self):
        sel = Selection.from_center(50.0, 8.0, 80000, 80000, rotation_deg=30)
        tiles = oc.plan_tiles(sel)
        self.assertGreater(len(tiles), 60)
        self.assertLess(len(tiles), 110)
        for tile in tiles:
            self.assertFalse(tile.is_rotated)
            self.assertAlmostEqual(tile.max_lat - tile.min_lat, 0.1, places=5)

    def test_narrow_band_has_few_tiles(self):
        sel = Selection.from_center(50.0, 8.0, 10752, 53760, rotation_deg=20)
        self.assertTrue(4 <= len(oc.plan_tiles(sel)) <= 16)

    def test_tiles_cover_the_selection(self):
        sel = Selection.from_center(50.0, 8.0, 60000, 60000, rotation_deg=17)
        tiles = oc.plan_tiles(sel)
        for lat, lon in sel.corners_latlon():
            self.assertTrue(any(
                t.min_lat <= lat <= t.max_lat and t.min_lon <= lon <= t.max_lon
                for t in tiles
            ))

    def test_scale_and_rotation_reuse_tiles(self):
        def filters(sel):
            return {area_filter(t) for t in oc.plan_tiles(sel)}

        a = Selection.from_center(50.0, 8.0, 40000, 40000)
        b = Selection.from_center(50.0, 8.0, 40000, 40000, scale_factor=1.5)
        c = Selection.from_center(50.0, 8.0, 40000, 40000, rotation_deg=25)
        self.assertTrue(filters(a) <= filters(b))
        self.assertGreater(len(filters(a) & filters(c)), 0.6 * len(filters(a)))

    def test_same_selection_same_tiles(self):
        sel = Selection.from_center(50.0, 8.0, 60000, 60000, rotation_deg=17)
        one = [area_filter(t) for t in oc.plan_tiles(sel)]
        two = [area_filter(t) for t in oc.plan_tiles(sel)]
        self.assertEqual(one, two)


if __name__ == "__main__":
    unittest.main()
