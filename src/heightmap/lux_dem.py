"""
Luxemburg: Gelaendemodell MNT Lidar 2024 (0,5 m) der Administration du cadastre et de la
topographie (ACT) als weitere Hoehenquelle neben Copernicus, DGM1, swissALTI3D, AHN und BEV.

Das ganze Land liegt in einer einzigen Datei (rund 40 GB): ein Cloud Optimized GeoTIFF
(BigTIFF, EPSG:2169 / LUREF, 128 x 128 Kacheln, LZW, 64-Bit-Gleitkomma) mit Uebersichtsstufen
(Ebene 0 = 0,5 m, Ebene 1 = 1 m, Ebene 2 = 2 m, Ebene 3 = 4 m, ...). Das Studio laedt die Datei
nie ganz, sondern holt per HTTP-Range nur die Kacheln der passenden Ebene, die das Rechteck
braucht (bei 4 m rund 0,3 MB je Quadratkilometer), entschluesselt sie und legt sie als .npy
im Zwischenspeicher ab.

Nutzungsbedingungen: CC0 1.0 (frei nutzbar); die Quellenangabe in ATTRIBUTION ist keine Pflicht,
wird aber mitgefuehrt.
"""

from __future__ import annotations

import io
import json
import math
import os
import struct
import threading
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

from src.heightmap.bev_dem import _array, _read_ifd, _scalar, lzw_decode
from src.heightmap.dgm1_dem import (
    Dgm1Cancelled,
    Dgm1Error,
    Dgm1FetchJob,
    FetchSummary,
    _write_atomic,
)
from src.heightmap.lux2169 import LU_BOUNDS, latlon_to_lux  # noqa: F401  (LU_BOUNDS fuer den Dialog)
from src.i18n import tr

FILE_URL = (
    "https://download.data.public.lu/resources/bd-l-lidar2024-releve-3d-du-territoire-luxembourgeois/"
    "20241223-093912/MNT_Lidar2024.tif"
)
ACTUALITY = "2024"

ATTRIBUTION = (
    "Datenquelle: Administration du cadastre et de la topographie (ACT), Luxembourg – "
    "Lidar 2024, MNT (data.public.lu, CC0 1.0)"
)

NODATA = -9999.0
VALID_MIN_M = -500.0
VALID_MAX_M = 5000.0

MIN_LEVEL = 3                # Ebene 3 = 4 m, die Aufloesung der TPF-Karte
MAX_LEVEL = 5                # 16 m
MIN_REQUEST_INTERVAL_S = 0.05
MAX_CACHED_TILES = 64

# Sicherheitsrand um den Kartenausschnitt (in Metern)
MARGIN_M = 100.0


# ---------------------------------------------------------------------------
# Ebenen
# ---------------------------------------------------------------------------


def level_for_pixel_size(real_pixel_m: float) -> int:
    """Gröbste Ebene, die noch nicht groeber ist als ein Pixel der Zielkarte, mindestens 4 m."""

    if real_pixel_m <= 4.0:
        return MIN_LEVEL

    level = MIN_LEVEL + int(math.floor(math.log2(real_pixel_m / 4.0)))

    return max(MIN_LEVEL, min(MAX_LEVEL, level))


def level_for_selection(selection) -> int:
    """Ebene passend zur realen Pixelgroesse des Rechtecks (Stauchfaktor beruecksichtigt)."""

    real_pixel = 4.0 * float(getattr(selection, "scale_factor", 1.0) or 1.0)

    return level_for_pixel_size(real_pixel)


# ---------------------------------------------------------------------------
# HTTP-Range
# ---------------------------------------------------------------------------


def http_range(url: str, start: int, length: int, session=None, retries: int = 4, sleep=time.sleep) -> bytes:
    """length Bytes ab start per HTTP-Range holen, mit wenigen Wiederholungen."""

    import requests

    from src.http_identity import USER_AGENT

    get = (session or requests).get
    last_error = ""

    for attempt in range(retries):

        try:
            response = get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Range": "bytes=%d-%d" % (start, start + length - 1),
                },
                timeout=120,
            )
        except requests.RequestException as exc:
            last_error = tr("Netzwerkfehler: {exc}").format(exc=exc)
            sleep(min(30.0, 2.0 ** (attempt + 1)))
            continue

        if response.status_code == 429 or response.status_code >= 500:
            last_error = tr("Dienstfehler HTTP {status}").format(status=response.status_code)
            sleep(min(60.0, 5.0 * (attempt + 1)))
            continue

        if response.status_code != 206:
            raise Dgm1Error(
                tr("Luxemburg (data.public.lu) antwortet mit HTTP {status} (erwartet 206, Teilabruf).").format(
                    status=response.status_code
                )
            )

        if len(response.content) != length:
            last_error = tr("unvollständige Antwort")
            sleep(2.0)
            continue

        return response.content

    raise Dgm1Error(
        tr("Luxemburg (data.public.lu) nicht erreichbar ({error}).").format(error=last_error or tr("unbekannter Fehler"))
    )


