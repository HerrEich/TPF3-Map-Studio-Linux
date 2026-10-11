import re
import unittest

from src.heightmap import towns_export as te


def _places(count=20):
    return [
        te.Place(
            name="Ort%d" % i,
            kind="town",
            x=float(i),
            y=float(-i),
            population=1000 + i,
        )
        for i in range(count)
    ]


class RandomNeedsTest(unittest.TestCase):

    def test_default_is_random(self):
        self.assertEqual(te.DEFAULT_NEEDS_MODE, "random")
        self.assertIn("random", [key for key, _label in te.NEEDS_MODES])

    def test_same_seed_same_output(self):
        a = te.towns_lua(_places(), needs_mode="random", seed=42)
        b = te.towns_lua(_places(), needs_mode="random", seed=42)
        self.assertEqual(a, b)

    def test_different_seed_differs(self):
        a = te.towns_lua(_places(), needs_mode="random", seed=1)
        b = te.towns_lua(_places(), needs_mode="random", seed=2)
        self.assertNotEqual(a, b)

    def test_lua_braces_balanced_and_one_entry_per_town(self):
        text = te.towns_lua(_places(), needs_mode="random", seed=7)
        self.assertEqual(text.count("{"), text.count("}"))
        self.assertEqual(text.count("landUse2CargoNeedsCategories"), 20)

    def test_only_known_goods(self):
        text = te.towns_lua(_places(), needs_mode="random", seed=7)
        names = set(re.findall(r'\{ "([A-Za-z_]+)", ', text))
        allowed = {g for goods in te.RANDOM_GOODS.values() for g in goods}
        self.assertTrue(names)
        self.assertTrue(names <= allowed)

    def test_amounts_in_range(self):
        text = te.towns_lua(_places(), needs_mode="random", seed=7)
        amounts = [
            float(x)
            for x in re.findall(r'\{ "[A-Za-z_]+", ([0-9.]+) \}', text)
        ]
        low, high = te.RANDOM_AMOUNT_RANGE
        self.assertTrue(amounts)
        self.assertTrue(all(low <= a <= high for a in amounts))

    def test_example_mode_unchanged(self):
        text = te.towns_lua(_places(2), needs_mode="example")
        self.assertIn(te.DEFAULT_NEEDS, text)


if __name__ == "__main__":
    unittest.main()
