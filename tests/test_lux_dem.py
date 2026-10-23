"""Tests fuer die Luxemburg-Hoehenquelle (MNT Lidar 2024): Projektion, Kachel-Entpackung,
Kopf der BigTIFF-Datei, Abruf per Range und Hoehenabfrage. Die Datei wird synthetisch nachgebaut."""

import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from src.heightmap import lux_dem
from src.heightmap.lux2169 import LU_BOUNDS, latlon_to_lux, lux_to_latlon


class _Sel:
    """Minimaler Ersatz fuer ein Rechteck: Ecken in WGS84, kein Stauchfaktor."""

    scale_factor = 1.0

    def __init__(self, e0, n0, e1, n1):
        self._corners = [lux_to_latlon(e, n) for e, n in ((e0, n0), (e1, n0), (e1, n1), (e0, n1))]

    def corners_latlon(self):
        return [(float(a), float(b)) for a, b in self._corners]


def _lzw(tile_f8: np.ndarray) -> bytes:
    """LZW-Strom einer Kachel (wie GDAL ihn schreibt, Predictor 1) ueber Pillow/libtiff."""

    size = tile_f8.shape[0]
    raw = np.frombuffer(tile_f8.astype("<f8").tobytes(), dtype=np.uint8).reshape(size, size * 8)
    buf = io.BytesIO()
    Image.fromarray(raw, "L").save(buf, format="TIFF", compression="tiff_lzw", tiffinfo={278: size})
    buf.seek(0)
    with Image.open(buf) as im:
        off = im.tag_v2[273][0]
        cnt = im.tag_v2[279][0]
    return buf.getvalue()[off:off + cnt]


def _entry(tag, typ, count, value):
    return struct.pack("<HHQQ", tag, typ, count, value)