# ---------------------------------------------------------------------------
# Kopf der Datei (BigTIFF)
# ---------------------------------------------------------------------------


def _doubles(get, tags, tag):
    typ, count, value = tags[tag]
    size = 8 * count

    if size <= 8:
        data = value[:size]
    else:
        data = get(struct.unpack("<Q", value)[0], size)

    return list(struct.unpack("<%dd" % count, data))


def read_header(get, level: int) -> dict:
    """
    Liest Georeferenz und Kachel-Tabellen der Ebene aus dem Kopf der Datei. Das Ergebnis ist
    ein einfaches Woerterbuch (JSON-faehig) mit:
    w, h, tile (Kantenlaenge), offsets, counts, e0, n0 (Ecke oben links von Pixel 0/0),
    ps (Pixelgroesse der Ebene in Metern), level.
    """

    head = get(0, 16)

    if head[:2] != b"II" or struct.unpack("<H", head[2:4])[0] != 43:
        raise Dgm1Error(tr("Die Luxemburg-Datei ist kein BigTIFF, das Studio kann sie nicht lesen."))

    off = struct.unpack("<Q", head[8:16])[0]

    base, off_next = _read_ifd(get, off)

    scale = _doubles(get, base, 33550)
    tie = _doubles(get, base, 33922)
    base_w = _scalar(base, 256)

    tags = base

    for _ in range(level):
        if not off_next:
            raise Dgm1Error(tr("Die Luxemburg-Datei hat keine Ebene {level}.").format(level=level))
        tags, off_next = _read_ifd(get, off_next)

    if _scalar(tags, 259) not in (1, 5, 8, 32946):
        raise Dgm1Error(tr("Die Luxemburg-Datei nutzt eine unbekannte Kompression."))

    if 317 in tags and _scalar(tags, 317) != 1:
        raise Dgm1Error(tr("Die Luxemburg-Datei nutzt einen unbekannten Predictor."))

    w = _scalar(tags, 256)

    return {
        "level": level,
        "w": w,
        "h": _scalar(tags, 257),
        "tile": _scalar(tags, 322),
        "compression": _scalar(tags, 259),
        "offsets": _array(get, tags, 324),
        "counts": _array(get, tags, 325),
        "e0": float(tie[3]),
        "n0": float(tie[4]),
        "ps": float(scale[0]) * base_w / float(w),
    }


# ---------------------------------------------------------------------------
# Kacheln entschluesseln
# ---------------------------------------------------------------------------


def _mini_tiff(data: bytes, width: int, height: int) -> bytes:
    """Verpackt einen LZW-Strom als einstreifiges 8-Bit-TIFF, damit Pillow (libtiff) ihn entpackt."""

    entries = [
        (256, 4, width),
        (257, 4, height),
        (258, 3, 8),
        (259, 3, 5),
        (262, 3, 1),
        (273, 4, 0),          # Platzhalter, siehe unten
        (277, 3, 1),
        (278, 4, height),
        (279, 4, len(data)),
    ]

    data_offset = 8 + 2 + 12 * len(entries) + 4

    out = io.BytesIO()
    out.write(b"II*\x00" + struct.pack("<I", 8))
    out.write(struct.pack("<H", len(entries)))

    for tag, typ, value in entries:
        if tag == 273:
            value = data_offset
        if typ == 3:
            out.write(struct.pack("<HHIHH", tag, typ, 1, value, 0))
        else:
            out.write(struct.pack("<HHII", tag, typ, 1, value))

    out.write(struct.pack("<I", 0))
    out.write(data)

    return out.getvalue()


def _lzw_pillow(data: bytes, width_bytes: int, height: int) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(_mini_tiff(data, width_bytes, height))) as im:
        return np.asarray(im, dtype=np.uint8).tobytes()


def unpack(data: bytes, expected: int, compression: int, width_bytes: int, height: int) -> bytes:
    """Rohe Kachelbytes (unkomprimiert, Deflate oder LZW)."""

    if compression == 1:
        return data

    if compression in (8, 32946):
        import zlib

        return zlib.decompress(data)

    # LZW: schnell ueber Pillow/libtiff, zur Not mit dem eigenen Entschluessler
    try:
        raw = _lzw_pillow(data, width_bytes, height)
        if len(raw) == expected:
            return raw
    except Exception:  # noqa: BLE001
        pass

    return lzw_decode(data, expected)


