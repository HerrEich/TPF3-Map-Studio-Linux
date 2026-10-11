import unittest
from pathlib import Path

from src.file_names import ascii_safe_name, ascii_safe_path


class AsciiSafeNameTest(unittest.TestCase):

    def test_plain_name_unchanged(self):
        self.assertEqual(ascii_safe_name("biome_osm-1.png"), "biome_osm-1.png")

    def test_umlauts(self):
        self.assertEqual(
            ascii_safe_name("biome_osm_Erstfeld-G\u00f6schenen.png"),
            "biome_osm_Erstfeld-Goeschenen.png",
        )
        self.assertEqual(
            ascii_safe_name("Gr\u00fcmpentalbr\u00fccke.png"),
            "Gruempentalbruecke.png",
        )
        self.assertEqual(ascii_safe_name("Stra\u00dfe.png"), "Strasse.png")
        self.assertEqual(ascii_safe_name("\u00c4\u00d6\u00dc.png"), "AeOeUe.png")

    def test_accents_and_symbols(self):
        self.assertEqual(ascii_safe_name("caf\u00e9.png"), "cafe.png")
        self.assertEqual(ascii_safe_name("a#b?c.png"), "a_b_c.png")

    def test_never_empty(self):
        self.assertTrue(ascii_safe_name("\u4e2d\u6587"))


class AsciiSafePathTest(unittest.TestCase):

    def test_only_file_name_changes(self):
        path, changed = ascii_safe_path(Path("/tmp/Bj\u00f6rn/g\u00f6.png"))
        self.assertTrue(changed)
        self.assertEqual(Path(path), Path("/tmp/Bj\u00f6rn/goe.png"))

    def test_plain_path_not_changed(self):
        path, changed = ascii_safe_path("/tmp/x/biome.png")
        self.assertFalse(changed)
        self.assertEqual(Path(path), Path("/tmp/x/biome.png"))


if __name__ == "__main__":
    unittest.main()
