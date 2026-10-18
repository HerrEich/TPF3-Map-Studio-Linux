import unittest

from src import help_content as hc


class HelpContentTest(unittest.TestCase):

    def setUp(self):
        self.pages = hc.load_index("de")
        self.flat = hc.flatten(self.pages)

    def test_ids_unique_and_files_exist(self):
        ids = [p.id for p in self.flat]
        self.assertEqual(len(ids), len(set(ids)))
        for page in self.flat:
            text = hc.read_page(page, "de")
            self.assertTrue(text.startswith("# "), page.id)

    def test_all_help_links_resolve(self):
        ids = {p.id for p in self.flat}
        for page in self.flat:
            for target in hc.linked_ids(hc.read_page(page, "de")):
                self.assertIn(target, ids, page.id)

    def test_unknown_language_falls_back_to_german(self):
        self.assertEqual([p.id for p in hc.load_index("fr")],
                         [p.id for p in self.pages])

    def test_search(self):
        hits = [p.id for p in hc.search(self.pages, "BEV Österreich")]
        self.assertIn("oesterreich-bev", hits)
        self.assertEqual(len(hc.search(self.pages, "")), len(self.flat))
        self.assertEqual(hc.search(self.pages, "xyzzy-nicht-vorhanden"), [])

    def test_find_page(self):
        self.assertEqual(hc.find_page(self.pages, "hoehenfenster").id, "hoehenfenster")
        self.assertIsNone(hc.find_page(self.pages, "gibtsnicht"))


if __name__ == "__main__":
    unittest.main()
