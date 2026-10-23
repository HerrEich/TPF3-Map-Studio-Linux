import atexit
import shutil
import tempfile
import unittest
from unittest import mock

from src.osm import overpass_client
from src.osm.objects.osm_data import OSMData
from src.osm.overpass_client import OverpassClient
from src.osm.tile_cache import TileCache

STAMP_NEW = "2026-10-12T06:21:00Z"
STAMP_OLD = "2026-10-12T05:59:00Z"


class _Response:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _client():
    client = OverpassClient()
    # Eigener Cache-Ordner: Tests duerfen nie in den echten osm_cache schreiben.
    cache_dir = tempfile.mkdtemp(prefix="osm_tile_test_")
    atexit.register(shutil.rmtree, cache_dir, ignore_errors=True)
    client.tile_cache = TileCache(cache_dir)
    client.parser = mock.Mock()
    client.parser.new_data.return_value = OSMData()
    return client


class OsmDataTimestampTest(unittest.TestCase):

    def test_roundtrip(self):
        osm = OSMData()
        osm.data_timestamp = STAMP_NEW
        self.assertEqual(OSMData.from_dict(osm.to_dict()).data_timestamp, STAMP_NEW)

    def test_old_project_without_the_key(self):
        self.assertEqual(OSMData.from_dict({"nodes": [], "ways": []}).data_timestamp, "")

    def test_default_and_clear(self):
        osm = OSMData()
        self.assertEqual(osm.data_timestamp, "")
        osm.data_timestamp = STAMP_NEW
        osm.clear()
        self.assertEqual(osm.data_timestamp, "")


class ClientTimestampTest(unittest.TestCase):

    def test_timestamp_of(self):
        read = OverpassClient._timestamp_of
        self.assertEqual(read({"osm3s": {"timestamp_osm_base": STAMP_NEW}}), STAMP_NEW)
        self.assertEqual(read({"elements": []}), "")
        self.assertEqual(read({"osm3s": None}), "")
        self.assertEqual(read([]), "")

    def test_single_download_sets_the_timestamp(self):
        client = _client()
        data = {"osm3s": {"timestamp_osm_base": STAMP_NEW}, "elements": []}
        with mock.patch.object(overpass_client, "build_query", return_value="q"), \
             mock.patch.object(client, "_post", return_value=_Response(data)):
            osm = client._download(object())
        self.assertEqual(osm.data_timestamp, STAMP_NEW)

    def test_tiled_download_takes_the_oldest_timestamp(self):
        client = _client()
        first = {"osm3s": {"timestamp_osm_base": STAMP_NEW}, "elements": []}
        second = {"osm3s": {"timestamp_osm_base": STAMP_OLD}, "elements": []}
        with mock.patch.object(overpass_client, "plan_tiles", return_value=[object(), object()]), \
             mock.patch.object(overpass_client, "build_query", return_value="q"), \
             mock.patch.object(client, "_fetch_json", side_effect=[first, second]):
            osm = client._download_tiled(object())
        self.assertEqual(osm.data_timestamp, STAMP_OLD)

    def test_tiled_download_without_timestamps(self):
        client = _client()
        with mock.patch.object(overpass_client, "plan_tiles", return_value=[object()]), \
             mock.patch.object(overpass_client, "build_query", return_value="q"), \
             mock.patch.object(client, "_fetch_json", return_value={"elements": []}):
            osm = client._download_tiled(object())
        self.assertEqual(osm.data_timestamp, "")


if __name__ == "__main__":
    unittest.main()
