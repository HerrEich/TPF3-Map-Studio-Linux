"""Tests: Overpass laedt nur zusaetzlich aktivierte Merkmale nach."""

import tempfile
import types
import unittest

from src.map.objects.selection import Selection
from src.osm import overpass_client as oc
from src.osm.overpass_query_builder import (
    OverpassQueryConfig,
    build_query,
    config_from_categories,
    query_categories,
)
from src.osm.tile_cache import TileCache


class _Parser:
    def parse(self, data):
        return types.SimpleNamespace(
            elements=data["elements"],
            node_count=0,
            way_count=len(data["elements"]),
            relation_count=0,
        )


class _Response:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


MARKERS = (
    ('way["highway"]', 1),
    ('way["building"]', 2),
    ('way["waterway"]', 3),
    ('way["leisure"~"^(park|garden)$"]', 4),
)


def _config(**flags):
    values = {name: False for name in (
        "railways", "highways", "buildings", "parks", "landuse", "vegetation",
        "water", "places", "biome_areas", "industry", "stations",
        "nature_details",
    )}
    values.update(flags)
    return OverpassQueryConfig(**values)


class CategoryTests(unittest.TestCase):

    def test_roundtrip(self):
        config = _config(highways=True, water=True)
        self.assertEqual(
            query_categories(config), frozenset({"highways", "water"})
        )
        again = config_from_categories(query_categories(config))
        self.assertEqual(again.to_dict(), config.to_dict())

    def test_tram_free_railways_are_their_own_group(self):
        config = _config(railways=True, include_tram=False)
        self.assertEqual(query_categories(config), frozenset({"railways_notram"}))
        again = config_from_categories({"railways_notram"})
        self.assertTrue(again.railways)
        self.assertFalse(again.include_tram)

    def test_single_group_query_only_has_that_group(self):
        selection = Selection.from_center(50.0, 8.0, 3000, 3000)
        text = build_query(selection, config_from_categories({"buildings"}))
        self.assertIn('way["building"]', text)
        self.assertNotIn('way["highway"]', text)


class IncrementalDownloadTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.client = oc.OverpassClient()
        self.client.parser = _Parser()
        self.client.tile_cache = TileCache(self._tmp.name)
        self.client.workers = 1
        self.client._sleep = lambda seconds: None
        self.selection = Selection.from_center(50.0, 8.0, 3000, 3000)
        self.queries = []

        def fake_post(server, query):
            self.queries.append(query)
            elements = [
                {"type": "way", "id": ident}
                for marker, ident in MARKERS
                if marker in query
            ]
            return _Response({
                "osm3s": {"timestamp_osm_base": "2026-10-01T00:00:00Z"},
                "elements": elements,
            })

        self.client._post = fake_post

    def ids(self, osm):
        return sorted(element["id"] for element in osm.elements)

    def test_extra_category_loads_only_the_missing_part(self):
        first = self.client.download(
            self.selection, _config(highways=True, buildings=True)
        )
        self.assertEqual(self.ids(first), [1, 2])
        self.assertEqual(len(self.queries), 1)

        self.queries.clear()
        second = self.client.download(
            self.selection, _config(highways=True, buildings=True, water=True)
        )

        self.assertEqual(len(self.queries), 1)
        self.assertIn('way["waterway"]', self.queries[0])
        self.assertNotIn('way["highway"]', self.queries[0])
        self.assertNotIn('way["building"]', self.queries[0])
        self.assertEqual(self.ids(second), [1, 2, 3])

    def test_same_request_again_needs_no_download(self):
        config = _config(highways=True, water=True)
        self.client.download(self.selection, config)
        self.queries.clear()
        osm = self.client.download(self.selection, config)
        self.assertEqual(self.queries, [])
        self.assertEqual(self.client.last_cache_hits, 1)
        self.assertEqual(self.ids(osm), [1, 3])

    def test_combination_of_cached_parts_needs_no_download(self):
        self.client.download(self.selection, _config(highways=True))
        self.client.download(self.selection, _config(water=True))
        self.queries.clear()

        osm = self.client.download(
            self.selection, _config(highways=True, water=True)
        )

        self.assertEqual(self.queries, [])
        self.assertEqual(self.ids(osm), [1, 3])

    def test_switched_off_category_does_not_reappear(self):
        self.client.download(
            self.selection, _config(highways=True, buildings=True)
        )
        self.queries.clear()

        osm = self.client.download(self.selection, _config(highways=True))

        self.assertEqual(self.ids(osm), [1])
        # Der Eintrag "Strassen + Gebaeude" ist keine Teilmenge: neu laden.
        self.assertEqual(len(self.queries), 1)

    def test_use_cache_false_loads_everything(self):
        config = _config(highways=True, buildings=True)
        self.client.download(self.selection, config)
        self.queries.clear()
        self.client.use_cache = False
        self.client.download(self.selection, config)
        self.assertEqual(len(self.queries), 1)
        self.assertIn('way["building"]', self.queries[0])

    def test_oldest_timestamp_wins_when_merging(self):
        self.client.download(self.selection, _config(highways=True))

        def newer_post(server, query):
            return _Response({
                "osm3s": {"timestamp_osm_base": "2026-10-09T00:00:00Z"},
                "elements": [{"type": "way", "id": 3}],
            })

        self.client._post = newer_post
        osm = self.client.download(
            self.selection, _config(highways=True, water=True)
        )

        self.assertEqual(osm.data_timestamp, "2026-10-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
