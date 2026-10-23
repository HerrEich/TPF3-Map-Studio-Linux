import base64
import unittest

import numpy as np

from src.heightmap.biome_mask import BIOME_NAMES, BIOME_PREVIEW_RGB
from src.heightmap.mesh3d import (
    EDITOR_MAX_M,
    EDITOR_MIN_M,
    biome_legend,
    build_mesh_payload,
    resample_index,
    resample_mask,
    scale_segments,
)


def _hoehen(maximum=400.0):
    x = np.linspace(0.0, 1.0, 60)
    X, Y = np.meshgrid(x, x)
    return (X + Y) / 2.0 * maximum + 10.0


class BiomeAufNetzTest(unittest.TestCase):

    def test_resample_index_groesse_und_typ(self):
        index = np.random.randint(0, 5, (120, 200))
        out = resample_index(index, 30, 50)
        self.assertEqual(out.shape, (30, 50))
        self.assertEqual(out.dtype, np.uint8)

    def test_resample_index_trifft_ecken(self):
        index = np.zeros((10, 10), dtype=int)
        index[0, 0] = 3
        index[-1, -1] = 4
        out = resample_index(index, 5, 5)
        self.assertEqual(out[0, 0], 3)
        self.assertEqual(out[-1, -1], 4)

    def test_resample_index_verlangt_2d(self):
        with self.assertRaises(ValueError):
            resample_index(np.zeros(5), 3, 3)

    def test_legende_nur_vorkommende_biome_mit_anteil(self):
        index = np.array([[1, 1, 1, 2]])
        legende = biome_legend(index, np.asarray(BIOME_PREVIEW_RGB), BIOME_NAMES)
        self.assertEqual([b["id"] for b in legende], [1, 2])
        self.assertAlmostEqual(legende[0]["pct"], 75.0)
        self.assertAlmostEqual(sum(b["pct"] for b in legende), 100.0)


class PayloadTest(unittest.TestCase):

    def _payload(self, **kw):
        return build_mesh_payload(_hoehen(kw.pop("maximum", 400.0)), 10.0, 330.0, 380.0, 16.0, **kw)

    def test_ohne_biome_keine_biomfelder(self):
        p = self._payload()
        self.assertNotIn("biome_colors_b64", p)
        self.assertNotIn("biomes", p)

    def test_mit_biomen_farben_in_netzgroesse(self):
        index = np.random.randint(0, 5, (30, 30))
        p = self._payload(biome_index=index, biome_palette=BIOME_PREVIEW_RGB, biome_names=BIOME_NAMES)
        farben = base64.b64decode(p["biome_colors_b64"])
        self.assertEqual(len(farben), p["rows"] * p["cols"] * 3)
        self.assertTrue(p["biomes"])

    def test_skalenwerte(self):
        p = self._payload()
        self.assertEqual(p["water_level_m"], 10.0)
        self.assertEqual(p["rock_above_m"], 330.0)
        self.assertEqual(p["snow_above_m"], 380.0)
        self.assertAlmostEqual(p["max_above_m"], 400.0, delta=0.5)
        self.assertEqual(p["editor_min_m"], EDITOR_MIN_M)
        self.assertEqual(p["editor_max_m"], EDITOR_MAX_M)

    def test_schneegrenze_nie_unter_felsgrenze(self):
        p = build_mesh_payload(_hoehen(), 0.0, 300.0, 100.0, 16.0)
        self.assertGreaterEqual(p["snow_above_m"], p["rock_above_m"])

    def test_absolute_hoehen_fuer_editorfenster(self):
        p = self._payload(maximum=4000.0)
        self.assertGreater(p["abs_max_m"], EDITOR_MAX_M)


class SkalenabschnitteTest(unittest.TestCase):

    def test_biome_nach_hoehe_gestapelt_dann_fels_und_schnee(self):
        h = np.linspace(0.0, 400.0, 4000).reshape(40, 100)
        index = np.digitize(h, [100, 200, 300]).astype(int)      # 0..3 nach Hoehe
        segs = scale_segments(h, 330.0, 380.0, index=index, palette=BIOME_PREVIEW_RGB, names=BIOME_NAMES)
        namen = [s["name"] for s in segs]
        self.assertEqual(namen[-1], "Schnee")
        self.assertIn("Fels", namen)
        farben = [tuple(s["rgb"]) for s in segs if s["name"] not in ("Fels", "Schnee")]
        self.assertEqual(farben[0], BIOME_PREVIEW_RGB[0])
        self.assertEqual(farben[-1], BIOME_PREVIEW_RGB[3])

    def test_wasser_unten_wenn_gelaende_unter_null(self):
        h = np.linspace(-10.0, 50.0, 600).reshape(20, 30)
        segs = scale_segments(h, 330.0, 380.0)
        self.assertEqual(segs[0]["name"], "Wasser")
        self.assertAlmostEqual(segs[0]["a"], -10.0, places=3)
        self.assertAlmostEqual(segs[0]["b"], 0.0, places=3)

    def test_nur_erreichter_bereich_ohne_fels_unter_der_grenze(self):
        h = np.linspace(0.0, 250.0, 1000).reshape(20, 50)
        segs = scale_segments(h, 330.0, 380.0)
        self.assertNotIn("Fels", [s["name"] for s in segs])
        self.assertAlmostEqual(segs[-1]["b"], 250.0, places=3)

    def test_payload_enthaelt_abschnitte(self):
        p = build_mesh_payload(_hoehen(), 10.0, 330.0, 380.0, 16.0)
        self.assertTrue(p["scale_segments"])


class WasserMaskeTest(unittest.TestCase):

    def test_schmaler_fluss_bleibt_beim_verkleinern_erhalten(self):
        mask = np.zeros((400, 400), dtype=bool)
        mask[200:203, :] = True                       # 3 Pixel breiter Fluss
        out = resample_mask(mask, 50, 50)
        self.assertTrue(out[25].all() or out[24].all())

    def test_ohne_wasser_nichts(self):
        out = resample_mask(np.zeros((100, 100), dtype=bool), 20, 20)
        self.assertFalse(out.any())

    def test_payload_mit_und_ohne_wasser(self):
        h = _hoehen()
        mask = np.zeros(h.shape, dtype=bool)
        mask[30, :] = True
        self.assertIn("water_b64", build_mesh_payload(h, 10.0, 330.0, 380.0, 16.0, water_mask=mask))
        self.assertNotIn("water_b64", build_mesh_payload(h, 10.0, 330.0, 380.0, 16.0))
        self.assertNotIn("water_b64", build_mesh_payload(h, 10.0, 330.0, 380.0, 16.0, water_mask=np.zeros(h.shape, bool)))


class VolleAufloesungTest(unittest.TestCase):

    def test_schmaler_gipfel_zaehlt_in_skala_und_grenzwarnung(self):
        h = np.full((2000, 2000), 100.0, dtype=np.float32)
        h[1001, 1001] = 3300.0        # ein einziger Pixel, im 512er-Netz nicht sicher dabei
        p = build_mesh_payload(h, 10.0, 330.0, 380.0, 4.0)
        self.assertAlmostEqual(p["abs_max_m"], 3300.0, places=1)
        self.assertAlmostEqual(p["max_above_m"], 3290.0, places=1)
        self.assertGreater(p["abs_max_m"], EDITOR_MAX_M)


if __name__ == "__main__":
    unittest.main()
