import re
import unittest

from src.heightmap import towns_export as te


def _places(count=60):
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


def _need_lines(text):
    return [
        line for line in text.splitlines()
        if "landUse2CargoNeedsCategories" in line
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
        self.assertEqual(len(_need_lines(text)), 60)

    def test_goods_per_row_within_limits(self):
        text = te.towns_lua(_places(), needs_mode="random", seed=7)
        for line in _need_lines(text):
            com, ind = line.split(", ind = ")
            for part in (com, ind):
                count = part.count('{ "')
                self.assertGreaterEqual(count, te.RANDOM_MIN_GOODS)
                self.assertLessEqual(count, te.RANDOM_MAX_GOODS)

    def test_goods_come_from_pool_without_late(self):
        text = te.towns_lua(_places(), needs_mode="random", seed=7)
        names = set(re.findall(r'\{ "([A-Za-z_]+)", ', text))
        early = {g for goods in te.RANDOM_GOODS.values() for g in goods}
        late = {g for goods in te.RANDOM_LATE_GOODS.values() for g in goods}
        self.assertTrue(names)
        self.assertTrue(names <= early)
        self.assertFalse(names & late)

    def test_late_goods_only_with_flag(self):
        text = te.towns_lua(
            _places(), needs_mode="random", seed=7, include_late=True
        )
        names = set(re.findall(r'\{ "([A-Za-z_]+)", ', text))
        early = {g for goods in te.RANDOM_GOODS.values() for g in goods}
        late = {g for goods in te.RANDOM_LATE_GOODS.values() for g in goods}
        self.assertTrue(names <= early | late)
        self.assertTrue(names & late)

    def test_no_duplicate_goods_in_one_town(self):
        text = te.towns_lua(
            _places(), needs_mode="random", seed=3, include_late=True
        )
        for line in _need_lines(text):
            names = re.findall(r'\{ "([A-Za-z_]+)", ', line)
            self.assertEqual(len(names), len(set(names)))

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
