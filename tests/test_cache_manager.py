import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.core import cache_manager as c


def make_files(folder, names_sizes):
    for name, size in names_sizes:
        path = Path(folder) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)


class FormatTests(unittest.TestCase):

    def test_bytes(self):
        self.assertEqual(c.format_size(0), "0 B")
        self.assertEqual(c.format_size(1023), "1023 B")
        self.assertEqual(c.format_size(-5), "0 B")

    def test_einheiten(self):
        self.assertEqual(c.format_size(1536), "1.5 KB")
        self.assertEqual(c.format_size(5 * 1024 * 1024), "5.0 MB")
        self.assertEqual(c.format_size(int(2.8 * 1024 ** 3)), "2.8 GB")
        self.assertEqual(c.format_size(3 * 1024 ** 4), "3.0 TB")

    def test_komma(self):
        self.assertEqual(c.format_size(1536, comma=True), "1,5 KB")

    def test_rundung_an_der_grenze(self):
        self.assertEqual(c.format_size(1024 * 1024 - 1), "1.0 MB")


class StatsTests(unittest.TestCase):

    def test_fehlender_ordner(self):
        path = Path(tempfile.gettempdir()) / "gibt_es_nicht_cache_test"
        self.assertEqual(c.folder_stats(path), (0, 0))

    def test_verschachtelt(self):
        with tempfile.TemporaryDirectory() as folder:
            make_files(folder, [("a.tif", 10), ("sub/b.tif", 20), ("sub/deep/c.tif", 30)])
            self.assertEqual(c.folder_stats(folder), (3, 60))


class ListTests(unittest.TestCase):

    def test_alle_eintraege_auch_ohne_ordner(self):
        with tempfile.TemporaryDirectory() as folder:
            infos = c.list_caches(folder)

        self.assertEqual([i.key for i in infos], list(c.CACHE_KEYS))
        self.assertTrue(all(i.files == 0 and i.size_bytes == 0 for i in infos))
        self.assertTrue(all(isinstance(i.label, str) and i.label for i in infos))

    def test_zaehlt_dateien_und_groesse(self):
        with tempfile.TemporaryDirectory() as folder:
            make_files(Path(folder) / "dem_cache", [("a.tif", 100), ("b.tif", 50)])
            infos = {i.key: i for i in c.list_caches(folder)}

        self.assertEqual(infos["dem_cache"].files, 2)
        self.assertEqual(infos["dem_cache"].size_bytes, 150)
        self.assertEqual(infos["dgm1_cache"].files, 0)


class ClearTests(unittest.TestCase):

    def test_leert_inhalt_und_behaelt_den_ordner(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            make_files(base / "dem_cache", [("a.tif", 100), ("sub/b.tif", 50)])
            make_files(base, [("logs/x.log", 7), ("dashboard_settings.json", 3)])

            result = c.clear_cache("dem_cache", base)

            self.assertEqual(result.deleted_files, 2)
            self.assertEqual(result.freed_bytes, 150)
            self.assertEqual(result.failed_files, 0)
            self.assertTrue((base / "dem_cache").is_dir())
            self.assertEqual(list((base / "dem_cache").iterdir()), [])
            self.assertTrue((base / "logs" / "x.log").is_file())
            self.assertTrue((base / "dashboard_settings.json").is_file())

    def test_andere_caches_bleiben(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            make_files(base / "dem_cache", [("a.tif", 10)])
            make_files(base / "dgm1_cache", [("b.tif", 10)])

            c.clear_cache("dem_cache", base)

            self.assertTrue((base / "dgm1_cache" / "b.tif").is_file())

    def test_unbekannter_schluessel(self):
        with tempfile.TemporaryDirectory() as folder:
            make_files(folder, [("logs/x.log", 7)])

            for key in ("logs", "../x", "", "dem_cache/..", None):
                with self.assertRaises(c.CacheError):
                    c.clear_cache(key, folder)

            self.assertTrue((Path(folder) / "logs" / "x.log").is_file())

    def test_fehlender_ordner(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(c.clear_cache("dem_cache", folder), c.ClearResult())

    def test_nicht_loeschbare_dateien_werden_gezaehlt(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            make_files(base / "dem_cache", [("a.tif", 10), ("b.tif", 10)])

            with mock.patch.object(c.os, "remove", side_effect=PermissionError("in use")):
                result = c.clear_cache("dem_cache", base)

            self.assertEqual(result.failed_files, 2)
            self.assertEqual(result.deleted_files, 0)
            self.assertEqual(c.folder_stats(base / "dem_cache"), (2, 20))

    def test_verknuepfter_cache_ordner_wird_abgelehnt(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder) / "app"
            outside = Path(folder) / "fremd"
            base.mkdir()
            make_files(outside, [("wichtig.txt", 5)])

            try:
                os.symlink(outside, base / "dem_cache", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks sind hier nicht erlaubt")

            with self.assertRaises(c.CacheError):
                c.clear_cache("dem_cache", base)

            self.assertTrue((outside / "wichtig.txt").is_file())

    def test_verknuepfung_im_cache_wird_nicht_verfolgt(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder) / "app"
            outside = Path(folder) / "fremd"
            make_files(outside, [("wichtig.txt", 5)])
            make_files(base / "dem_cache", [("a.tif", 10)])

            try:
                os.symlink(outside, base / "dem_cache" / "link", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks sind hier nicht erlaubt")

            result = c.clear_cache("dem_cache", base)

            self.assertEqual(result.skipped_links, 1)
            self.assertTrue((outside / "wichtig.txt").is_file())


class SourceTests(unittest.TestCase):

    def test_namen_passen_zum_heightmap_dialog(self):
        path = Path(__file__).resolve().parents[1] / "src" / "gui" / "heightmap_dialog.py"
        text = path.read_text(encoding="utf-8")

        for key in c.CACHE_KEYS:
            self.assertIn('APP_DIR / "%s"' % key, text)