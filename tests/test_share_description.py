import unittest
from unittest import mock

from src.heightmap.heightmap_exporter import (
    SOURCE_COPERNICUS,
    SOURCE_DGM1_DE,
    SOURCE_SWISSALTI3D,
    HeightmapBuildInfo,
)
from src.map.objects.selection import Selection
from src import share_description
from src.share_description import build_share_description, edit_notes

COMMON = dict(range_min_m=100.0, range_max_m=900.0, water_level_m=120.0)


def _selection(scale=1.0):
    return Selection.from_center(
        46.95, 7.45, 14336.0, 14336.0, scale_factor=scale
    )


class ShareDescriptionTest(unittest.TestCase):

    def test_swiss_has_attribution_and_no_copernicus(self):
        info = HeightmapBuildInfo(source=SOURCE_SWISSALTI3D)
        text = build_share_description(_selection(), info, fmt="text", **COMMON)
        self.assertIn("swisstopo", text)
        self.assertNotIn("Copernicus DEM", text)

    def test_fallback_adds_copernicus(self):
        info = HeightmapBuildInfo(
            source=SOURCE_DGM1_DE, fallback_fraction=0.05, attributions=["© Test"]
        )
        text = build_share_description(_selection(), info, fmt="text", **COMMON)
        self.assertIn("© Test", text)
        self.assertIn("produced using Copernicus WorldDEM-30", text)

    def test_scaled_map_shows_real_area(self):
        text = build_share_description(
            _selection(5.0), HeightmapBuildInfo(), fmt="text", **COMMON
        )
        self.assertIn("5", text)
        self.assertEqual(text.count("km"), 2)

    def test_relative_values(self):
        text = build_share_description(
            _selection(), HeightmapBuildInfo(), fmt="text",
            relative_values=True, **COMMON
        )
        self.assertIn("-20 bis 780 m", text)

    def test_formats(self):
        info = HeightmapBuildInfo()
        md = build_share_description(_selection(), info, fmt="markdown", **COMMON)
        bb = build_share_description(_selection(), info, fmt="bbcode", **COMMON)
        self.assertIn("- **", md)
        self.assertTrue(bb.rstrip().endswith("[/list]"))
        with self.assertRaises(ValueError):
            build_share_description(_selection(), info, fmt="html", **COMMON)

    def test_license_url_only_when_set(self):
        info = HeightmapBuildInfo(source=SOURCE_COPERNICUS)
        with mock.patch.dict(share_description.LICENSE_URLS, {}, clear=True):
            plain = build_share_description(_selection(), info, fmt="markdown", **COMMON)
        osm_line = next(l for l in plain.splitlines() if "ODbL" in l)
        self.assertNotIn("](", osm_line)
        with mock.patch.dict(share_description.LICENSE_URLS, {"osm": "https://example.org/x"}, clear=True):
            linked = build_share_description(_selection(), info, fmt="bbcode", **COMMON)
        self.assertIn("[url=https://example.org/x]", linked)

    def test_no_osm_line_without_osm(self):
        text = build_share_description(
            _selection(), HeightmapBuildInfo(), fmt="text", osm_used=False, **COMMON
        )
        self.assertNotIn("OpenStreetMap", text)


class ExperimentalHintTest(unittest.TestCase):

    def _text(self, width_m, height_m, fmt="text"):
        selection = Selection.from_center(50.0, 7.0, width_m, height_m)
        return build_share_description(
            selection, HeightmapBuildInfo(), fmt=fmt, **COMMON
        )

    def test_experimental_size_has_hint_and_link(self):
        text = self._text(10752.0, 53760.0, fmt="bbcode")
        self.assertIn("experimentalMapFeatures", text)
        self.assertIn("16 GB", text)
        self.assertIn(
            "[url=https://wiki.transportfever3.com/doku.php?id=gamemanual:mapsizes",
            text,
        )
        self.assertIn("Grössenwahnsinnig 1:5", text)

    def test_normal_size_has_no_hint(self):
        text = self._text(14336.0, 14336.0)
        self.assertNotIn("experimentalMapFeatures", text)
        self.assertIn("Gross 1:1", text)

    def test_unknown_size_has_no_hint_and_no_format_row(self):
        text = self._text(5000.0, 5000.0)
        self.assertNotIn("experimentalMapFeatures", text)
        self.assertNotIn("Kartenformat im Spiel", text)


class EditNotesTest(unittest.TestCase):

    def test_nothing_set(self):
        self.assertEqual(edit_notes(), [])

    def test_all_set(self):
        notes = edit_notes(
            smooth_sigma=15,
            flatten_sigma=10,
            slope=(100, 400),
            enforce=(2.0, 8.0, 10),
            blend_transition=60,
            clip_mode="Oben kappen",
        )
        self.assertEqual(len(notes), 6)
        self.assertIn("15 m", notes[0])
        self.assertIn("Stärke 100 %", notes[2])
        self.assertIn("2 bis 8 m", notes[3])
        self.assertIn("Oben kappen", notes[5])


class LicenseTextTest(unittest.TestCase):

    def _text(self, info, fmt="text"):
        return build_share_description(_selection(), info, fmt=fmt, **COMMON)

    def test_copernicus_notice_for_modified_data(self):
        text = self._text(HeightmapBuildInfo(source=SOURCE_COPERNICUS))
        self.assertIn("produced using Copernicus WorldDEM-30", text)
        self.assertIn("all rights reserved", text)
        self.assertIn("do not incur any liability", text)

    def test_dgm1_names_licences_and_change(self):
        info = HeightmapBuildInfo(source=SOURCE_DGM1_DE, attributions=["© Test"])
        text = self._text(info, fmt="markdown")
        self.assertIn("dl-de/by-2-0", text)
        self.assertIn("(http://www.govdata.de/dl-de/by-2-0)", text)
        self.assertIn("CC BY 4.0", text)
        self.assertIn("Daten verändert", text)
        self.assertNotIn("produced using Copernicus", text)

    def test_default_license_links(self):
        md = self._text(HeightmapBuildInfo(), fmt="markdown")
        self.assertIn("(https://www.openstreetmap.org/copyright)", md)
        swiss = self._text(HeightmapBuildInfo(source=SOURCE_SWISSALTI3D), fmt="markdown")
        self.assertIn("terms-of-use-free-geodata-and-geoservices", swiss)


if __name__ == "__main__":
    unittest.main()
