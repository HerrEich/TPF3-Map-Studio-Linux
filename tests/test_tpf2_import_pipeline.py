import unittest

import numpy as np

from src.heightmap.tpf2_heightmap_import import raw_to_meters
from src.heightmap.tpf2_import_pipeline import (
    ImportSettings,
    ImportSettingsError,
    default_output_name,
    run_import,
    validate_settings,
    water_preview_rgb,
    water_raw,
)


def _karte() -> np.ndarray:
    """0..100 m: See (20 m) in flacher Ebene knapp ueber Wasser (50,5 m),
    dazu ein Huegel bis 90 m."""
    m = np.full((80, 80), 50.5, dtype=np.float32)
    m[20:50, 20:50] = 20.0
    m[60:75, 60:75] = 90.0
    return np.rint(m / 100.0 * 65535).astype(np.uint16)


class ValidateTest(unittest.TestCase):
    def test_gueltig(self):
        validate_settings(ImportSettings(0, 100, 50))

    def test_reihenfolge(self):
        with self.assertRaises(ImportSettingsError) as ctx:
            validate_settings(ImportSettings(100, 100, 100))
        self.assertEqual(ctx.exception.code, "order")

    def test_tpf3_grenzen(self):
        with self.assertRaises(ImportSettingsError) as ctx:
            validate_settings(ImportSettings(-50, 100, 0))
        self.assertEqual(ctx.exception.code, "limits")
        with self.assertRaises(ImportSettingsError):
            validate_settings(ImportSettings(0, 4000, 10))

    def test_wasser_ausserhalb(self):
        with self.assertRaises(ImportSettingsError) as ctx:
            validate_settings(ImportSettings(0, 100, 120))
        self.assertEqual(ctx.exception.code, "water")

    def test_baender_werden_geprueft(self):
        with self.assertRaises(ValueError):
            validate_settings(ImportSettings(0, 100, 50, bands=((0.5, 0),)))


class WaterRawTest(unittest.TestCase):
    def test_kein_wasser_auf_min(self):
        self.assertIsNone(water_raw(ImportSettings(0, 100, 0)))

    def test_umrechnung(self):
        self.assertAlmostEqual(water_raw(ImportSettings(0, 100, 50)), 32767.5)


class RunImportTest(unittest.TestCase):
    def test_mit_bereinigung(self):
        res = run_import(_karte(), ImportSettings(0, 100, 50, margin_m=1.5))
        m = raw_to_meters(res.raw, 0, 100)
        self.assertIsNotNone(res.cleanup)
        self.assertGreaterEqual(float(m[0, 0]), 51.4)          # Ebene angehoben
        self.assertTrue((m[25:45, 25:45] < 50).all())          # See bleibt
        self.assertTrue((res.biome_index[25:45, 25:45] == 0).all())
        self.assertAlmostEqual(res.flooded_share, 900 / 6400, delta=0.01)

    def test_ohne_bereinigung_unveraendert(self):
        raw = _karte()
        res = run_import(raw, ImportSettings(0, 100, 50, cleanup=False))
        self.assertIsNone(res.cleanup)
        self.assertTrue((res.raw == raw).all())

    def test_wasser_auf_min_kein_wasser(self):
        res = run_import(_karte(), ImportSettings(0, 100, 0))
        self.assertIsNone(res.cleanup)
        self.assertEqual(res.flooded_share, 0.0)

    def test_wasser_biom(self):
        res = run_import(_karte(), ImportSettings(0, 100, 50, water_biome=3))
        self.assertTrue((res.biome_index[25:45, 25:45] == 3).all())
        self.assertFalse((res.biome_index[0:10, 0:10] == 3).any())


class PreviewTest(unittest.TestCase):
    def test_form_und_wasserfarbe(self):
        rgb = water_preview_rgb(_karte(), ImportSettings(0, 100, 50), step=4)
        self.assertEqual(rgb.shape, (20, 20, 3))
        self.assertEqual(rgb.dtype, np.uint8)
        self.assertEqual(tuple(rgb[8, 8]), (40, 110, 220))
        self.assertNotEqual(tuple(rgb[0, 0]), (40, 110, 220))


class NameTest(unittest.TestCase):
    def test_name(self):
        from pathlib import Path
        self.assertEqual(default_output_name(Path("ordner") / "meine_karte.png", "tpf3"),
                         "meine_karte_tpf3.png")


if __name__ == "__main__":
    unittest.main()
