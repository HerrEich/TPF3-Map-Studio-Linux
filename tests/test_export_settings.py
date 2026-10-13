import json
import os
import tempfile
import unittest

from src.core.export_settings import sanitize_export_settings
from src.core.project.project import Project
from src.core.project_serializer import ProjectSerializer


class SanitizeTests(unittest.TestCase):

    def test_kein_dict_ergibt_leer(self):
        for raw in (None, "x", 5, [], [1]):
            self.assertEqual(sanitize_export_settings(raw), {})

    def test_gueltige_werte_bleiben(self):
        raw = {"source": "x", "smooth": True, "compress": 80, "clip_mode": "top"}
        self.assertEqual(
            sanitize_export_settings(raw),
            {"source": "x", "smooth": True, "compress": 80.0, "clip_mode": "top"},
        )

    def test_falsche_typen_fliegen_raus(self):
        raw = {
            "smooth": 1,
            "flatten": "ja",
            "compress": "5",
            "rock": True,
            "water_level": float("nan"),
            "clip_mode": "quer",
            "source": "",
        }
        self.assertEqual(sanitize_export_settings(raw), {})

    def test_unbekannte_schluessel_werden_ignoriert(self):
        self.assertEqual(sanitize_export_settings({"zukunft": 1}), {})


class ProjectFileTests(unittest.TestCase):

    def test_roundtrip_version_3(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "p.tpf2ms")
            project = Project()
            project.set_export_settings({"smooth": True, "compress": 80})
            ProjectSerializer.save(project, path)

            loaded = Project()
            ProjectSerializer.load(path, loaded)

        self.assertEqual(
            loaded.export_settings, {"smooth": True, "compress": 80.0}
        )

    def test_alte_version_2_laedt_weiter(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "alt.tpf2ms")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": 2, "project": {"name": "alt"}}, f)

            loaded = Project()
            ProjectSerializer.load(path, loaded)

        self.assertEqual(loaded.export_settings, {})

    def test_unbekannte_version_wird_abgelehnt(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "neu.tpf2ms")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": 99}, f)

            with self.assertRaises(ValueError):
                ProjectSerializer.load(path, Project())

    def test_nur_echte_aenderung_macht_projekt_dirty(self):
        project = Project()
        project.set_export_settings({})
        self.assertFalse(project.dirty)

        project.set_export_settings({"smooth": True})
        self.assertTrue(project.dirty)