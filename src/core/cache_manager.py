"""Cache-Verwaltung: Groesse der Hoehendaten-Caches zeigen und leeren.

Ohne Qt, einzeln testbar. Geloescht wird nur INNERHALB der bekannten
Cache-Ordner; Logs, Einstellungen und Projekte liegen woanders und sind
nie betroffen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src.i18n import tr

# Muss zu den Konstanten DEFAULT_*_CACHE_DIR in src/gui/heightmap_dialog.py passen
# (ein Test prueft das).
CACHE_KEYS = (
    "dem_cache", "dgm1_cache", "swissalti3d_cache", "ahn_nl_cache", "bev_at_cache", "lux_mnt_cache", "osm_cache",
)


class CacheError(Exception):
    """Cache kann nicht geleert werden; der Text ist fuer Nutzer gedacht."""


@dataclass
class CacheInfo:
    key: str
    label: str
    path: Path
    files: int
    size_bytes: int


@dataclass
class ClearResult:
    deleted_files: int = 0
    freed_bytes: int = 0
    failed_files: int = 0
    skipped_links: int = 0


def cache_labels() -> dict:
    return {
        "dem_cache": tr("Copernicus (weltweit, 30 m)"),
        "dgm1_cache": tr("DGM1 Deutschland (1 m, \u00fcber hoehendaten.de)"),
        "osm_cache": tr("OpenStreetMap-Kacheln (Overpass)"),
        "ahn_nl_cache": tr("AHN Niederlande (2 m, über PDOK)"),
        "swissalti3d_cache": tr("swissALTI3D Schweiz (2 m, \u00fcber data.geo.admin.ch)"),
        "bev_at_cache": tr("BEV Österreich (1 m, über data.bev.gv.at)"),
        "lux_mnt_cache": tr("Luxemburg MNT 2024 (0,5 m, über data.public.lu)"),
    }


def default_app_dir() -> Path:
    # Erst hier importiert: app_paths kann beim Import den Ordner umbenennen.
    from src.app_paths import APP_DIR

    return APP_DIR


def format_size(size_bytes, comma: bool = False) -> str:
    size = max(0, int(size_bytes))

    if size < 1024:
        return "%d B" % size

    value = float(size)
    unit = "KB"

    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if round(value, 1) < 1024.0 or unit == "TB":
            break

    text = "%.1f %s" % (value, unit)

    return text.replace(".", ",") if comma else text


def folder_stats(path) -> tuple[int, int]:
    """(Anzahl Dateien, Gesamtgroesse in Bytes); Verknuepfungen werden nicht verfolgt."""

    files = 0
    size = 0
    stack = [str(path)]

    while stack:
        current = stack.pop()

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)

                        elif entry.is_file(follow_symlinks=False):
                            files += 1
                            size += entry.stat(follow_symlinks=False).st_size

                    except OSError:
                        continue

        except OSError:
            continue

    return files, size


def list_caches(app_dir=None) -> list[CacheInfo]:
    base = Path(app_dir) if app_dir is not None else default_app_dir()
    labels = cache_labels()

    result = []

    for key in CACHE_KEYS:
        path = base / key
        files, size = folder_stats(path)
        result.append(CacheInfo(key, labels[key], path, files, size))

    return result


def _cache_path(base: Path, key) -> Path:
    if key not in CACHE_KEYS:
        raise CacheError(
            tr("Unbekannter Cache: {name}").format(name=str(key)[:40])
        )

    path = base / key

    unsafe = tr(
        "Der Cache-Ordner ist eine Verkn\u00fcpfung oder liegt au\u00dferhalb des "
        "Studio-Verzeichnisses und wird nicht ge\u00e4ndert: {path}"
    ).format(path=path)

    if path.is_symlink():
        raise CacheError(unsafe)

    if path.exists():
        try:
            real = os.path.normcase(str(path.resolve(strict=True)))
            expected = os.path.normcase(str(base.resolve(strict=True) / key))
        except OSError:
            raise CacheError(unsafe)

        if real != expected:
            raise CacheError(unsafe)

    return path


def _delete_tree(directory: str, result: ClearResult) -> bool:
    """Loescht den Inhalt von directory; True, wenn danach nichts mehr darin liegt."""

    empty = True

    try:
        with os.scandir(directory) as iterator:
            entries = list(iterator)
    except OSError:
        result.failed_files += 1
        return False

    for entry in entries:

        try:
            if entry.is_symlink():
                result.skipped_links += 1
                empty = False
                continue

            if entry.is_dir(follow_symlinks=False):

                if _delete_tree(entry.path, result):
                    try:
                        os.rmdir(entry.path)
                    except OSError:
                        empty = False
                else:
                    empty = False

                continue

            size = entry.stat(follow_symlinks=False).st_size

        except OSError:
            result.failed_files += 1
            empty = False
            continue

        try:
            os.remove(entry.path)
        except OSError:
            result.failed_files += 1
            empty = False
        else:
            result.deleted_files += 1
            result.freed_bytes += size

    return empty


def clear_cache(key, app_dir=None) -> ClearResult:
    """Leert einen Cache-Ordner (der Ordner selbst bleibt bestehen)."""

    base = Path(app_dir) if app_dir is not None else default_app_dir()

    path = _cache_path(base, key)

    result = ClearResult()

    if not path.is_dir():
        return result

    _delete_tree(str(path), result)

    return result