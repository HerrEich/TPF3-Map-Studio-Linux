"""AHN Niederlande als Hoehenquelle: Kachelwahl, WCS-Parameter, Abruf, Zwischenspeicher, Lesen."""

import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, TiffImagePlugin

from src.heightmap import ahn_nl_dem as ahn
from src.heightmap.dgm1_dem import (
    Dgm1Cancelled,
    Dgm1Error,
    read_raster_array,
    read_raster_info,
)
from src.http_identity import USER_AGENT

NODATA = 3.4028234663852886e38


class FakeSelection:
    """Zwei mal zwei Kilometer um Amsterdam, nicht gedreht, nicht gestaucht."""

    def __init__(self, scale_factor=1.0):
        self.scale_factor = scale_factor

    def corners_latlon(self):
        d_lat, d_lon = 0.009, 0.015
        lat, lon = 52.37, 4.90
        return [
            (lat - d_lat, lon - d_lon),
            (lat - d_lat, lon + d_lon),
            (lat + d_lat, lon + d_lon),
            (lat + d_lat, lon - d_lon),
        ]


def tile_bytes(ie=600, inn=5781, nodata_share=0.0, all_nodata=False):
    """Ein GeoTIFF wie vom PDOK-Dienst: 500 x 500, Float32, 2 m, EPSG:25831, Nodata 3.4e38."""

    arr = np.full((ahn.TILE_PX, ahn.TILE_PX), 1.5, dtype=np.float32)

    if all_nodata:
        arr[:] = NODATA
    elif nodata_share:
        arr[: int(ahn.TILE_PX * nodata_share), :] = NODATA

    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[33550] = (2.0, 2.0, 0.0)
    ifd[33922] = (0.0, 0.0, 0.0, float(ie * 1000), float((inn + 1) * 1000), 0.0)
    ifd[34735] = (1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, ahn.NL_EPSG)
    ifd[42113] = "3.4028234663852886e+38"

    buf = io.BytesIO()
    Image.fromarray(arr, mode="F").save(buf, format="TIFF", tiffinfo=ifd, compression="tiff_deflate")
    return buf.getvalue()


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code
        self.headers = {}


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.handler(params)


def no_sleep(_seconds):
    return None


class SelectionTests(unittest.TestCase):

    def test_tiles_are_in_zone_31_around_amsterdam(self):
        tiles = ahn.required_ahn_tiles(FakeSelection())

        self.assertGreaterEqual(len(tiles), 4)

        for zone, ie, inn in tiles:
            self.assertEqual(zone, 31)
            self.assertTrue(600 <= ie <= 800, ie)
            self.assertTrue(5700 <= inn <= 5900, inn)

    def test_scaled_map_is_no_longer_rejected(self):
        self.assertGreater(len(ahn.required_ahn_tiles(FakeSelection(scale_factor=2.0))), 0)

    def test_wcs_parameters_use_the_kilometer_grid(self):
        params = ahn.tile_params(600, 5781)

        self.assertEqual(params["BBOX"], "600000,5781000,601000,5782000")
        self.assertEqual(params["WIDTH"], 500)
        self.assertEqual(params["HEIGHT"], 500)
        self.assertEqual(params["CRS"], "EPSG:25831")
        self.assertEqual(params["COVERAGE"], "dtm_05m")
        self.assertEqual(params["FORMAT"], "GEOTIFF")

    def test_cache_name_matches_slot_scheme(self):
        self.assertEqual(ahn.cache_file_name(600, 5781), "31_600_5781__ahn")

    def test_uses_shared_user_agent(self):
        self.assertIs(ahn.USER_AGENT, USER_AGENT)


class CheckTileTests(unittest.TestCase):

    def test_tile_with_data(self):
        self.assertTrue(ahn.check_tile(tile_bytes(), 600, 5781))

    def test_tile_with_gaps_still_has_data(self):
        self.assertTrue(ahn.check_tile(tile_bytes(nodata_share=0.3), 600, 5781))

    def test_tile_without_data(self):
        self.assertFalse(ahn.check_tile(tile_bytes(all_nodata=True), 600, 5781))

    def test_service_exception_becomes_error(self):
        body = (
            b'<?xml version="1.0"?><ServiceExceptionReport><ServiceException code="X">'
            b"Unrecognized value for the FORMAT parameter.</ServiceException></ServiceExceptionReport>"
        )

        with self.assertRaises(Dgm1Error) as ctx:
            ahn.check_tile(body, 600, 5781)

        self.assertIn("FORMAT", str(ctx.exception))

    def test_garbage_becomes_error(self):
        with self.assertRaises(Dgm1Error):
            ahn.check_tile(b"<html>nope</html>", 600, 5781)