def build_cog(base_w, base_h, e0, n0, height_fn, tile=128, levels=4):
    """BigTIFF mit Uebersichtsstufen (0,5 m, 1 m, 2 m, 4 m, ...) und LZW-Kacheln."""

    sizes = [(base_w // 2 ** i, base_h // 2 ** i) for i in range(levels)]

    blobs = []   # je Ebene: Liste komprimierter Kacheln
    for lvl, (w, h) in enumerate(sizes):
        ps = 0.5 * 2 ** lvl
        tx, ty = -(-w // tile), -(-h // tile)
        tiles = []
        for r in range(ty):
            for c in range(tx):
                rr = np.arange(r * tile, (r + 1) * tile)
                cc = np.arange(c * tile, (c + 1) * tile)
                e = e0 + (cc + 0.5) * ps
                n = n0 - (rr + 0.5) * ps
                grid = height_fn(e[None, :], n[:, None]).astype(np.float64)
                tiles.append(_lzw(np.broadcast_to(grid, (tile, tile)).copy()))
        blobs.append(tiles)

    def ifd_size(n):
        return 8 + n * 20 + 8

    n_entries = [10 + (2 if i == 0 else 0) for i in range(levels)]
    pos = 16
    ifd_pos = []
    for n in n_entries:
        ifd_pos.append(pos)
        pos += ifd_size(n)

    geo_pos = pos
    pos += 24 + 48
    arr_pos = []
    for tiles in blobs:
        arr_pos.append(pos)
        pos += 16 * len(tiles)
    data_pos = pos

    offsets = []
    for tiles in blobs:
        offs = []
        for t in tiles:
            offs.append(data_pos)
            data_pos += len(t)
        offsets.append(offs)

    out = bytearray(b"II" + struct.pack("<HHHQ", 43, 8, 0, ifd_pos[0]))

    for lvl, (w, h) in enumerate(sizes):
        n = len(blobs[lvl])
        entries = [
            _entry(256, 4, 1, w),
            _entry(257, 4, 1, h),
            _entry(258, 3, 1, 64),
            _entry(259, 3, 1, 5),
            _entry(277, 3, 1, 1),
            _entry(317, 3, 1, 1),
            _entry(322, 3, 1, tile),
            _entry(323, 3, 1, tile),
            _entry(324, 16, n, arr_pos[lvl]),
            _entry(325, 16, n, arr_pos[lvl] + 8 * n),
        ]
        if lvl == 0:
            entries.append(_entry(33550, 12, 3, geo_pos))
            entries.append(_entry(33922, 12, 6, geo_pos + 24))
        entries.sort(key=lambda e: struct.unpack("<H", e[:2])[0])
        nxt = ifd_pos[lvl + 1] if lvl + 1 < levels else 0
        out += struct.pack("<Q", len(entries)) + b"".join(entries) + struct.pack("<Q", nxt)

    out += struct.pack("<3d", 0.5, 0.5, 0.0)
    out += struct.pack("<6d", 0.0, 0.0, 0.0, e0, n0, 0.0)

    for lvl, tiles in enumerate(blobs):
        out += struct.pack("<%dQ" % len(tiles), *offsets[lvl])
        out += struct.pack("<%dQ" % len(tiles), *[len(t) for t in tiles])

    for tiles in blobs:
        for t in tiles:
            out += t

    return bytes(out)


def ramp(e, n):
    return 100.0 + 0.01 * (e - 75000.0) + 0.02 * (n - 80000.0)


class LuxProjectionTest(unittest.TestCase):

    def test_origin_and_roundtrip(self):
        lat, lon = lux_to_latlon(80000.0, 100000.0)
        e, n = latlon_to_lux(lat, lon)
        self.assertAlmostEqual(float(e), 80000.0, delta=0.01)
        self.assertAlmostEqual(float(n), 100000.0, delta=0.01)

    def test_roundtrip_whole_country(self):
        e0, e1, n0, n1 = 48000.0, 107000.0, 56000.0, 140000.0
        e, n = np.meshgrid(np.linspace(e0, e1, 9), np.linspace(n0, n1, 9))
        lat, lon = lux_to_latlon(e, n)
        e2, n2 = latlon_to_lux(lat, lon)
        self.assertLess(float(np.abs(e2 - e).max()), 0.01)
        self.assertLess(float(np.abs(n2 - n).max()), 0.01)

    def test_country_lies_inside_bounds(self):
        lat, lon = lux_to_latlon(np.array([48880.5, 106189.0]), np.array([56965.0, 138809.0]))
        lat_min, lat_max, lon_min, lon_max = LU_BOUNDS
        # die Rasterecken liegen knapp ausserhalb des Landesumrisses, aber nahe daran
        self.assertTrue(np.all((lat > lat_min - 0.03) & (lat < lat_max + 0.03)))
        self.assertTrue(np.all((lon > lon_min - 0.03) & (lon < lon_max + 0.03)))

    def test_known_reference_point(self):
        # Mitte des Gebiets laut EPSG-Katalog (77322 / 97937 mit der aelteren 7-Parameter-Kennung);
        # die genauere Kennung EPSG:5486 weicht davon um rund 100 m ab.
        e, n = latlon_to_lux(49.815, 6.13)
        self.assertLess(abs(float(e) - 77322.0), 150.0)
        self.assertLess(abs(float(n) - 97937.0), 150.0)


class LuxDecodeTest(unittest.TestCase):

    def test_decode_tile_lzw(self):
        rng = np.random.default_rng(1)
        tile = rng.uniform(150, 500, (128, 128))
        tile[5, 7] = -9999.0
        arr = lux_dem.decode_tile(_lzw(tile), 128, 5)
        self.assertEqual(arr.shape, (128, 128))
        self.assertTrue(np.allclose(arr[0], tile[0].astype(np.float32)))
        self.assertTrue(np.isclose(arr[5, 7], -9999.0))

    def test_fallback_decoder_matches(self):
        rng = np.random.default_rng(2)
        tile = rng.uniform(150, 500, (128, 128))
        data = _lzw(tile)
        raw = lux_dem.lzw_decode(data, 128 * 128 * 8)
        self.assertEqual(raw, tile.astype("<f8").tobytes())

    def test_clean_heights(self):
        arr = np.array([[100.0, -9999.0, np.nan, 99999.0]], dtype=np.float32)
        out = lux_dem.clean_heights(arr)
        self.assertEqual(int(np.isfinite(out).sum()), 1)

    def test_level_for_pixel_size(self):
        self.assertEqual(lux_dem.level_for_pixel_size(4.0), 3)
        self.assertEqual(lux_dem.level_for_pixel_size(8.0), 4)
        self.assertEqual(lux_dem.level_for_pixel_size(100.0), lux_dem.MAX_LEVEL)


class LuxFetchTest(unittest.TestCase):

    E0, N0 = 74000.0, 82000.0

    def setUp(self):
        self.data = build_cog(2048, 2048, self.E0, self.N0, ramp)
        self.calls = []

    def get_range(self, url, start, length):
        self.calls.append((start, length))
        return self.data[start:start + length]

    def test_header(self):
        header = lux_dem.read_header(lambda s, n: self.data[s:s + n], 3)
        self.assertEqual((header["w"], header["h"], header["tile"]), (256, 256, 128))
        self.assertAlmostEqual(header["ps"], 4.0)
        self.assertEqual(len(header["offsets"]), 4)
        self.assertEqual((header["e0"], header["n0"]), (self.E0, self.N0))

    def test_fetch_and_sample(self):
        sel = _Sel(74300.0, 80900.0, 74900.0, 81500.0)

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            summary = lux_dem.fetch_tiles_for_selection(sel, cache, get_range=self.get_range, sleep=lambda s: None)
            self.assertGreater(summary.fetched, 0)
            self.assertEqual(summary.no_data, 0)

            # zweiter Lauf: alles aus dem Zwischenspeicher, kein Netz
            self.calls.clear()
            again = lux_dem.fetch_tiles_for_selection(sel, cache, get_range=self.get_range, sleep=lambda s: None)
            self.assertEqual(again.fetched, 0)
            self.assertEqual(self.calls, [])

            mosaic = lux_dem.LuxMosaic.from_cache(sel, cache)
            self.assertGreater(mosaic.slot_count, 0)
            self.assertEqual(mosaic.missing_slots, 0)
            self.assertTrue(mosaic.attributions)

            e = np.array([74400.0, 74600.0, 74800.0])
            n = np.array([81000.0, 81200.0, 81400.0])
            lat, lon = lux_to_latlon(e, n)
            h = mosaic.sample_grid(lat, lon)
            self.assertTrue(np.allclose(h, ramp(e, n), atol=0.05), (h, ramp(e, n)))

    def test_outside_is_nan(self):
        sel = _Sel(74300.0, 80900.0, 74900.0, 81500.0)

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            lux_dem.fetch_tiles_for_selection(sel, cache, get_range=self.get_range, sleep=lambda s: None)
            mosaic = lux_dem.LuxMosaic.from_cache(sel, cache)
            lat, lon = lux_to_latlon(np.array([60000.0]), np.array([60000.0]))
            self.assertTrue(np.isnan(mosaic.sample_grid(lat, lon)).all())

    def test_empty_cache_gives_empty_mosaic(self):
        sel = _Sel(74300.0, 80900.0, 74900.0, 81500.0)

        with tempfile.TemporaryDirectory() as tmp:
            mosaic = lux_dem.LuxMosaic.from_cache(sel, Path(tmp))
            self.assertEqual(mosaic.slot_count, 0)

    def test_merged_ranges_reduce_requests(self):
        sel = _Sel(74100.0, 80600.0, 74900.0, 81900.0)
        header = lux_dem.read_header(lambda s, n: self.data[s:s + n], 3)
        tiles = lux_dem.required_lux_tiles(sel, header)
        groups = lux_dem._merged_ranges(tiles, header)
        self.assertLessEqual(len(groups), len(tiles))

    def test_header_is_json_serialisable(self):
        header = lux_dem.read_header(lambda s, n: self.data[s:s + n], 3)
        self.assertEqual(json.loads(json.dumps(header))["w"], 256)


if __name__ == "__main__":
    unittest.main()
