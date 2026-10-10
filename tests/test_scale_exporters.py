import unittest
from types import SimpleNamespace

from src.heightmap.station_markers import station_marker_data
from src.map.objects.selection import Selection
from src.tpf2.tpf2_exporter import TPF2Exporter


def _data():
    road = SimpleNamespace(
        id=1,
        geometry=[(50.000, 10.000), (50.010, 10.020)],
        properties={},
    )
    return SimpleNamespace(roads=[road], railways=[])


class ExporterScaleTest(unittest.TestCase):

    def test_default_unchanged(self):
        a = TPF2Exporter(50.0, 10.0).export(_data())
        b = TPF2Exporter(50.0, 10.0, 0.0, 1.0).export(_data())
        self.assertEqual(a["nodes"], b["nodes"])

    def test_positions_divided_by_scale(self):
        a = TPF2Exporter(50.0, 10.0).export(_data())["nodes"]
        b = TPF2Exporter(50.0, 10.0, 0.0, 10.0).export(_data())["nodes"]
        self.assertEqual(set(a), set(b))
        for key in a:
            for i in (0, 1):
                self.assertAlmostEqual(
                    b[key]["pos"][i], a[key]["pos"][i] / 10.0, places=6
                )

    def test_from_selection_uses_scale(self):
        sel = Selection.from_center(
            50.0, 10.0, 4000.0, 4000.0, 0.0, 0.0, scale_factor=8.0
        )
        exporter = TPF2Exporter.from_selection(sel)
        self.assertEqual(exporter.geometry.scale, 8.0)

    def test_from_selection_default_scale(self):
        sel = Selection.from_center(50.0, 10.0, 4000.0, 4000.0, 0.0, 0.0)
        self.assertEqual(TPF2Exporter.from_selection(sel).geometry.scale, 1.0)


class StationMarkerScaleTest(unittest.TestCase):

    def _data(self, scale=None):
        info = {"center_lat": 50.0, "center_lon": 10.0, "rotation_deg": 0.0}
        if scale is not None:
            info["scale_factor"] = scale
        return {
            "map": info,
            "stations": [{"id": 1, "name": "A", "x": 0.0, "y": 100.0}],
        }

    def test_without_scale_unchanged(self):
        lat = station_marker_data(self._data())[0]["lat"]
        self.assertAlmostEqual(lat, 50.0 + 100.0 / 111320.0, places=6)

    def test_marker_uses_real_distance(self):
        lat = station_marker_data(self._data(10.0))[0]["lat"]
        self.assertAlmostEqual(lat, 50.0 + 1000.0 / 111320.0, places=6)


if __name__ == "__main__":
    unittest.main()
