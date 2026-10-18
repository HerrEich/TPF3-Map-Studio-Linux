import unittest

from src.gui import zoom_math as zm

PW, PH = 2689, 13441
W, H = 300, 400


class ZoomMathTest(unittest.TestCase):
    def test_zoom1_ganzes_bild_mittig(self):
        src, dst = zm.visible_rects(PW, PH, W, H, 1.0, PW / 2, PH / 2)
        self.assertAlmostEqual(src[2], PW, places=3)
        self.assertAlmostEqual(src[3], PH, places=3)
        # schmales Bild: Rand links/rechts leer, Hoehe ganz genutzt
        self.assertAlmostEqual(dst[1], 0.0, places=3)
        self.assertAlmostEqual(dst[3], H, places=3)
        self.assertAlmostEqual(dst[0] + dst[2] / 2, W / 2, places=3)

    def test_punkt_unter_der_maus_bleibt(self):
        z, cx, cy = 1.0, PW / 2, PH / 2
        mx, my = 200.0, 100.0
        s0 = zm.scale_for(PW, PH, W, H, z)
        before = (cx + (mx - W / 2) / s0, cy + (my - H / 2) / s0)
        z, cx, cy = zm.zoom_at(PW, PH, W, H, z, cx, cy, 4.0, mx, my)
        s1 = zm.scale_for(PW, PH, W, H, z)
        after = (cx + (mx - W / 2) / s1, cy + (my - H / 2) / s1)
        self.assertGreater(z, 1.0)
        self.assertAlmostEqual(before[1], after[1], places=3)

    def test_grenzen(self):
        z, cx, cy = zm.zoom_at(PW, PH, W, H, 1.0, PW / 2, PH / 2, 0.1, 0, 0)
        self.assertEqual(z, 1.0)
        z, cx, cy = zm.zoom_at(PW, PH, W, H, 1.0, PW / 2, PH / 2, 1e9, 0, 0)
        self.assertEqual(z, zm.MAX_ZOOM)

    def test_kein_leerer_rand_beim_ziehen(self):
        z = 8.0
        cx, cy = zm.pan(PW, PH, W, H, z, PW / 2, PH / 2, -1e7, -1e7)
        src, dst = zm.visible_rects(PW, PH, W, H, z, cx, cy)
        self.assertLessEqual(src[0] + src[2], PW + 1e-6)
        self.assertLessEqual(src[1] + src[3], PH + 1e-6)
        cx, cy = zm.pan(PW, PH, W, H, z, cx, cy, 1e7, 1e7)
        src, dst = zm.visible_rects(PW, PH, W, H, z, cx, cy)
        self.assertGreaterEqual(src[0], 0.0)
        self.assertGreaterEqual(src[1], 0.0)

    def test_zoom_zeigt_kleineren_ausschnitt(self):
        s1, _ = zm.visible_rects(PW, PH, W, H, 1.0, PW / 2, PH / 2)
        s4, _ = zm.visible_rects(PW, PH, W, H, 4.0, PW / 2, PH / 2)
        self.assertAlmostEqual(s4[3], s1[3] / 4, places=3)

    def test_quadratisches_bild(self):
        src, dst = zm.visible_rects(100, 100, 200, 100, 1.0, 50, 50)
        self.assertAlmostEqual(dst[2], 100.0, places=3)
        self.assertAlmostEqual(dst[0], 50.0, places=3)


if __name__ == "__main__":
    unittest.main()
