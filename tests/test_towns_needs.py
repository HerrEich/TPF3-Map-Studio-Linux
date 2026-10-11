import unittest

from src.heightmap import towns_export as te


def _places():
    return [
        te.Place("Altstadt", "town", 10.0, 20.0, 5000),
        te.Place("Dorf", "village", -5.0, 7.5, 300),
    ]


class NeedsModeTest(unittest.TestCase):

    def test_example_mode_writes_example_value(self):
        text = te.towns_lua(_places(), needs_mode="example")
        self.assertEqual(text.count("landUse2CargoNeedsCategories"), 2)
        self.assertEqual(text.count('"fish"'), 2)

    def test_default_writes_one_needs_line_per_town(self):
        text = te.towns_lua(_places())
        self.assertEqual(text.count("landUse2CargoNeedsCategories"), 2)

    def test_random_equals_default(self):
        self.assertEqual(
            te.towns_lua(_places(), seed=1),
            te.towns_lua(_places(), needs_mode="random", seed=1),
        )

    def test_omit_has_no_needs_line(self):
        text = te.towns_lua(_places(), needs_mode="omit")
        self.assertNotIn("landUse2CargoNeedsCategories", text)
        self.assertNotIn("fish", text)
        self.assertEqual(text.count("sizeFactors"), 2)
        self.assertIn('name = "Altstadt"', text)

    def test_empty_has_empty_table(self):
        text = te.towns_lua(_places(), needs_mode="empty")
        self.assertEqual(text.count("landUse2CargoNeedsCategories = {},"), 2)
        self.assertNotIn("fish", text)

    def test_braces_balanced_in_all_modes(self):
        for key, _label in te.NEEDS_MODES:
            text = te.towns_lua(_places(), needs_mode=key)
            self.assertEqual(text.count("{"), text.count("}"), key)


if __name__ == "__main__":
    unittest.main()
