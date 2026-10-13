import json
import os
import tempfile
import unittest

from src.core import recipe as r
from src.core.project.project import Project
from src.core.project_serializer import ProjectSerializer
from src.map.objects.selection import Selection


def band():
    return Selection.from_center(
        center_lat=50.1,
        center_lon=7.6,
        width_m=10752.0,
        height_m=53760.0,
        rotation_deg=12.5,
        margin_m=500.0,
        scale_factor=1.0,
    )


def raw_recipe(**changes):
    data = {
        "format": r.RECIPE_FORMAT,
        "version": r.RECIPE_VERSION,
        "name": "Rheintal",
        "description": "Test",
        "selection": {
            "min_lat": 50.0,
            "min_lon": 7.0,
            "max_lat": 50.5,
            "max_lon": 7.5,
        },
        "export_settings": {"smooth": True},
    }
    data.update(changes)
    return json.dumps(data)


def raw_with_selection(**changes):
    selection = {
        "min_lat": 50.0,
        "min_lon": 7.0,
        "max_lat": 50.5,
        "max_lon": 7.5,
    }
    selection.update(changes)
    return raw_recipe(selection=selection)


class SelectionTests(unittest.TestCase):

    def test_einfache_bbox_roundtrip(self):
        selection = Selection(50.0, 7.0, 50.5, 7.5)
        self.assertEqual(
            r.selection_from_dict(r.selection_to_dict(selection)), selection
        )

    def test_gedrehtes_band_roundtrip(self):
        selection = band()
        self.assertEqual(
            r.selection_from_dict(r.selection_to_dict(selection)), selection
        )

    def test_gestauchte_karte_roundtrip(self):
        selection = Selection.from_center(
            center_lat=50.1,
            center_lon=7.6,
            width_m=10752.0,
            height_m=53760.0,
            rotation_deg=3.0,
            margin_m=500.0,
            scale_factor=5.0,
        )
        loaded = r.selection_from_dict(r.selection_to_dict(selection))
        self.assertEqual(loaded, selection)
        self.assertTrue(loaded.is_scaled)

    def test_height_scale_fehlt_dann_kehrwert(self):
        recipe = r.parse_recipe(raw_with_selection(scale_factor=4.0))
        self.assertAlmostEqual(recipe.selection.height_scale, 0.25)

    def test_fehlender_pflichtwert(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_with_selection(min_lat=None))

    def test_wert_ausserhalb_des_bereichs(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_with_selection(max_lat=91.0))
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_with_selection(max_lon=181.0))

    def test_minimum_nicht_kleiner_als_maximum(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_with_selection(min_lat=50.5, max_lat=50.0))

    def test_bool_und_nan_werden_abgelehnt(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_with_selection(min_lat=True))
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_with_selection(min_lat=float("nan")))

    def test_band_nur_teilweise_angegeben(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_with_selection(width_m=1000.0))

    def test_drehung_ohne_band(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_with_selection(rotation_deg=10.0))

    def test_auswahl_fehlt(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_recipe(selection=None))


class RecipeTests(unittest.TestCase):

    def test_nur_erlaubte_felder(self):
        data = r.build_recipe("Name", "Text", band(), {"smooth": True})
        self.assertEqual(
            set(data),
            {"format", "version", "name", "description", "selection", "export_settings"},
        )

    def test_einstellungen_werden_bereinigt(self):
        data = r.build_recipe("x", "", band(), {"smooth": True, "evil": 1})
        self.assertEqual(data["export_settings"], {"smooth": True})

    def test_import_bereinigt_einstellungen(self):
        recipe = r.parse_recipe(
            raw_recipe(export_settings={"smooth": True, "evil": 5})
        )
        self.assertEqual(recipe.export_settings, {"smooth": True})

    def test_name_wird_einzeilig(self):
        data = r.build_recipe("Zeile1\nZeile2", "", band(), {})
        self.assertEqual(data["name"], "Zeile1 Zeile2")

    def test_kein_json(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe("das ist kein json")

    def test_falsches_format(self):
        with self.assertRaises(r.RecipeError):
            r.parse_recipe(raw_recipe(format="anderes"))
        with self.assertRaises(r.RecipeError):
            r.parse_recipe("[1, 2]")

    def test_falsche_version(self):
        for version in (2, 0, "1", True, None):
            with self.assertRaises(r.RecipeError):
                r.parse_recipe(raw_recipe(version=version))

    def test_datei_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a" + r.RECIPE_SUFFIX)
            data = r.build_recipe("Rhein", "Beschreibung", band(), {"smooth": True})
            r.write_recipe(path, data)
            recipe = r.read_recipe(path)

        self.assertEqual(recipe.name, "Rhein")
        self.assertEqual(recipe.description, "Beschreibung")
        self.assertEqual(recipe.selection, band())
        self.assertEqual(recipe.export_settings, {"smooth": True})

    def test_datei_mit_bom_wird_gelesen(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "bom.tpf3recipe")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(raw_recipe())
            self.assertEqual(r.read_recipe(path).name, "Rheintal")

    def test_zu_grosse_datei(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "gross.tpf3recipe")
            with open(path, "wb") as f:
                f.write(b" " * (r.MAX_FILE_BYTES + 1))
            with self.assertRaises(r.RecipeError):
                r.read_recipe(path)

    def test_datei_fehlt(self):
        with self.assertRaises(r.RecipeError):
            r.read_recipe(os.path.join(tempfile.gettempdir(), "gibt_es_nicht.tpf3recipe"))

    def test_projektdatei_aus_rezept(self):
        recipe = r.parse_recipe(
            raw_recipe(name="Mosel", description="Weinberge", export_settings={"smooth": True, "compress": 80})
        )

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "p.tpf2ms")
            r.project_file_from_recipe(recipe, path)

            loaded = Project()
            ProjectSerializer.load(path, loaded)

        self.assertEqual(loaded.name, "Mosel")
        self.assertEqual(loaded.description, "Weinberge")
        self.assertEqual(loaded.selection, recipe.selection)
        self.assertEqual(loaded.export_settings, {"smooth": True, "compress": 80.0})
        self.assertEqual(loaded.markers, [])
        self.assertEqual(loaded.node_count, 0)
        self.assertEqual(loaded.heightmap_export_path, "")


class FileStemTests(unittest.TestCase):

    def test_ungueltige_zeichen(self):
        self.assertEqual(r.safe_file_stem('a<b>:c"d/e\\f|g?h*'), "a_b__c_d_e_f_g_h_")

    def test_leer_ergibt_standardnamen(self):
        for name in ("", None, "  ..  "):
            self.assertEqual(r.safe_file_stem(name), "kartenrezept")

    def test_laenge_begrenzt(self):
        self.assertLessEqual(len(r.safe_file_stem("a" * 200)), 60)