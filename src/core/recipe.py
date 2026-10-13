"""Kartenrezept: gedrehtes Gebiet plus Export-Einstellungen als kleine Datei.

Ohne Qt, einzeln testbar. Ein Rezept enthaelt bewusst keine OSM-Daten,
keine Marker, keine Pfade und keinen Autor.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass

from src.core.export_settings import sanitize_export_settings
from src.core.project.project import Project
from src.core.project_serializer import ProjectSerializer
from src.i18n import tr
from src.map.objects.selection import Selection

RECIPE_FORMAT = "tpf3-map-recipe"
RECIPE_VERSION = 1
SUPPORTED_VERSIONS = (1,)
RECIPE_SUFFIX = ".tpf3recipe"

MAX_FILE_BYTES = 1_000_000
MAX_NAME_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 4000


class RecipeError(ValueError):
    """Rezept nicht lesbar oder ungueltig; der Text ist fuer Nutzer gedacht."""


@dataclass
class Recipe:
    name: str
    description: str
    selection: Selection
    export_settings: dict


# ---------------------------------------------------------------- Hilfen

def _text(value, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = "".join(ch for ch in value if ch == "\n" or ch >= " ")
    return cleaned.strip()[:limit]


def _single_line(value, limit: int) -> str:
    return " ".join(_text(value, limit).split())


def _number(raw: dict, key: str, low: float, high: float, required: bool = False):
    value = raw.get(key)

    if value is None:
        if required:
            raise RecipeError(
                tr("Im Kartenrezept fehlt der Wert '{key}'.").format(key=key)
            )
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not (low <= value <= high)
    ):
        raise RecipeError(
            tr("Im Kartenrezept ist der Wert '{key}' ung\u00fcltig.").format(key=key)
        )

    return float(value)


_INVALID_FILE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_file_stem(name, default: str = "kartenrezept") -> str:
    stem = _INVALID_FILE_CHARS.sub("_", name or "").strip(" .")
    return stem[:60].strip(" .") or default


# ------------------------------------------------------------- Auswahl

def selection_to_dict(selection) -> dict:
    return {
        "min_lat": selection.min_lat,
        "min_lon": selection.min_lon,
        "max_lat": selection.max_lat,
        "max_lon": selection.max_lon,
        "rotation_deg": selection.rotation_deg,
        "width_m": selection.width_m,
        "height_m": selection.height_m,
        "center_lat": selection.center_lat,
        "center_lon": selection.center_lon,
        "scale_factor": getattr(selection, "scale_factor", 1.0),
        "height_scale": getattr(selection, "height_scale", 1.0),
    }


def selection_from_dict(raw) -> Selection:
    if not isinstance(raw, dict):
        raise RecipeError(tr("Das Gebiet im Kartenrezept fehlt (selection)."))

    min_lat = _number(raw, "min_lat", -90.0, 90.0, True)
    max_lat = _number(raw, "max_lat", -90.0, 90.0, True)
    min_lon = _number(raw, "min_lon", -180.0, 180.0, True)
    max_lon = _number(raw, "max_lon", -180.0, 180.0, True)

    if min_lat >= max_lat or min_lon >= max_lon:
        raise RecipeError(
            tr("Das Gebiet im Kartenrezept ist ung\u00fcltig "
               "(Minimum nicht kleiner als Maximum).")
        )

    rotation = _number(raw, "rotation_deg", -360.0, 360.0) or 0.0
    width_m = _number(raw, "width_m", 1.0, 2_000_000.0)
    height_m = _number(raw, "height_m", 1.0, 2_000_000.0)
    center_lat = _number(raw, "center_lat", -90.0, 90.0)
    center_lon = _number(raw, "center_lon", -180.0, 180.0)

    band = (width_m, height_m, center_lat, center_lon)
    incomplete = any(v is not None for v in band) and any(v is None for v in band)

    if incomplete or (rotation and width_m is None):
        raise RecipeError(
            tr("Das Gebiet im Kartenrezept ist unvollst\u00e4ndig (Breite, H\u00f6he "
               "und Mittelpunkt geh\u00f6ren zusammen).")
        )

    scale_factor = _number(raw, "scale_factor", 0.01, 1000.0)
    if scale_factor is None:
        scale_factor = 1.0

    height_scale = _number(raw, "height_scale", 1e-6, 1000.0)
    if height_scale is None:
        height_scale = 1.0 / scale_factor

    return Selection(
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
        rotation_deg=rotation,
        width_m=width_m,
        height_m=height_m,
        center_lat=center_lat,
        center_lon=center_lon,
        scale_factor=scale_factor,
        height_scale=height_scale,
    )


# -------------------------------------------------------------- Rezept

def build_recipe(name, description, selection, export_settings) -> dict:
    return {
        "format": RECIPE_FORMAT,
        "version": RECIPE_VERSION,
        "name": _single_line(name, MAX_NAME_LENGTH),
        "description": _text(description, MAX_DESCRIPTION_LENGTH),
        "selection": selection_to_dict(selection),
        "export_settings": sanitize_export_settings(export_settings),
    }


def parse_recipe(text: str) -> Recipe:
    try:
        data = json.loads(text)
    except ValueError:
        raise RecipeError(
            tr("Die Datei ist kein lesbares Kartenrezept (kein g\u00fcltiges JSON).")
        )

    if not isinstance(data, dict) or data.get("format") != RECIPE_FORMAT:
        raise RecipeError(tr("Das ist kein Kartenrezept des TPF3-Map-Studios."))

    version = data.get("version")

    if isinstance(version, bool) or version not in SUPPORTED_VERSIONS:
        raise RecipeError(
            tr("Nicht unterst\u00fctzte Rezeptversion: {version}").format(version=version)
        )

    return Recipe(
        name=_single_line(data.get("name"), MAX_NAME_LENGTH),
        description=_text(data.get("description"), MAX_DESCRIPTION_LENGTH),
        selection=selection_from_dict(data.get("selection")),
        export_settings=sanitize_export_settings(data.get("export_settings")),
    )


def read_recipe(path: str) -> Recipe:
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            raise RecipeError(tr("Die Datei ist zu gro\u00df f\u00fcr ein Kartenrezept."))

        with open(path, "r", encoding="utf-8-sig") as f:
            text = f.read()

    except RecipeError:
        raise
    except (OSError, UnicodeDecodeError) as exc:
        raise RecipeError(
            tr("Die Datei konnte nicht gelesen werden: {error}").format(error=exc)
        )

    return parse_recipe(text)


def write_recipe(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")


# ------------------------------------------------- Rezept -> Projekt

def project_from_recipe(recipe: Recipe) -> Project:
    project = Project()

    if recipe.name:
        project.name = recipe.name

    project.description = recipe.description
    project.set_selection(recipe.selection)
    project.export_settings = dict(recipe.export_settings)

    return project


def project_file_from_recipe(recipe: Recipe, path: str):
    """Schreibt eine Projektdatei (ohne OSM und Marker) und prueft, dass sie ladbar ist."""

    ProjectSerializer.save(project_from_recipe(recipe), path)

    try:
        ProjectSerializer.load(path, Project())
    except Exception as exc:
        raise RecipeError(
            tr("Das Kartenrezept konnte nicht angewendet werden: {error}").format(
                error=exc
            )
        )