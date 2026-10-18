import math
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.heightmap import bev_dem
from src.heightmap.dgm1_dem import Dgm1Cancelled

FIXTURE = Path(__file__).parent / "data" / "bev_tile_l2_graz.bin"

GRAZ = (47.07, 15.44)


class FakeSelection:
    """Kleines Rechteck um Graz (ca. 1 km x 1 km), unrotiert."""

    scale_factor = 1.0

    def __init__(self, scale_factor=1.0):
        self.scale_factor = scale_factor

    def corners_latlon(self):
        lat, lon = GRAZ
        d_lat, d_lon = 0.0045, 0.0066
        return [
            (lat - d_lat, lon - d_lon),
            (lat - d_lat, lon + d_lon),
            (lat + d_lat, lon + d_lon),
            (lat + d_lat, lon - d_lon),
        ]


def _build_fake_file(blob):
    """Minimales BigTIFF mit 3 Ebenen; Ebene 2 hat 25 x 25 Kacheln, alle zeigen auf blob."""

    def ifd(tags, next_off):
        out = struct.pack("<Q", len(tags))
        for tag, typ, count, value in tags:
            out += struct.pack("<HHQ", tag, typ, count) + value
        return out + struct.pack("<Q", next_off)

    def short(v):
        return struct.pack("<H", v).ljust(8, b"\0")

    def long8(v):
        return struct.pack("<Q", v)

    data = bytearray(b"II" + struct.pack("<HHHQ", 43, 8, 0, 16))

    blob_off = 4000
    n_tiles = 625
    offsets_off = blob_off + len(blob) + 16
    counts_off = offsets_off + n_tiles * 8

    def level_tags(w, with_arrays):
        tags = [
            (256, 3, 1, short(w)),
            (257, 3, 1, short(w)),
            (259, 3, 1, short(5)),
            (317, 3, 1, short(3)),
            (322, 3, 1, short(512)),
            (323, 3, 1, short(512)),
        ]
        if with_arrays:
            tags.append((324, 16, n_tiles, long8(offsets_off)))
            tags.append((325, 16, n_tiles, long8(counts_off)))
        return tags

    ifd0 = ifd(level_tags(50001, False), 16 + 8 + 20 * 6 + 8 + 100)
    ifd1_off = 16 + 8 + 20 * 6 + 8 + 100
    ifd1 = ifd(level_tags(25000, False), ifd1_off + 8 + 20 * 6 + 8 + 100)
    ifd2_off = ifd1_off + 8 + 20 * 6 + 8 + 100
    ifd2 = ifd(level_tags(12500, True), 0)

    data += ifd0
    data += b"\0" * (ifd1_off - len(data))
    data += ifd1
    data += b"\0" * (ifd2_off - len(data))
    data += ifd2
    assert len(data) < blob_off
    data += b"\0" * (blob_off - len(data))
    data += blob
    data += b"\0" * (offsets_off - len(data))
    data += struct.pack("<%dQ" % n_tiles, *([blob_off] * n_tiles))
    data += struct.pack("<%dQ" % n_tiles, *([len(blob)] * n_tiles))
    return bytes(data)