def clean_heights(arr: np.ndarray) -> np.ndarray:
    """Nodata und unmoegliche Werte -> NaN (in place)."""

    bad = ~np.isfinite(arr) | (arr < VALID_MIN_M) | (arr > VALID_MAX_M) | np.isclose(arr, NODATA)
    arr[bad] = np.nan

    return arr


def decode_tile(data: bytes, size: int = 128, compression: int = 5) -> np.ndarray:
    """Eine Kachel (64-Bit-Gleitkomma, Predictor 1) -> float32-Array, Zeilen von Norden nach Sueden."""

    expected = size * size * 8
    raw = unpack(data, expected, compression, size * 8, size)

    if len(raw) != expected:
        raise Dgm1Error(tr("Eine Luxemburg-Kachel ist beschädigt (falsche Größe nach dem Entpacken)."))

    return np.frombuffer(raw, dtype="<f8").reshape(size, size).astype(np.float32)


# ---------------------------------------------------------------------------
# Welche Kacheln braucht der Kartenausschnitt?
# ---------------------------------------------------------------------------


def tile_grid(header: dict) -> tuple[int, int]:
    """(Kachelspalten, Kachelzeilen) der Ebene."""

    return math.ceil(header["w"] / header["tile"]), math.ceil(header["h"] / header["tile"])


def _to_pixel(e, n, header):
    """Ost/Nord -> (Spalte, Zeile) als Dezimalzahlen im Raster der Ebene (Pixelmitte = ganze Zahl)."""

    ps = header["ps"]

    col = (e - header["e0"]) / ps - 0.5
    row = (header["n0"] - n) / ps - 0.5

    return col, row


def required_lux_tiles(selection, header: dict, margin_m: float = MARGIN_M) -> list[tuple[int, int, int]]:
    """
    Liste der Kacheln (Ebene, Zeile, Spalte), die das (ggf. gedrehte) Rechteck beruehren.
    Nicht die Bounding-Box, sondern nur die tatsaechlich belegten Kacheln.
    """

    corners = list(selection.corners_latlon())

    if len(corners) != 4:
        raise Dgm1Error("Der Kartenausschnitt hat keine vier Ecken.")

    pts = []
    for lat, lon in corners:
        e, n = latlon_to_lux(lat, lon)
        pts.append((float(e), float(n)))

    cx = sum(p[0] for p in pts) / 4.0
    cy = sum(p[1] for p in pts) / 4.0
    pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))

    p0 = np.array(pts[0])
    pu = np.array(pts[1]) - p0
    pv = np.array(pts[3]) - p0

    len_u = float(np.hypot(*pu))
    len_v = float(np.hypot(*pv))

    if len_u <= 0 or len_v <= 0:
        raise Dgm1Error("Der Kartenausschnitt ist leer.")

    step_m = header["tile"] * header["ps"] / 2.0

    mu = margin_m / len_u
    mv = margin_m / len_v

    nu = int(math.ceil(len_u * (1 + 2 * mu) / step_m)) + 1
    nv = int(math.ceil(len_v * (1 + 2 * mv) / step_m)) + 1

    uu, vv = np.meshgrid(np.linspace(-mu, 1 + mu, nu), np.linspace(-mv, 1 + mv, nv))

    e = p0[0] + uu * pu[0] + vv * pv[0]
    n = p0[1] + uu * pu[1] + vv * pv[1]

    col, row = _to_pixel(e, n, header)

    tiles_x, tiles_y = tile_grid(header)

    tc = np.floor(col / header["tile"]).astype(np.int64)
    tr_ = np.floor(row / header["tile"]).astype(np.int64)

    inside = (tc >= 0) & (tc < tiles_x) & (tr_ >= 0) & (tr_ < tiles_y)

    result = {(header["level"], int(r), int(c)) for r, c in zip(tr_[inside].ravel(), tc[inside].ravel())}

    return sorted(result)


# ---------------------------------------------------------------------------
# Zwischenspeicher
# ---------------------------------------------------------------------------


def header_path(cache_dir: Path, level: int) -> Path:
    return Path(cache_dir) / f"header_L{level}.json"


def tile_path(cache_dir: Path, level: int, row: int, col: int) -> Path:
    return Path(cache_dir) / f"L{level}_{row}_{col}.npy"


def _none_path(cache_dir: Path, level: int, row: int, col: int) -> Path:
    return tile_path(cache_dir, level, row, col).with_suffix(".none")


