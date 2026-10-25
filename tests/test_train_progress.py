import unittest

from src.gui.train_math import ease, fraction


class TrainMathTest(unittest.TestCase):

    def test_fraction_grenzen(self):
        self.assertEqual(fraction(0, 10), 0.0)
        self.assertEqual(fraction(5, 10), 0.5)
        self.assertEqual(fraction(12, 10), 1.0)
        self.assertEqual(fraction(-1, 10), 0.0)

    def test_fraction_ohne_total(self):
        self.assertEqual(fraction(3, 0), 0.0)
        self.assertEqual(fraction(3, None), 0.0)

    def test_ease_naehert_sich_an(self):
        value = 0.0
        for _ in range(200):
            value = ease(value, 1.0, 0.033)
        self.assertEqual(value, 1.0)

    def test_ease_ueberschiesst_nicht(self):
        value = 0.2
        for _ in range(50):
            value = ease(value, 0.6, 0.05)
            self.assertLessEqual(value, 0.6)
            self.assertGreaterEqual(value, 0.2)

    def test_ease_ohne_zeit_bleibt(self):
        self.assertEqual(ease(0.3, 0.9, 0.0), 0.3)

    def test_ease_rueckwaerts(self):
        self.assertLess(ease(0.9, 0.1, 0.1), 0.9)


if __name__ == "__main__":
    unittest.main()