class ProjectionTests(unittest.TestCase):
    def test_origin(self):
        e, n = bev_dem.latlon_to_laea(52.0, 10.0)
        self.assertAlmostEqual(float(e), 4321000.0, places=3)
        self.assertAlmostEqual(float(n), 3210000.0, places=3)

    def test_epsg_guidance_note_example(self):
        e, n = bev_dem.latlon_to_laea(50.0, 5.0)
        self.assertAlmostEqual(float(e), 3962799.45, places=1)
        self.assertAlmostEqual(float(n), 2999718.85, places=1)

    def test_graz_lies_in_expected_file(self):
        e, n = bev_dem.latlon_to_laea(*GRAZ)
        self.assertEqual(int(e // 50000) * 50000, 4700000)
        self.assertEqual(int(n // 50000) * 50000, 2650000)


class LevelTests(unittest.TestCase):
    def test_level_for_pixel_size(self):
        self.assertEqual(bev_dem.level_for_pixel_size(4.0), 2)
        self.assertEqual(bev_dem.level_for_pixel_size(7.9), 2)
        self.assertEqual(bev_dem.level_for_pixel_size(8.0), 3)
        self.assertEqual(bev_dem.level_for_pixel_size(200.0), 7)
        self.assertEqual(bev_dem.level_for_pixel_size(100000.0), 8)

    def test_file_name(self):
        self.assertEqual(
            bev_dem.file_name(4700000, 2650000),
            "ALS_DTM_CRS3035RES50000mN2650000E4700000",
        )


class DecodeTests(unittest.TestCase):
    def test_real_tile_decodes_to_plausible_heights(self):
        arr = bev_dem.decode_tile(FIXTURE.read_bytes())
        self.assertEqual(arr.shape, (512, 512))
        self.assertGreater(float(arr.min()), 300.0)
        self.assertLess(float(arr.max()), 500.0)
        self.assertAlmostEqual(float(arr.mean()), 350.316, places=2)
        # Gelaende: Nachbarpixel unterscheiden sich kaum
        self.assertLess(float(np.abs(np.diff(arr, axis=1)).mean()), 0.5)

    def test_truncated_data_is_rejected(self):
        with self.assertRaises(Exception):
            bev_dem.decode_tile(FIXTURE.read_bytes()[:1000])

    def test_clean_heights_marks_nodata(self):
        arr = np.array([[1.0, -9999.0, np.nan, 9000.0]], dtype=np.float32)
        out = bev_dem.clean_heights(arr)
        self.assertTrue(np.isnan(out[0, 1:]).all())
        self.assertEqual(float(out[0, 0]), 1.0)


class RequiredTilesTests(unittest.TestCase):
    def test_small_square_needs_few_tiles(self):
        tiles = bev_dem.required_bev_tiles(FakeSelection(), 2)
        self.assertGreaterEqual(len(tiles), 1)
        self.assertLessEqual(len(tiles), 4)
        self.assertIn((4700000, 2650000, 2, 11, 16), tiles)

    def test_coarser_level_needs_no_more_tiles(self):
        a = bev_dem.required_bev_tiles(FakeSelection(), 2)
        b = bev_dem.required_bev_tiles(FakeSelection(), 5)
        self.assertLessEqual(len(b), len(a))


class FetchAndSampleTests(unittest.TestCase):
    def setUp(self):
        self.blob = FIXTURE.read_bytes()
        self.file = _build_fake_file(self.blob)
        self.requests = []

    def get_range(self, url, start, length):
        self.requests.append((url, start, length))
        return self.file[start:start + length]

    def test_fetch_stores_only_needed_tiles_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = bev_dem.fetch_tiles_for_selection(
                FakeSelection(), Path(tmp), get_range=self.get_range, sleep=lambda s: None
            )
            self.assertEqual(summary.fetched, summary.total)
            self.assertGreaterEqual(summary.fetched, 1)
            tile_requests = [r for r in self.requests if r[2] == len(self.blob)]
            self.assertEqual(len(tile_requests), summary.fetched)

            self.requests.clear()
            again = bev_dem.fetch_tiles_for_selection(
                FakeSelection(), Path(tmp), get_range=self.get_range, sleep=lambda s: None
            )
            self.assertEqual(again.fetched, 0)
            self.assertEqual(again.already_cached, summary.total)
            self.assertEqual(self.requests, [])

            mosaic = bev_dem.BevMosaic.from_cache(FakeSelection(), Path(tmp))
            self.assertEqual(mosaic.missing_slots, 0)
            self.assertEqual(mosaic.slot_count, summary.total)
            self.assertTrue(mosaic.attributions)
            lat, lon = GRAZ
            value = mosaic.sample_grid(np.array([[lat]]), np.array([[lon]]))
            self.assertTrue(np.isfinite(value[0, 0]))
            self.assertTrue(300.0 < float(value[0, 0]) < 500.0)

    def test_cancel_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Dgm1Cancelled):
                bev_dem.fetch_tiles_for_selection(
                    FakeSelection(),
                    Path(tmp),
                    get_range=self.get_range,
                    cancelled=lambda: True,
                    sleep=lambda s: None,
                )

    def test_mosaic_without_tiles_gives_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            mosaic = bev_dem.BevMosaic.from_cache(FakeSelection(), Path(tmp))
            self.assertEqual(mosaic.slot_count, 0)
            value = mosaic.sample_grid(np.array([[GRAZ[0]]]), np.array([[GRAZ[1]]]))
            self.assertTrue(np.isnan(value[0, 0]))

    def test_sampling_matches_pixel_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            tile = (4700000, 2650000, 2, 11, 16)
            rows, cols = np.mgrid[0:512, 0:512]
            arr = (rows * 0.5 + cols * 0.25).astype(np.float32)
            path = bev_dem.tile_path(Path(tmp), *tile)
            path.parent.mkdir(parents=True)
            np.save(path, arr)
            mosaic = bev_dem.BevMosaic(Path(tmp), 2, [tile])

            lat = np.array([[47.0700, 47.0710]])
            lon = np.array([[15.4400, 15.4415]])
            e, n = bev_dem.latlon_to_laea(lat, lon)
            col, row = bev_dem._to_pixel(e, n, 4700000, 2650000, 2)
            expected = (row - 11 * 512) * 0.5 + (col - 16 * 512) * 0.25
            got = mosaic.sample_grid(lat, lon)
            np.testing.assert_allclose(got, expected, atol=0.01)

    def test_missing_tile_inside_file_is_nan_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tile = (4700000, 2650000, 2, 11, 16)
            arr = np.full((512, 512), 100.0, dtype=np.float32)
            path = bev_dem.tile_path(Path(tmp), *tile)
            path.parent.mkdir(parents=True)
            np.save(path, arr)
            mosaic = bev_dem.BevMosaic(Path(tmp), 2, [tile])
            e, n = 4700000.0 + 500.0, 2650000.0 + 500.0
            # weit entfernt von der geladenen Kachel
            lat = np.array([[46.5]])
            lon = np.array([[15.0]])
            self.assertTrue(np.isnan(mosaic.sample_grid(lat, lon)[0, 0]))


if __name__ == "__main__":
    unittest.main()