def load_header(cache_dir: Path, level: int) -> dict | None:
    path = header_path(cache_dir, level)

    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_npy(path: Path, arr: np.ndarray) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.part")
    try:
        with open(tmp, "wb") as f:
            np.save(f, arr)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Abruf
# ---------------------------------------------------------------------------


def _merged_ranges(tiles, header):
    """
    Fasst Kacheln, die in der Datei lueckenlos hintereinander liegen, zu einem Abruf zusammen.
    Ergebnis: Liste von (Start, Laenge, [(Kachel, Start in diesem Abruf, Laenge), ...]).
    """

    tiles_x, _ = tile_grid(header)
    items = []

    for tile in tiles:
        _lvl, row, col = tile
        index = row * tiles_x + col
        items.append((header["offsets"][index], header["counts"][index], tile))

    items.sort()

    groups = []

    for start, length, tile in items:
        if length <= 0:
            continue
        if groups and start == groups[-1][0] + groups[-1][1]:
            g = groups[-1]
            g[2].append((tile, g[1], length))
            groups[-1] = (g[0], g[1] + length, g[2])
        else:
            groups.append((start, length, [(tile, 0, length)]))

    return groups


def fetch_tiles_for_selection(
    selection,
    cache_dir: Path,
    level: int | None = None,
    progress=None,
    cancelled=None,
    get_range=None,
    sleep=time.sleep,
    min_interval_s: float = MIN_REQUEST_INTERVAL_S,
) -> FetchSummary:
    """
    Holt alle fehlenden Kacheln fuer das Rechteck, entschluesselt sie und legt sie im
    Zwischenspeicher ab. progress(done, total, text) wird laufend aufgerufen, cancelled()
    fragt den Abbruchwunsch ab (Dgm1Cancelled). Kacheln ohne Daten (ausserhalb Luxemburgs)
    werden vermerkt und nicht erneut angefragt.
    """

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    level = level_for_selection(selection) if level is None else level

    def get(start, length):
        return (get_range or http_range)(FILE_URL, start, length)

    header = load_header(cache_dir, level)

    if header is None:
        header = read_header(get, level)
        _write_atomic(header_path(cache_dir, level), json.dumps(header).encode("utf-8"))

    tiles = required_lux_tiles(selection, header)
    summary = FetchSummary(total=len(tiles))

    todo = []

    for tile in tiles:
        if tile_path(cache_dir, *tile).exists():
            summary.already_cached += 1
        elif _none_path(cache_dir, *tile).exists():
            summary.no_data += 1
        else:
            todo.append(tile)

    done = len(tiles) - len(todo)

    def report(text):
        if progress is not None:
            progress(done, len(tiles), text)

    if not todo:
        report("Fertig")
        return summary

    last_request = None

    for start, length, members in _merged_ranges(todo, header):

        if cancelled is not None and cancelled():
            raise Dgm1Cancelled("Abgebrochen.")

        report(tr("Kachel {value} von {count}").format(value=done + 1, count=len(tiles)))

        if last_request is not None:
            wait = min_interval_s - (time.monotonic() - last_request)
            if wait > 0:
                sleep(wait)
        last_request = time.monotonic()

        blob = get(start, length)

        for tile, pos, size in members:

            arr = clean_heights(decode_tile(blob[pos:pos + size], header["tile"], header["compression"]))

            if np.isnan(arr).all():
                _write_atomic(_none_path(cache_dir, *tile), b"keine Daten")
                summary.no_data += 1
            else:
                _save_npy(tile_path(cache_dir, *tile), arr)
                summary.fetched += 1

            done += 1

    # Kacheln mit Laenge 0 (nie beschrieben) gelten als "keine Daten"
    for tile in todo:
        if not tile_path(cache_dir, *tile).exists() and not _none_path(cache_dir, *tile).exists():
            _write_atomic(_none_path(cache_dir, *tile), b"keine Daten")
            summary.no_data += 1

    report("Fertig")

    return summary


class LuxFetchJob(Dgm1FetchJob):
    """Fuehrt fetch_tiles_for_selection in einem Hintergrund-Thread aus (gleiche Schnittstelle
    wie Dgm1FetchJob, damit das Fortschrittsfenster alle Quellen nutzen kann)."""

    def _run(self) -> None:
        try:
            self.summary = fetch_tiles_for_selection(
                self.selection,
                self.cache_dir,
                progress=self._on_progress,
                cancelled=self._cancel_flag.is_set,
            )
        except Dgm1Cancelled:
            self.cancelled = True
            self.error = "Abgebrochen."
        except Exception as exc:  # noqa: BLE001 - jede Fehlerart soll in der Oberflaeche landen
            self.error = str(exc)
        finally:
            self.finished = True


