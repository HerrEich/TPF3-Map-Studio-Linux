import unittest
from src.osm.overpass_query_builder import OverpassQueryConfig, build_query
from src.gui import overpass_dialog


class _Sel:
    pass


class NatureDetailsTests(unittest.TestCase):
    def test_default_off(self):
        self.assertFalse(OverpassQueryConfig().nature_details)

    def test_label_present(self):
        self.assertIn("nature_details", [k for k, _ in overpass_dialog.CATEGORY_LABELS])

    def test_roundtrip(self):
        c = OverpassQueryConfig(nature_details=True)
        self.assertTrue(OverpassQueryConfig.from_dict(c.to_dict()).nature_details)


if __name__ == "__main__":
    unittest.main()
