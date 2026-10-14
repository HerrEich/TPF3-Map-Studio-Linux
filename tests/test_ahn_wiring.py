"""AHN Niederlande: Verdrahtung in Exporter, Dialog, Freigabetext und Cache-Verwaltung."""

import unittest
from pathlib import Path

from src.core import cache_manager
from src.heightmap.heightmap_exporter import SOURCE_AHN_NL
from src.heightmap import ahn_nl_dem as ahn

ROOT = Path(__file__).resolve().parent.parent


class WiringTests(unittest.TestCase):

    def test_source_constant(self):
        self.assertEqual(SOURCE_AHN_NL, "ahn_nl")

    def test_cache_key_and_label(self):
        self.assertIn("ahn_nl_cache", cache_manager.CACHE_KEYS)
        self.assertIn("ahn_nl_cache", cache_manager.cache_labels())

    def test_share_description_knows_ahn(self):
        from src import share_description

        self.assertIn("ahn", share_description.LICENSE_URLS)
        self.assertIn("Rijkswaterstaat", share_description.AHN_ATTRIBUTION)

    def test_dialog_offers_ahn_source(self):
        source = (ROOT / "src" / "gui" / "heightmap_dialog.py").read_text(encoding="utf-8")

        for needle in (
            "SOURCE_AHN_NL",
            "AhnFetchJob",
            "NL_BOUNDS",
            "DEFAULT_AHN_CACHE_DIR",
            "ahn_cache_dir=DEFAULT_AHN_CACHE_DIR",
        ):
            self.assertIn(needle, source)

    def test_dialog_combo_has_five_sources(self):
        source = (ROOT / "src" / "gui" / "heightmap_dialog.py").read_text(encoding="utf-8")
        self.assertIn("self.source_combo.setItemData(4,", source)

    def test_bounds_cover_amsterdam_but_not_berlin(self):
        lat_min, lat_max, lon_min, lon_max = ahn.NL_BOUNDS
        self.assertTrue(lat_min <= 52.37 <= lat_max and lon_min <= 4.9 <= lon_max)
        self.assertFalse(lat_min <= 52.52 <= lat_max and lon_min <= 13.4 <= lon_max)


class DocsTests(unittest.TestCase):

    def _read(self, *parts):
        return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")

    def test_guide_describes_ahn(self):
        guide = self._read("src", "gui", "heightmap_guide.py")
        self.assertIn("AHN Niederlande", guide)
        self.assertIn("Actueel Hoogtebestand Nederland", guide)
        self.assertIn("CC0 1.0", guide)

    def test_notices_and_readmes_name_ahn(self):
        for name in ("THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.en.md"):
            text = self._read(name)
            self.assertIn("https://creativecommons.org/publicdomain/zero/1.0/", text, name)
            self.assertIn("Actueel Hoogtebestand Nederland", text, name)
        for name in ("README.md", "README.en.md"):
            self.assertIn("AHN", self._read(name), name)

    def test_overview_names_ahn(self):
        self.assertIn("AHN Niederlande", self._read("src", "gui", "feature_overview_dialog.py"))


if __name__ == "__main__":
    unittest.main()