# ---------------------------------------------------------------------------
# Mosaik
# ---------------------------------------------------------------------------


class LuxMosaic:
    """Zwischengespeicherte Luxemburg-Kacheln, angesprochen wie eine einzige Hoehenquelle (sample_grid)."""

    # Mehrere Threads duerfen gleichzeitig abfragen (Kachel-Speicher ist abgesichert).
    parallel_safe = True

    def __init__(self, cache_dir: Path, header: dict | None, tiles=(), missing: int = 0):
        self.cache_dir = Path(cache_dir)
        self.header = header
        self.level = header["level"] if header else MIN_LEVEL
        self.missing_slots = missing
        self._have = {t for t in tiles if tile_path(self.cache_dir, *t).exists()} if header else set()
        self.slot_count = len(self._have)
        self.attributions = [ATTRIBUTION] if self._have else []
        self.actualities = [ACTUALITY] if self._have else []
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._max_cached = MAX_CACHED_TILES

    def prepare_parallel(self, workers: int):
        """Mehr Arbeits-Threads brauchen etwas mehr Kachel-Speicher."""

        self._max_cached = max(MAX_CACHED_TILES, 2 * int(workers))

    @classmethod
    def from_cache(cls, selection, cache_dir: Path, level: int | None = None) -> "LuxMosaic":
        level = level_for_selection(selection) if level is None else level
        header = load_header(cache_dir, level)

        if header is None:
            return cls(cache_dir, None)

        tiles = required_lux_tiles(selection, header)
        missing = sum(1 for t in tiles if not tile_path(cache_dir, *t).exists() and not _none_path(cache_dir, *t).exists())

        return cls(cache_dir, header, tiles, missing)

    def _array(self, tile):
        with self._lock:
            arr = self._cache.pop(tile, None)
        if arr is None:
            # Laden ausserhalb der Sperre, damit Threads gleichzeitig laden koennen.
            arr = np.load(tile_path(self.cache_dir, *tile))
        with self._lock:
            self._cache[tile] = arr
            while len(self._cache) > self._max_cached:
                self._cache.popitem(last=False)
        return arr

    def _gather(self, rows, cols):
        """Werte an ganzzahligen Pixelpositionen; NaN ohne geladene Kachel."""

        size = self.header["tile"]
        out = np.full(rows.shape, np.nan, dtype=np.float32)

        keys = (rows // size) * 100000 + (cols // size)

        for key in np.unique(keys):
            tile = (self.level, int(key // 100000), int(key % 100000))
            if tile not in self._have:
                continue
            sel = keys == key
            arr = self._array(tile)
            out[sel] = arr[rows[sel] - tile[1] * size, cols[sel] - tile[2] * size]

        return out

    def sample_grid(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """Bilineare Hoehenabfrage; NaN dort, wo keine Kachel vorhanden ist."""

        lat = np.asarray(lat)
        lon = np.asarray(lon)

        if self.header is None or not self._have:
            return np.full(lat.shape, np.nan, dtype=np.float32)

        e, n = latlon_to_lux(lat.ravel(), lon.ravel())

        col, row = _to_pixel(e, n, self.header)

        width, height = self.header["w"], self.header["h"]

        # Punkte ausserhalb des Rasters bleiben NaN (dort springt Copernicus ein)
        inside = (col >= -0.5) & (col <= width - 0.5) & (row >= -0.5) & (row <= height - 0.5)

        out = np.full(e.shape, np.nan, dtype=np.float32)

        if not inside.any():
            return out.reshape(lat.shape)

        idx = np.nonzero(inside)[0]

        col = np.clip(col[idx], 0, width - 1)
        row = np.clip(row[idx], 0, height - 1)

        c0 = np.minimum(np.floor(col).astype(np.int64), width - 2)
        r0 = np.minimum(np.floor(row).astype(np.int64), height - 2)
        c1 = c0 + 1
        r1 = r0 + 1
        fc = (col - c0).astype(np.float32)
        fr = (row - r0).astype(np.float32)

        v00 = self._gather(r0, c0)
        v01 = self._gather(r0, c1)
        v10 = self._gather(r1, c0)
        v11 = self._gather(r1, c1)

        top = v00 * (1 - fc) + v01 * fc
        bottom = v10 * (1 - fc) + v11 * fc

        out[idx] = top * (1 - fr) + bottom * fr

        return out.reshape(lat.shape)


def attribution_text(attributions: list[str]) -> str:
    """Quellenvermerk fuer veroeffentlichte Karten."""

    return "\n".join(attributions)
