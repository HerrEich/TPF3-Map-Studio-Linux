import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import app_paths


class ResolveAppDirTest(unittest.TestCase):

    def test_legacy_is_renamed_with_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            legacy = home / ".tpf2_map_studio" / "dem_cache"
            legacy.mkdir(parents=True)
            (legacy / "kachel.tif").write_bytes(b"abc")

            result = app_paths.resolve_app_dir(home)

            self.assertEqual(result, home / ".tpf3_map_studio")
            self.assertTrue((result / "dem_cache" / "kachel.tif").is_file())
            self.assertFalse((home / ".tpf2_map_studio").exists())

    def test_new_dir_wins_and_legacy_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".tpf3_map_studio").mkdir()
            (home / ".tpf2_map_studio").mkdir()

            result = app_paths.resolve_app_dir(home)

            self.assertEqual(result, home / ".tpf3_map_studio")
            self.assertTrue((home / ".tpf2_map_studio").exists())

    def test_nothing_exists_returns_new_without_creating(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            result = app_paths.resolve_app_dir(home)

            self.assertEqual(result, home / ".tpf3_map_studio")
            self.assertFalse(result.exists())

    def test_rename_failure_keeps_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".tpf2_map_studio").mkdir()

            with mock.patch.object(Path, "rename", side_effect=OSError("gesperrt")):
                result = app_paths.resolve_app_dir(home)

            self.assertEqual(result, home / ".tpf2_map_studio")
            self.assertTrue(result.exists())


if __name__ == "__main__":
    unittest.main()
