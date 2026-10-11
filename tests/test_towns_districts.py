import unittest
from types import SimpleNamespace

from src.heightmap import towns_export as te
from src.osm.overpass_query_builder import PLACE_VALUES


def _sel():
    return SimpleNamespace(
        center=(50.0, 10.0), rotation_deg=0.0, width_m=20000.0,
        height_m=20000.0, scale_factor=1.0,
    )


def _node(lat, lon, **tags):
    return SimpleNamespace(lat=lat, lon=lon, tags=tags)


def _osm():
    return SimpleNamespace(nodes={
        1: _node(50.0, 10.0, place="city", name="Stadt"),
        2: _node(50.01, 10.01, place="suburb", name="Nordviertel"),
        3: _node(50.02, 10.02, place="quarter", name="Altstadt"),
        4: _node(50.03, 10.03, place="neighbourhood", name="Siedlung"),
    })


class DistrictsTest(unittest.TestCase):

    def test_kinds_known(self):
        for kind in ("suburb", "quarter", "neighbourhood"):
            self.assertIn(kind, te.PLACE_KINDS)
            self.assertIn(kind, te.FALLBACK_FACTOR)
            self.assertIn(kind, PLACE_VALUES)

    def test_districts_not_default(self):
        for kind in ("suburb", "quarter", "neighbourhood"):
            self.assertNotIn(kind, te.DEFAULT_KINDS)

    def test_default_ignores_districts(self):
        names = [p.name for p in te.collect_places(_osm(), _sel())]
        self.assertEqual(names, ["Stadt"])

    def test_districts_collected(self):
        places = te.collect_places(
            _osm(), _sel(),
            kinds=("city", "suburb", "quarter", "neighbourhood"),
        )
        self.assertEqual(len(places), 4)

    def test_fallback_size_factor(self):
        p = te.Place("x", "suburb", 0.0, 0.0)
        self.assertEqual(te.size_factor(p), 2.0)


if __name__ == "__main__":
    unittest.main()
