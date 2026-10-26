import unittest

import numpy as np

from src.heightmap.scale_info import scale_info
from src.heightmap.water_check import check_water
from src.i18n import translate_to


class ScaleInfoTest(unittest.TestCase):

    def test_faktor_15(self):
        info = scale_info(15.0, 1 / 15)
        self.assertAlmostEqual(info.real_m_per_pixel, 60.0)
        # Fluss wird nicht mitgestaucht: immer 3 Pixel = 12 m im Spiel
        self.assertAlmostEqual(info.river_width_game_m, 12.0)
        self.assertAlmostEqual(info.river_width_real_m, 180.0)
        self.assertAlmostEqual(info.height_example_game_m, 1000 / 15, places=3)

    def test_faktor_1(self):
        info = scale_info(1.0, 1.0)
        self.assertAlmostEqual(info.real_m_per_pixel, 4.0)
        self.assertAlmostEqual(info.height_example_game_m, 1000.0)

    def test_ungueltiger_faktor_bricht_nicht(self):
        self.assertGreater(scale_info(0, 1.0).real_m_per_pixel, 0)


class WaterCheckTest(unittest.TestCase):

    def test_anteil_ueber_grenze(self):
        heights = np.array([[0, 1, 2, 50], [0, 0, 80, 90]], dtype=np.float32)
        mask = np.ones_like(heights, dtype=bool)
        r = check_water(heights, mask, 0.0, 15.0)
        self.assertEqual(r.water_px, 8)
        self.assertEqual(r.high_px, 3)
        self.assertAlmostEqual(r.high_share, 3 / 8)
        self.assertEqual(r.active_px, 5)

    def test_absenkung(self):
        heights = np.array([[0, 2, 4, 6]], dtype=np.float32)
        mask = np.ones_like(heights, dtype=bool)
        r = check_water(heights, mask, 0.0, 100.0)
        self.assertAlmostEqual(r.mean_cut_m, 3.0)
        self.assertLessEqual(r.p95_cut_m, 6.0)
        self.assertGreater(r.p95_cut_m, 5.0)

    def test_maske_nur_teilweise(self):
        heights = np.array([[0, 100], [0, 100]], dtype=np.float32)
        mask = np.array([[True, False], [True, False]])
        r = check_water(heights, mask, 0.0, 15.0)
        self.assertEqual(r.water_px, 2)
        self.assertEqual(r.high_px, 0)

    def test_ohne_wasser_oder_falsche_form(self):
        heights = np.zeros((2, 2), dtype=np.float32)
        self.assertIsNone(check_water(heights, np.zeros((2, 2), bool), 0.0, 5.0))
        self.assertIsNone(check_water(heights, np.ones((3, 3), bool), 0.0, 5.0))
        self.assertIsNone(check_water(None, np.ones((2, 2), bool), 0.0, 5.0))

    def test_alles_zu_hoch(self):
        heights = np.full((2, 2), 500.0, dtype=np.float32)
        r = check_water(heights, np.ones((2, 2), bool), 0.0, 15.0)
        self.assertEqual(r.active_px, 0)
        self.assertEqual(r.mean_cut_m, 0.0)
        self.assertAlmostEqual(r.high_share, 1.0)


class EnglishTextsTest(unittest.TestCase):

    def test_neue_texte_haben_englisch(self):
        keys = [
            "Wasser-Check: {share:.0f} % der Gewässerfläche liegt höher als {rise:.0f} m über dem Wasserspiegel und bleibt unverändert (dort entsteht kein Wasser). Die übrigen Gewässer werden im Mittel um {mean:.0f} m abgesenkt, höchstens um etwa {p95:.0f} m.",
            "Über die Hälfte liegt zu hoch: Die Grenze „Nur Gewässer bis“ erhöhen oder den Wasserspiegel prüfen.",
        ]
        for k in keys:
            self.assertNotEqual(translate_to(k, "en"), k)

    def test_rechteck_hinweis_im_quelltext_hat_katalogeintrag(self):
        # Der Hinweis im Rechteck-Dialog wird aus Teilstuecken zusammengesetzt.
        text = (
            "1 Pixel der Höhenkarte = 4 m im Spiel = {real:.0f} m echtes "
            "Gelände. Flüsse und Kanäle werden immer {river:.0f} m breit "
            "gezeichnet (nicht mitgestaucht); Bäche und Gräben werden nicht "
            "als Wasser gezeichnet. {ex_real:.0f} m echte Höhe werden zu {ex_game:.0f} m."
        )
        self.assertNotEqual(translate_to(text, "en"), text)


if __name__ == "__main__":
    unittest.main()
