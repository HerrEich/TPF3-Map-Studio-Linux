import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from src.heightmap.tpf2_heightmap_import import (
    Tpf2HeightmapError,
    find_map_sizes,
    load_tpf2_heightmap,
    raw_to_meters,
)


def _save(arr: np.ndarray, folder: str, name: str, mode: str | None = None) -> Path:
    p = Path(folder) / name
    im = Image.fromarray(arr) if mode is None else Image.fromarray(arr).convert(mode)
    im.save(p)
    return p


class FindMapSizesTest(unittest.TestCase):
    def test_winzig_1_5(self):
        sizes, rotated = find_map_sizes(385, 1921)
        self.assertEqual([m.label for m in sizes], ["Winzig 1:5"])
        self.assertFalse(rotated)

    def test_gedreht(self):
        sizes, rotated = find_map_sizes(1921, 385)
        self.assertEqual([m.label for m in sizes], ["Winzig 1:5"])
        self.assertTrue(rotated)

    def test_doppelte_groesse_liefert_alle_kandidaten(self):
        sizes, _ = find_map_sizes(513, 1537)
        labels = [m.label for m in sizes]
        self.assertIn("Winzig 1:3", labels)
        self.assertIn("Winzig 1:4", labels)

    def test_unbekannt(self):
        sizes, rotated = find_map_sizes(100, 100)
        self.assertEqual(sizes, ())
        self.assertFalse(rotated)


class LoadTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_16bit_winzig(self):
        a = np.zeros((1921, 385), dtype=np.uint16)
        a[0, 0] = 819
        a[-1, -1] = 65517
        hm = load_tpf2_heightmap(_save(a, self.dir, "hm.png"))
        self.assertFalse(hm.is_8bit)
        self.assertEqual((hm.width_px, hm.height_px), (385, 1921))
        self.assertEqual((hm.width_m, hm.height_m), (1536.0, 7680.0))
        self.assertEqual(hm.map_size.label, "Winzig 1:5")
        self.assertEqual(hm.raw_max, 65517)
        self.assertEqual(hm.raw.dtype, np.uint16)

    def test_unbekannte_groesse_wird_trotzdem_geladen(self):
        a = np.full((100, 100), 1000, dtype=np.uint16)
        hm = load_tpf2_heightmap(_save(a, self.dir, "hm.png"))
        self.assertIsNone(hm.map_size)
        self.assertEqual(hm.width_m, 396.0)

    def test_8bit_wird_gestreckt(self):
        a = np.array([[0, 255], [128, 255]], dtype=np.uint8)
        hm = load_tpf2_heightmap(_save(a, self.dir, "hm8.png"))
        self.assertTrue(hm.is_8bit)
        self.assertEqual(hm.raw_max, 65535)
        self.assertEqual(hm.raw_min, 0)

    def test_farbbild_abgelehnt(self):
        a = np.zeros((10, 10, 3), dtype=np.uint8)
        with self.assertRaises(Tpf2HeightmapError) as ctx:
            load_tpf2_heightmap(_save(a, self.dir, "rgb.png"))
        self.assertEqual(ctx.exception.code, "mode")

    def test_fehlende_datei(self):
        with self.assertRaises(Tpf2HeightmapError) as ctx:
            load_tpf2_heightmap(Path(self.dir) / "gibtsnicht.png")
        self.assertEqual(ctx.exception.code, "missing")

    def test_kaputte_datei(self):
        p = Path(self.dir) / "kaputt.png"
        p.write_bytes(b"keine png")
        with self.assertRaises(Tpf2HeightmapError) as ctx:
            load_tpf2_heightmap(p)
        self.assertEqual(ctx.exception.code, "read")


class RawToMetersTest(unittest.TestCase):
    def test_skala(self):
        raw = np.array([0, 65535, 32767], dtype=np.uint16)
        m = raw_to_meters(raw, 70.0, 250.0)
        self.assertAlmostEqual(float(m[0]), 70.0, places=3)
        self.assertAlmostEqual(float(m[1]), 250.0, places=3)
        self.assertAlmostEqual(float(m[2]), 160.0, delta=0.01)

    def test_falsche_skala(self):
        with self.assertRaises(Tpf2HeightmapError) as ctx:
            raw_to_meters(np.zeros(2, dtype=np.uint16), 100.0, 100.0)
        self.assertEqual(ctx.exception.code, "scale")


if __name__ == "__main__":
    unittest.main()
