import unittest

import numpy as np

from src.heightmap.water_lake_lowering import lake_drop_field, lower_terrain_around_lakes

PIXEL = 4.0


def _karte():
    """Flaches Land 100 m, ein See (Mitte) bei 150 m, ein Berg weit weg."""
    h = np.full((600, 600), 100.0, dtype=np.float32)
    mask = np.zeros(h.shape, dtype=bool)
    yy, xx = np.ogrid[:600, :600]
    lake = (yy - 300) ** 2 + (xx - 300) ** 2 < 40 ** 2     # 160 m Radius
    h[lake] = 150.0
    mask[lake] = True
    h[:60, :60] = 400.0                                    # ferner Berg
    return h, mask


class LakeLoweringTest(unittest.TestCase):
    def test_see_liegt_danach_auf_wasserspiegel(self):
        h, mask = _karte()
        out = lower_terrain_around_lakes(h, mask, 100.0, PIXEL, falloff_m=600.0)
        self.assertAlmostEqual(float(out[300, 300]), 100.0, delta=0.5)

    def test_weit_entfernt_unveraendert(self):
        h, mask = _karte()
        out = lower_terrain_around_lakes(h, mask, 100.0, PIXEL, falloff_m=300.0)
        self.assertEqual(float(out[10, 10]), 400.0)
        self.assertEqual(float(out[580, 580]), 100.0)

    def test_neigung_der_absenkung_ist_begrenzt(self):
        h, mask = _karte()
        drop = lake_drop_field(h, mask, 100.0, PIXEL, falloff_m=800.0)
        gy, gx = np.gradient(drop, PIXEL)
        steil = float(np.hypot(gx, gy).max())
        # smoothstep: Spitzenneigung 1,5 x drop / falloff = 1,5 x 50 / 800 ~ 0,094
        self.assertLess(steil, 0.12)

    def test_nichts_zu_tun_ohne_hohe_seen(self):
        h, mask = _karte()
        out = lower_terrain_around_lakes(h, mask, 150.0, PIXEL)
        np.testing.assert_array_equal(out, h)

    def test_kleine_gewaesser_zaehlen_nicht(self):
        h = np.full((200, 200), 100.0, dtype=np.float32)
        mask = np.zeros(h.shape, dtype=bool)
        h[100:104, 100:104] = 160.0
        mask[100:104, 100:104] = True
        self.assertIsNone(lake_drop_field(h, mask, 100.0, PIXEL))

    def test_max_drop_kappt(self):
        h, mask = _karte()
        out = lower_terrain_around_lakes(h, mask, 100.0, PIXEL, falloff_m=600.0, max_drop_m=20.0)
        self.assertAlmostEqual(float(out[300, 300]), 130.0, delta=0.5)

    def test_form_stimmt_nicht(self):
        with self.assertRaises(ValueError):
            lake_drop_field(np.zeros((4, 4), np.float32), np.zeros((5, 5), bool), 0.0, 4.0)

    def test_eingabe_bleibt_unveraendert(self):
        h, mask = _karte()
        kopie = h.copy()
        lower_terrain_around_lakes(h, mask, 100.0, PIXEL)
        np.testing.assert_array_equal(h, kopie)


if __name__ == "__main__":
    unittest.main()
