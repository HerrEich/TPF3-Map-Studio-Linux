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


class ActualityTest(unittest.TestCase):

    def _text(self, info):
        return build_share_description(_selection(), info, fmt="text", **COMMON)

    def test_single_value_and_range(self):
        one = HeightmapBuildInfo(source=SOURCE_SWISSALTI3D, actualities=["2021"])
        self.assertIn("Datenstand der Höhendaten: 2021", self._text(one))
        many = HeightmapBuildInfo(source=SOURCE_DGM1_DE, actualities=["2019", "2023"])
        self.assertIn("Datenstand der Höhendaten: 2019 – 2023", self._text(many))

    def test_no_row_without_data(self):
        self.assertNotIn("Datenstand", self._text(HeightmapBuildInfo(source=SOURCE_DGM1_DE)))
        self.assertNotIn("Datenstand", self._text(HeightmapBuildInfo()))


class MosaicActualityTest(unittest.TestCase):

    def test_mosaic_collects_distinct_sorted_dates(self):
        import numpy as np
        from src.heightmap.dgm1_dem import Dgm1Mosaic, Slot

        cells = np.zeros((2, 2), dtype=np.float32)
        slots = [
            Slot(zone=32, ie=1, inn=1, cell_m=4.0, cells=cells, actualities=["2023"]),
            Slot(zone=32, ie=2, inn=1, cell_m=4.0, cells=cells, actualities=["2021"]),
            Slot(zone=32, ie=3, inn=1, cell_m=4.0, cells=cells, actualities=["2021"]),
        ]
        self.assertEqual(Dgm1Mosaic(slots).actualities, ["2021", "2023"])

    def test_cache_file_passes_actuality_on(self):
        import json
        import tempfile
        from pathlib import Path
        from src.heightmap import dgm1_dem

        with tempfile.TemporaryDirectory() as folder:
            tif = Path(folder) / "32_1_1__XX.tif"
            tif.write_bytes(b"x")
            tif.with_suffix(".json").write_text(
                json.dumps({"Attribution": "© A", "Actuality": 2022}), encoding="utf-8"
            )
            with mock.patch.object(dgm1_dem, "read_raster_info", return_value=object()), \
                 mock.patch.object(dgm1_dem, "slots_from_raster", return_value=[]) as called:
                dgm1_dem._slots_from_cache_file(tif, 4.0, None)

        self.assertEqual(called.call_args.args[3:], ("© A", "2022"))


class BiomeRowTest(unittest.TestCase):

    def test_biome_row_only_with_summary(self):
        with_biomes = build_share_description(
            _selection(), HeightmapBuildInfo(), fmt="text",
            biomes="Wald → Biom 1", **COMMON
        )
        self.assertIn("Biome: Wald → Biom 1", with_biomes)
        without = build_share_description(
            _selection(), HeightmapBuildInfo(), fmt="text", **COMMON
        )
        self.assertNotIn("Biome:", without)


class LanguageTest(unittest.TestCase):

    def _text(self, **kwargs):
        return build_share_description(
            _selection(), HeightmapBuildInfo(), fmt="text", **kwargs, **COMMON
        )

    def test_english_text_with_decimal_point(self):
        text = self._text(language="en")
        self.assertIn("Map size", text)
        self.assertIn("14.3 x 14.3 km", text)

    def test_german_text_with_decimal_comma(self):
        text = self._text(language="de")
        self.assertIn("Kartengröße", text)
        self.assertIn("14,3 x 14,3 km", text)

    def test_language_is_restored_afterwards(self):
        self._text(language="en")
        self.assertIsNone(share_description._lang)
        with self.assertRaises(ValueError):
            build_share_description(
                _selection(), HeightmapBuildInfo(), fmt="html", language="en", **COMMON
            )
        self.assertIsNone(share_description._lang)

    def test_edit_params_follow_the_text_language(self):
        text = self._text(language="en", edit_params=dict(smooth_sigma=15))
        self.assertIn("Terrain smoothed (15 m)", text)
        text = self._text(language="de", edit_params=dict(smooth_sigma=15))
        self.assertIn("Gelände geglättet (15 m)", text)

    def test_relative_values_are_marked(self):
        text = self._text(language="de", relative_values=True)
        self.assertIn("(auf Wasserhöhe 0 bezogen)", text)
        self.assertNotIn("bezogen", self._text(language="de"))


class OsmTimestampRowTest(unittest.TestCase):

    def _text(self, language="de", **kwargs):
        return build_share_description(
            _selection(), HeightmapBuildInfo(), fmt="text", language=language, **kwargs, **COMMON
        )

    def test_formats_per_language(self):
        stamp = "2026-10-12T06:21:00Z"
        self.assertIn("Datenstand der OSM-Daten: 12.10.2026 06:21 UTC", self._text("de", osm_timestamp=stamp))
        self.assertIn("Date of the OSM data: 2026-10-12 06:21 UTC", self._text("en", osm_timestamp=stamp))

    def test_unreadable_value_is_shown_as_is(self):
        self.assertIn("Datenstand der OSM-Daten: gestern", self._text(osm_timestamp="gestern"))

    def test_no_row_without_value_or_without_osm(self):
        self.assertNotIn("Datenstand der OSM", self._text())
        self.assertNotIn(
            "Datenstand der OSM",
            self._text(osm_timestamp="2026-10-12T06:21:00Z", osm_used=False),
        )


if __name__ == "__main__":
    unittest.main()
