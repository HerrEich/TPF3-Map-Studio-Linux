import tempfile
import unittest
from pathlib import Path

from src.heightmap import dgm1_dem as d
from src.map.objects.selection import Selection


class Resp:
    status_code = 400
    headers = {}

    def json(self):
        return {"Attributes": {"Error": {"Detail": "kein Gebiet"}}}


class Session:
    def __init__(self):
        self.zones = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.zones.append(json["Attributes"]["Zone"])
        return Resp()


class ZoneFallbackTest(unittest.TestCase):
    def setUp(self):
        self.sel = Selection.from_center(48.0, 12.3, 2000.0, 2000.0)

    def test_default_zone_is_33_east_of_12(self):
        self.assertEqual({t[0] for t in d.required_dgm1_tiles(self.sel)}, {33})

    def test_zone_override(self):
        self.assertEqual({t[0] for t in d.required_dgm1_tiles(self.sel, zone=32)}, {32})

    def test_rejected_zone_is_retried_in_other_zone(self):
        session = Session()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(d.Dgm1TileRejected) as ctx:
                d.fetch_tiles_for_selection(
                    self.sel, Path(tmp), min_interval_s=0, session=session, sleep=lambda s: None
                )
        self.assertEqual(session.zones, [33, 32])
        self.assertIn("kein Gebiet", str(ctx.exception))

    def test_cache_zone_is_found(self):
        alt = d.required_dgm1_tiles(self.sel, zone=32)
        with tempfile.TemporaryDirectory() as tmp:
            zone, ie, inn = alt[0]
            (Path(tmp) / (d._slot_prefix(zone, ie, inn) + ".none")).write_bytes(b"x")
            tiles = d._tiles_in_cached_zone(self.sel, Path(tmp))
        self.assertEqual({t[0] for t in tiles}, {32})


if __name__ == "__main__":
    unittest.main()
