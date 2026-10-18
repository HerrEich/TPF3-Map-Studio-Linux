"""
Automatischer Download von Copernicus-DEM-GLO-30-Höhenkacheln fuer eine
(ggf. gedrehte) Selection.

Findet selbststaendig heraus, welche 1°x1°-Kacheln die Selection (also
auch ein gedrehtes Kartenband) berührt, laedt sie bei Bedarf vom
oeffentlichen AWS-Bucket herunter (kein Account/Key noetig) und legt sie
in einem lokalen Cache ab.

Quelle: https://copernicus-dem-30m.s3.amazonaws.com/
"""

from __future__ import annotations

import math
import os
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests

from src.map.objects.selection import Selection
from src.i18n import tr

BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"

# Sicherheitsrand um den eigentlichen Kartenausschnitt herum, damit beim
# Drehen/Zuschneiden immer echte Nachbarpixel zur Verfuegung stehen.
MARGIN_DEG = 0.05


def _tile_id(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def required_tiles(selection: Selection) -> list[str]:
    """Liste der 1°x1°-Kachel-IDs, die den (ggf. gedrehten) Selection-Bereich abdecken."""
    corners = selection.corners_latlon()
    lats = [c[0] for c in corners]
    lons = [c[1] for c in corners]
    lat_min, lat_max = min(lats) - MARGIN_DEG, max(lats) + MARGIN_DEG
    lon_min, lon_max = min(lons) - MARGIN_DEG, max(lons) + MARGIN_DEG

    tiles = []
    for lat_floor in range(math.floor(lat_min), math.ceil(lat_max)):
        for lon_floor in range(math.floor(lon_min), math.ceil(lon_max)):
            tiles.append(_tile_id(lat_floor, lon_floor))
    return tiles


def download_tile(tile_id: str, cache_dir: Path, on_progress=None, should_cancel=None) -> Path:
    """Laedt eine Kachel herunter (falls noch nicht im Cache) und gibt den Pfad zurueck."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{tile_id}.tif"
    if dest.exists():
        return dest

    url = f"{BASE_URL}/{tile_id}/{tile_id}.tif"
    # Eindeutiger Name pro Thread: Downloads laufen im Hintergrund und
    # koennten sich sonst (z.B. nach erneutem Oeffnen des Dialogs) bei
    # derselben Kachel gegenseitig die .part-Datei ueberschreiben.
    tmp = dest.with_suffix(f".tif.{os.getpid()}-{threading.get_ident()}.part")
    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            if resp.status_code == 404:
                raise FileNotFoundError(
                    tr("Kachel {tile_id} existiert nicht bei Copernicus DEM (vermutlich reines Wassergebiet ohne Landkachel: {url})").format(tile_id=tile_id, url=url)
                )
            resp.raise_for_status()
            with open(tmp, "wb") as f:
                headers = getattr(resp, "headers", None) or {}
                size_text = headers.get("Content-Length")
                total = int(size_text) if isinstance(size_text, str) and size_text.isdigit() else None
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if should_cancel is not None and should_cancel():
                        raise DownloadCancelled()
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress is not None:
                        on_progress(downloaded, total)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def download_tiles_for_selection(selection: Selection, cache_dir: Path) -> list[Path]:
    """Bequemer Rundum-Aufruf: alle fuer die Selection noetigen Kacheln laden."""
    paths = []
    for tile_id in required_tiles(selection):
        try:
            paths.append(download_tile(tile_id, cache_dir))
        except FileNotFoundError:
            continue  # reine Wasserkachel ohne Landdaten - kein Fehler
    if not paths:
        raise RuntimeError(
            "Keine Copernicus-DEM-Kacheln fuer diesen Kartenausschnitt gefunden."
        )
    return paths


class DownloadCancelled(Exception):
    """Der Nutzer hat den Download abgebrochen."""


_TILE_LABEL = re.compile(r"_([NS]\d+)_00_([EW]\d+)_00_DEM$")


def tile_label(tile_id: str) -> str:
    """Kurzname einer Kachel fuer die Anzeige, z. B. N50 E007."""

    match = _TILE_LABEL.search(tile_id)

    return "%s %s" % match.groups() if match else tile_id


def missing_tiles(selection: Selection, cache_dir: Path) -> list[str]:
    """Kacheln, die fuer die Selection noch nicht im Cache liegen."""

    cache_dir = Path(cache_dir)

    return [
        tile_id
        for tile_id in required_tiles(selection)
        if not (cache_dir / f"{tile_id}.tif").exists()
    ]


class CopernicusFetchJob:
    """Laedt fehlende Copernicus-Kacheln in einem Hintergrund-Thread.

    Gleiche Schnittstelle wie Dgm1FetchJob und SwissFetchJob (done, total,
    text, finished, error, summary, start, cancel), damit Dgm1FetchDialog
    Fortschritt und Abbrechen anzeigen kann. Nach einem Abbruch steht in
    error "Abgebrochen.", dann liefert der Dialog False.
    """

    def __init__(self, selection, cache_dir, downloader=None):
        self.selection = selection
        self.cache_dir = Path(cache_dir)
        self._download = downloader or download_tile

        self.done = 0.0
        self.total = 0
        self.text = tr("Starte...")
        self.finished = False
        self.error = None
        self.summary = None

        self._cancel = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(
            target=self._run, name="copernicus-fetch", daemon=True
        )
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _progress_callback(self, index, count, tile_id):

        label = tile_label(tile_id)

        def callback(downloaded, total_bytes):

            done_mb = downloaded / 1048576.0

            if total_bytes:
                self.done = (index - 1) + min(1.0, downloaded / total_bytes)
                self.text = tr(
                    "Kachel {index} von {count}: {tile} "
                    "({done_mb:.0f} von {total_mb:.0f} MB)"
                ).format(
                    index=index,
                    count=count,
                    tile=label,
                    done_mb=done_mb,
                    total_mb=total_bytes / 1048576.0,
                )
            else:
                self.text = tr(
                    "Kachel {index} von {count}: {tile} ({done_mb:.0f} MB)"
                ).format(
                    index=index,
                    count=count,
                    tile=label,
                    done_mb=done_mb,
                )

        return callback

    def _run(self):

        loaded = 0

        try:

            todo = missing_tiles(self.selection, self.cache_dir)

            self.total = len(todo)

            for index, tile_id in enumerate(todo, start=1):

                if self._cancel.is_set():
                    raise DownloadCancelled()

                self.done = float(index - 1)

                self.text = tr("Kachel {index} von {count}: {tile}").format(
                    index=index,
                    count=len(todo),
                    tile=tile_label(tile_id),
                )

                try:
                    self._download(
                        tile_id,
                        self.cache_dir,
                        on_progress=self._progress_callback(
                            index, len(todo), tile_id
                        ),
                        should_cancel=self._cancel.is_set,
                    )
                    loaded += 1

                except FileNotFoundError:
                    # reine Wasserkachel ohne Landdaten - kein Fehler
                    pass

                self.done = float(index)

            self.summary = tr("{count} Kacheln geladen.").format(count=loaded)

        except DownloadCancelled:
            self.error = tr("Abgebrochen.")

        except Exception as exc:
            self.error = tr("Download fehlgeschlagen: {error}").format(error=exc)

        finally:
            self.finished = True


@dataclass
class DemTile:
    """Eine geladene Hoehenkachel mit ihrer Geo-Referenzierung."""

    array: np.ndarray
    lon0: float
    lat0: float
    dlon: float
    dlat: float

    @classmethod
    def load(cls, path: Path) -> "DemTile":
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(path)
        tags = im.tag_v2
        scale = tags[33550]
        tiepoint = tags[33922]
        return cls(
            array=np.array(im, dtype=np.float32),
            lon0=tiepoint[3],
            lat0=tiepoint[4],
            dlon=scale[0],
            dlat=scale[1],
        )


# Wie viele Kacheln gleichzeitig im Arbeitsspeicher bleiben duerfen. Eine
# Kachel (3600 x 3600, float32) ist knapp 50 MB gross. Bei grossem
# Stauchfaktor braucht eine Karte viele Kacheln; alle auf einmal zu laden
# fuellt den Arbeitsspeicher (MemoryError).
MAX_CACHED_TILES = 4


class LazyDemTile:
    """Hoehenkachel, deren Pixel erst bei Bedarf geladen werden.

    Beim Anlegen wird nur der Kopf der Datei gelesen (Lage und Groesse),
    nicht die Hoehenwerte.
    """

    def __init__(self, path, lon0, lat0, dlon, dlat, shape, loader=None):
        self.path = Path(path)
        self.lon0 = lon0
        self.lat0 = lat0
        self.dlon = dlon
        self.dlat = dlat
        self.shape = tuple(shape)
        self._loader = loader

    @classmethod
    def open(cls, path: Path) -> "LazyDemTile":
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as im:
            tags = im.tag_v2
            scale = tags[33550]
            tiepoint = tags[33922]
            width, height = im.size
        return cls(
            path=path,
            lon0=tiepoint[3],
            lat0=tiepoint[4],
            dlon=scale[0],
            dlat=scale[1],
            shape=(height, width),
        )

    def load_array(self) -> np.ndarray:
        if self._loader is not None:
            return self._loader(self.path)
        return DemTile.load(self.path).array

    @property
    def array(self) -> np.ndarray:
        # Nur fuer Aufrufer, die direkt auf .array zugreifen (nicht zwischengespeichert).
        return self.load_array()


class DemMosaic:
    """Mehrere Hoehenkacheln, angesprochen wie eine einzige zusammenhaengende Quelle.

    Fuer jeden angefragten Punkt wird die passende Kachel gewaehlt und
    dort bilinear interpoliert - die Kacheln muessen dafuer nicht auf ein
    gemeinsames Pixelraster gebracht werden (wichtig, weil Copernicus DEM
    noerdlich 50°N eine andere Ost-West- als Nord-Sued-Pixelbreite hat).
    """

    def __init__(self, tiles: list[DemTile]):
        self.tiles = tiles
        self._cache = OrderedDict()

    @classmethod
    def from_paths(cls, paths: list[Path]) -> "DemMosaic":
        # Nur die Kopfdaten lesen; die Hoehenwerte kommen erst beim Abfragen.
        return cls([LazyDemTile.open(p) for p in paths])

    def _array_of(self, tile):
        """Hoehenwerte einer Kachel; geladene Kacheln werden begrenzt zwischengespeichert."""

        if not hasattr(tile, "load_array"):
            return tile.array

        key = tile.path
        array = self._cache.pop(key, None)
        if array is None:
            array = tile.load_array()
        self._cache[key] = array
        while len(self._cache) > MAX_CACHED_TILES:
            self._cache.popitem(last=False)
        return array

    def sample_grid(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """Bilineare Hoehenabfrage fuer ganze Arrays von lat/lon-Punkten."""

        out = np.full(lat.shape, np.nan, dtype=np.float32)
        remaining = np.ones(lat.shape, dtype=bool)

        for tile in self.tiles:
            if not remaining.any():
                break
            row = (tile.lat0 - lat) / tile.dlat - 0.5
            col = (lon - tile.lon0) / tile.dlon - 0.5
            h, w = getattr(tile, "shape", None) or tile.array.shape
            in_tile = remaining & (row >= -0.5) & (row < h - 0.5) & (col >= -0.5) & (col < w - 0.5)
            if not in_tile.any():
                continue
            out[in_tile] = _bilinear(self._array_of(tile), row[in_tile], col[in_tile])
            remaining &= ~in_tile

        return out


def _bilinear(array: np.ndarray, row: np.ndarray, col: np.ndarray) -> np.ndarray:
    """
    Bilineare Interpolation an (fraktionalen) Pixelpositionen, Punkte
    ausserhalb werden auf den Rand geklemmt - dasselbe Ergebnis wie
    scipy.ndimage.map_coordinates(order=1, mode="nearest"), aber ohne
    scipy als (in der exe sehr grosse) Abhaengigkeit.
    """

    h, w = array.shape

    r = np.clip(row, 0, h - 1)
    c = np.clip(col, 0, w - 1)

    r0 = np.minimum(np.floor(r).astype(np.intp), max(h - 2, 0))
    c0 = np.minimum(np.floor(c).astype(np.intp), max(w - 2, 0))
    r1 = np.minimum(r0 + 1, h - 1)
    c1 = np.minimum(c0 + 1, w - 1)

    fr = r - r0
    fc = c - c0

    top = array[r0, c0] * (1 - fc) + array[r0, c1] * fc
    bottom = array[r1, c0] * (1 - fc) + array[r1, c1] * fc

    return top * (1 - fr) + bottom * fr