class ReaderTests(unittest.TestCase):

    def test_reader_understands_zone_31_tile(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "31_600_5781__ahn.tif"
            path.write_bytes(tile_bytes(nodata_share=0.25))

            info = read_raster_info(path)
            self.assertEqual(info.zone, 31)

            arr = read_raster_array(info)
            self.assertEqual(arr.shape, (500, 500))
            self.assertAlmostEqual(float(np.isnan(arr).mean()), 0.25, places=2)
            self.assertAlmostEqual(float(np.nanmax(arr)), 1.5, places=3)


class FetchTests(unittest.TestCase):

    def test_fetch_stores_tiles_and_skips_cached(self):
        selection = FakeSelection()
        expected = ahn.required_ahn_tiles(selection)

        session = FakeSession(lambda params: FakeResponse(tile_bytes()))

        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)

            summary = ahn.fetch_tiles_for_selection(
                selection, cache, session=session, sleep=no_sleep, min_interval_s=0
            )

            self.assertEqual(summary.fetched, len(expected))
            self.assertEqual(len(session.calls), len(expected))

            zone, ie, inn = expected[0]
            self.assertTrue((cache / f"31_{ie}_{inn}__ahn.tif").exists())
            meta = json.loads((cache / f"31_{ie}_{inn}__ahn.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["Origin"], "AHN")
            self.assertIn("Rijkswaterstaat", meta["Attribution"])

            session2 = FakeSession(lambda params: FakeResponse(tile_bytes()))
            summary2 = ahn.fetch_tiles_for_selection(
                selection, cache, session=session2, sleep=no_sleep, min_interval_s=0
            )

            self.assertEqual(session2.calls, [])
            self.assertEqual(summary2.already_cached, len(expected))
            self.assertEqual(summary2.fetched, 0)

    def test_empty_tiles_are_marked_and_not_requested_again(self):
        selection = FakeSelection()
        expected = ahn.required_ahn_tiles(selection)

        session = FakeSession(lambda params: FakeResponse(tile_bytes(all_nodata=True)))

        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)

            summary = ahn.fetch_tiles_for_selection(
                selection, cache, session=session, sleep=no_sleep, min_interval_s=0
            )

            self.assertEqual(summary.no_data, len(expected))
            self.assertEqual(summary.fetched, 0)
            self.assertEqual(len(list(cache.glob("*.none"))), len(expected))
            self.assertEqual(list(cache.glob("*.tif")), [])

            session2 = FakeSession(lambda params: FakeResponse(tile_bytes()))
            ahn.fetch_tiles_for_selection(selection, cache, session=session2, sleep=no_sleep, min_interval_s=0)
            self.assertEqual(session2.calls, [])

    def test_http_error_stops_with_message(self):
        session = FakeSession(lambda params: FakeResponse(b"", status_code=404))

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(Dgm1Error) as ctx:
                ahn.fetch_tiles_for_selection(
                    FakeSelection(), Path(folder), session=session, sleep=no_sleep, min_interval_s=0
                )

        self.assertIn("404", str(ctx.exception))

    def test_server_error_is_retried_then_reported(self):
        session = FakeSession(lambda params: FakeResponse(b"", status_code=503))

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(Dgm1Error):
                ahn.fetch_tiles_for_selection(
                    FakeSelection(), Path(folder), session=session, sleep=no_sleep, min_interval_s=0
                )

        self.assertEqual(len(session.calls), 3)

    def test_cancel(self):
        session = FakeSession(lambda params: FakeResponse(tile_bytes()))

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(Dgm1Cancelled):
                ahn.fetch_tiles_for_selection(
                    FakeSelection(),
                    Path(folder),
                    cancelled=lambda: True,
                    session=session,
                    sleep=no_sleep,
                    min_interval_s=0,
                )

        self.assertEqual(session.calls, [])


if __name__ == "__main__":
    unittest.main()
