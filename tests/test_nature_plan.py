import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.heightmap.nature_plan import (
    KIND_HEDGE, KIND_ORCHARD, KIND_VINEYARD, KIND_WALL,
    classify, collect_features, estimate_rows, summarize, write_csv, write_json,
)
from src.osm.objects.node import Node
from src.osm.objects.osm_data import OSMData
from src.osm.objects.way import Way
from src.osm.overpass_query_builder import OverpassQueryConfig, build_query

LAT, LON = 50.0, 10.0
DLAT = 1 / 111_320.0
DLON = 1 / (111_320.0 * 0.6427876)  # cos(50 Grad)


def _add(osm, way_id, tags, metres, closed=False):
    ids = []
    for i, (east, north) in enumerate(metres):
        nid = way_id * 100 + i
        osm.nodes[nid] = Node(nid, LAT + north * DLAT, LON + east * DLON)
        ids.append(nid)
    if closed:
        ids.append(ids[0])
    osm.ways[way_id] = Way(way_id, ids, tags)


class NaturePlanTest(unittest.TestCase):
    def setUp(self):
        self.osm = OSMData()
        # Weinberg 100 m (Ost) x 50 m (Nord) bei (200, 100)
        _add(self.osm, 1, {"landuse": "vineyard"},
             [(150, 75), (250, 75), (250, 125), (150, 125)], closed=True)
        _add(self.osm, 2, {"landuse": "orchard"},
             [(-50, -50), (-20, -50), (-20, -20), (-50, -20)], closed=True)
        _add(self.osm, 3, {"barrier": "wall"}, [(0, 0), (30, 0), (30, 40)])
        _add(self.osm, 4, {"barrier": "hedge"}, [(0, 10), (20, 10)])
        _add(self.osm, 5, {"landuse": "forest"}, [(0, 0), (9, 0), (9, 9)], closed=True)
        _add(self.osm, 6, {"landuse": "vineyard"},  # weit ausserhalb
             [(9000, 0), (9100, 0), (9100, 50)], closed=True)
        self.sel = SimpleNamespace(center=(LAT, LON), width_m=1000, height_m=1000,
                                   rotation_deg=0.0, scale_factor=1.0)

    def test_classify(self):
        self.assertEqual(classify({"landuse": "vineyard"}), KIND_VINEYARD)
        self.assertEqual(classify({"landuse": "orchard"}), KIND_ORCHARD)
        self.assertEqual(classify({"barrier": "retaining_wall"}), KIND_WALL)
        self.assertEqual(classify({"barrier": "hedge"}), KIND_HEDGE)
        self.assertIsNone(classify({"landuse": "forest"}))

    def test_collect(self):
        f = collect_features(self.osm, self.sel)
        self.assertEqual(sorted(x.osm_id for x in f), [1, 2, 3, 4])

    def test_vineyard_values(self):
        v = [x for x in collect_features(self.osm, self.sel) if x.kind == KIND_VINEYARD][0]
        self.assertAlmostEqual(v.area_m2, 5000, delta=60)
        self.assertAlmostEqual(v.x, 200, delta=2)
        self.assertAlmostEqual(v.y, 100, delta=2)
        # laengste Kante zeigt nach Osten -> Reihen in Ost-West-Richtung
        self.assertAlmostEqual(v.row_direction_deg, 90, delta=2)
        # Breite quer dazu 50 m, Abstand 2 m -> etwa 25 Reihen
        self.assertAlmostEqual(v.rows, 25, delta=1)

    def test_wall_length(self):
        w = [x for x in collect_features(self.osm, self.sel) if x.kind == KIND_WALL][0]
        self.assertAlmostEqual(w.length_m, 70, delta=1)

    def test_kinds_and_minimum(self):
        f = collect_features(self.osm, self.sel, kinds=(KIND_WALL,))
        self.assertEqual([x.kind for x in f], [KIND_WALL])
        f = collect_features(self.osm, self.sel, min_area_m2=2000)
        self.assertEqual([x.osm_id for x in f if x.kind in (KIND_VINEYARD, KIND_ORCHARD)], [1])

    def test_scale_factor(self):
        self.sel.scale_factor = 2.0
        v = [x for x in collect_features(self.osm, self.sel) if x.kind == KIND_VINEYARD][0]
        self.assertAlmostEqual(v.x, 100, delta=2)

    def test_default_min_area_constant(self):
        import re
        from pathlib import Path
        src = Path("src/gui/heightmap_dialog.py").read_text(encoding="utf-8")
        self.assertRegex(src, r"DEFAULT_NATURE_MIN_AREA_M2 = \d+")
        self.assertIn("min_area_m2=float(min_area)", src)

    def test_summary(self):
        s = summarize(collect_features(self.osm, self.sel))
        self.assertEqual(s["vineyard"]["count"], 1)
        self.assertAlmostEqual(s["vineyard"]["area_ha"], 0.5, delta=0.01)
        self.assertEqual(s["wall"]["count"], 1)

    def test_write_files(self):
        f = collect_features(self.osm, self.sel)
        with tempfile.TemporaryDirectory() as d:
            write_csv(f, Path(d) / "a.csv")
            write_json(f, Path(d) / "a.json")
            rows = list(csv.reader((Path(d) / "a.csv").open(encoding="utf-8-sig"), delimiter=";"))
            self.assertEqual(len(rows), 1 + len(f))
            data = json.loads((Path(d) / "a.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data["features"]), len(f))
            self.assertEqual(data["summary"]["wall"]["count"], 1)

    def test_estimate_rows_edge(self):
        self.assertEqual(estimate_rows([(0, 0), (1, 0)], 0, 2.0), 0)
        self.assertEqual(estimate_rows([(0, 0), (10, 0), (10, 10)], 0, 0), 0)

    def test_query_nature(self):
        sel = SimpleNamespace(
            is_rotated=False, min_lat=LAT - 0.01, min_lon=LON - 0.01,
            max_lat=LAT + 0.01, max_lon=LON + 0.01,
        )
        q = build_query(sel, OverpassQueryConfig(nature_details=True))
        self.assertIn("vineyard", q)  # Standard laedt Weinberge/Obstwiesen mit
        self.assertIn("retaining_wall", q)
        off = build_query(sel, OverpassQueryConfig(nature_details=False))
        self.assertNotIn("retaining_wall", off)


if __name__ == "__main__":
    unittest.main()
