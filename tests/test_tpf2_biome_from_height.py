import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from src.heightmap.biome_mask import BIOME_GRAY
from src.heightmap.tpf2_biome_from_height import (
    DEFAULT_BANDS,
    BiomeBandError,
    biome_gray,
    biome_index_from_height,
    flooded_share,
    land_range,
    meters_to_raw,
    save_biome_mask,
    validate_bands,
    water_mask,
)


def _rampe(n: int = 1001) -> np.ndarray:
    """Eine Zeile mit gleichmaessig steigenden Werten 0..65535."""
    return np.linspace(0, 65535, n).round().astype(np.uint16).reshape(1, n)


class MetersToRawTest(unittest.TestCase):
    def test_umrechnung(self):
        self.assertAlmostEqual(meters_to_raw(70, 70, 250), 0.0)
        self.assertAlmostEqual(meters_to_raw(250, 70, 250), 65535.0)
        self.assertAlmostEqual(meters_to_raw(160, 70, 250), 32767.5)

    def test_falsche_skala(self):
        with self.assertRaises(BiomeBandError):
            meters_to_raw(10, 5, 5)


class WaterTest(unittest.TestCase):
    def test_maske(self):
        raw = np.array([[100, 200, 300]], dtype=np.uint16)
        self.assertEqual(water_mask(raw, 250).tolist(), [[True, True, False]])
        self.assertFalse(water_mask(raw, None).any())

    def test_anteil(self):
        raw = np.array([[100, 200, 300, 400]], dtype=np.uint16)
        self.assertAlmostEqual(flooded_share(raw, 250), 0.5)
        self.assertAlmostEqual(flooded_share(raw, None), 0.0)


class BandsTest(unittest.TestCase):
    def test_standard_gueltig(self):
        self.assertEqual(validate_bands(DEFAULT_BANDS), DEFAULT_BANDS)

    def test_nicht_aufsteigend(self):
        with self.assertRaises(BiomeBandError) as ctx:
            validate_bands([(0.7, 0), (0.3, 1), (1.0, 2)])
        self.assertEqual(ctx.exception.code, "order")

    def test_letzte_nicht_eins(self):
        with self.assertRaises(BiomeBandError) as ctx:
            validate_bands([(0.5, 0), (0.9, 1)])
        self.assertEqual(ctx.exception.code, "last")

    def test_biom_gibt_es_nicht(self):
        with self.assertRaises(BiomeBandError) as ctx:
            validate_bands([(1.0, 7)])
        self.assertEqual(ctx.exception.code, "biome")

    def test_leer(self):
        with self.assertRaises(BiomeBandError) as ctx:
            validate_bands([])
        self.assertEqual(ctx.exception.code, "empty")


class LandRangeTest(unittest.TestCase):
    def test_ausreisser_ignoriert(self):
        raw = np.full((1, 1000), 30000, dtype=np.uint16)
        raw[0, :500] = 20000
        raw[0, 0] = 65535          # einzelne Spitze
        lo, hi = land_range(raw)
        self.assertEqual(lo, 20000.0)
        self.assertEqual(hi, 30000.0)

    def test_wasser_hebt_untergrenze(self):
        raw = _rampe()
        lo, _ = land_range(raw, water_raw=10000)
        self.assertGreaterEqual(lo, 10000.0)

    def test_alles_geflutet(self):
        raw = np.full((2, 2), 100, dtype=np.uint16)
        lo, hi = land_range(raw, water_raw=60000)
        self.assertEqual(lo, hi)


class BiomeIndexTest(unittest.TestCase):
    def test_standard_baender_auf_rampe(self):
        idx = biome_index_from_height(_rampe())[0]
        n = idx.size
        self.assertEqual(int(idx[0]), 0)
        self.assertEqual(int(idx[n // 2]), 1)
        self.assertEqual(int(idx[-1]), 2)
        # grob 30 / 40 / 30 Prozent
        anteile = [float((idx == b).mean()) for b in (0, 1, 2)]
        self.assertAlmostEqual(anteile[0], 0.30, delta=0.02)
        self.assertAlmostEqual(anteile[1], 0.40, delta=0.02)
        self.assertAlmostEqual(anteile[2], 0.30, delta=0.02)

    def test_wasser_bekommt_wasser_biom(self):
        raw = _rampe()
        idx = biome_index_from_height(raw, water_raw=20000, water_biome=4)[0]
        self.assertTrue((idx[raw[0] < 20000] == 4).all())
        self.assertFalse((idx[raw[0] >= 20000] == 4).any())

    def test_flache_karte(self):
        raw = np.full((3, 3), 5000, dtype=np.uint16)
        idx = biome_index_from_height(raw)
        self.assertTrue((idx == 0).all())

    def test_eigene_baender(self):
        raw = _rampe()
        idx = biome_index_from_height(raw, bands=[(0.5, 3), (1.0, 4)])[0]
        self.assertEqual(int(idx[0]), 3)
        self.assertEqual(int(idx[-1]), 4)


class GrayTest(unittest.TestCase):
    def test_grauwerte(self):
        idx = np.array([[0, 1, 2, 3, 4]], dtype=np.uint8)
        self.assertEqual(biome_gray(idx).tolist(), [list(BIOME_GRAY)])

    def test_speichern_8bit(self):
        gray = biome_gray(np.array([[0, 4], [2, 1]], dtype=np.uint8))
        with tempfile.TemporaryDirectory() as d:
            p = save_biome_mask(Path(d) / "biom.png", gray)
            with Image.open(p) as im:
                self.assertEqual(im.mode, "L")
                self.assertEqual(np.array(im).tolist(), gray.tolist())


if __name__ == "__main__":
    unittest.main()
