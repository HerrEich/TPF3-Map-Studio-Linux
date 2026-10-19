"""
Oesterreich: ALS-DTM-Hoehenraster 1 m des BEV (Bundesamt fuer Eich- und Vermessungswesen)
als weitere Hoehenquelle neben Copernicus, DGM1, swissALTI3D und AHN.

Die Daten liegen als 55 Dateien zu je 50 km x 50 km (EPSG:3035, ETRS89-LAEA) auf
data.bev.gv.at. Jede Datei ist ein Cloud Optimized GeoTIFF (BigTIFF, 512 x 512 Kacheln,
LZW mit Gleitkomma-Predictor) und rund 8 GB gross; sie enthaelt Uebersichtsstufen
(Ebene 0 = 1 m, Ebene 1 = 2 m, Ebene 2 = 4 m, ...). Das Studio laedt deshalb nie die
ganze Datei, sondern holt per HTTP-Range nur die 512er-Kacheln der passenden Ebene,
die das Rechteck braucht (bei 4 m rund 0,6 MB je Kachel), entschluesselt sie selbst
(ohne Zusatzbibliothek) und legt sie als .npy im Zwischenspeicher ab.

Nutzungsbedingungen: CC BY 4.0, die Quellenangabe ist Pflicht (siehe ATTRIBUTION).
"""

from __future__ import annotations

import json
import math
import os
import struct
import threading
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

from src.heightmap.dgm1_dem import (
    Dgm1Cancelled,
    Dgm1Error,
    Dgm1FetchJob,
    FetchSummary,
    _write_atomic,
)
from src.i18n import tr

BASE_URL = "https://data.bev.gv.at/download/ALS/DTM/20250915"
ACTUALITY = "2025-09-15"

# Quellenangabe nach den Nutzungsbedingungen (CC BY 4.0)
ATTRIBUTION = "Datenquelle: BEV – Bundesamt für Eich- und Vermessungswesen, ALS DTM Höhenraster 1 m (CC BY 4.0)"

# Grober Umriss von Oesterreich (Breite von/bis, Laenge von/bis); nur dafuer, die
# BEV-Auswahl bei passenden Karten anzubieten.
AT_BOUNDS = (46.3, 49.1, 9.5, 17.2)

FILE_SIZE_M = 50000          # Kantenlaenge einer Datei in Metern
FILE_PIXELS = 50001          # Pixel je Seite in Ebene 0 (50 km plus ein Randpixel)
ORIGIN_E = -0.5              # Ecke oben links des Pixels (0, 0) relativ zur Dateigrenze
ORIGIN_N = 0.5               # (Ost: Dateigrenze - 0,5 m, Nord: Dateioberkante + 0,5 m)
TILE_PX = 512
NODATA = -9999.0
VALID_MIN_M = -500.0
VALID_MAX_M = 5000.0

MIN_LEVEL = 2                # Ebene 2 = 4 m, die Aufloesung der TPF-Karte
MAX_LEVEL = 8
MIN_REQUEST_INTERVAL_S = 0.05
MAX_CACHED_TILES = 32

# Sicherheitsrand um den Kartenausschnitt (in Metern)
MARGIN_M = 100.0


# ---------------------------------------------------------------------------
# Projektion: WGS84/ETRS89 -> EPSG:3035 (Lambert Azimuthal Equal Area)
# ---------------------------------------------------------------------------

_A = 6378137.0
_F = 1 / 298.257222101
_E2 = 2 * _F - _F * _F
_E = math.sqrt(_E2)
_LAT0 = math.radians(52.0)
_LON0 = math.radians(10.0)
_FALSE_E = 4321000.0
_FALSE_N = 3210000.0


def _q(phi):
    s = np.sin(phi)
    return (1 - _E2) * (s / (1 - _E2 * s * s) - (1 / (2 * _E)) * np.log((1 - _E * s) / (1 + _E * s)))


_QP = float(_q(np.array(math.pi / 2)))
_Q0 = float(_q(np.array(_LAT0)))
_RQ = _A * math.sqrt(_QP / 2)
_B0 = math.asin(_Q0 / _QP)
_M0 = math.cos(_LAT0) / math.sqrt(1 - _E2 * math.sin(_LAT0) ** 2)
_D = _A * _M0 / (_RQ * math.cos(_B0))


def latlon_to_laea(lat, lon):
    """(Breite, Laenge) in Grad -> (Ost, Nord) in Metern, EPSG:3035."""

    phi = np.radians(np.asarray(lat, dtype=np.float64))
    lam = np.radians(np.asarray(lon, dtype=np.float64))

    beta = np.arcsin(np.clip(_q(phi) / _QP, -1.0, 1.0))
    dl = lam - _LON0

    denom = 1 + math.sin(_B0) * np.sin(beta) + math.cos(_B0) * np.cos(beta) * np.cos(dl)
    b = _RQ * np.sqrt(2.0 / denom)

    x = b * _D * np.cos(beta) * np.sin(dl)
    y = (b / _D) * (math.cos(_B0) * np.sin(beta) - math.sin(_B0) * np.cos(beta) * np.cos(dl))

    return x + _FALSE_E, y + _FALSE_N


# ---------------------------------------------------------------------------
# Dateien, Ebenen, Kacheln
# ---------------------------------------------------------------------------


def file_name(e_key: int, n_key: int) -> str:
    """Dateiname ohne Endung, z. B. ALS_DTM_CRS3035RES50000mN2650000E4700000."""

    return f"ALS_DTM_CRS3035RES50000mN{n_key}E{e_key}"


def file_url(e_key: int, n_key: int) -> str:
    return f"{BASE_URL}/{file_name(e_key, n_key)}.tif"


def level_pixel_size(width: int) -> float:
    """Pixelgroesse einer Ebene aus ihrer Breite (Ebene 0: 1 m)."""

    return FILE_PIXELS / float(width)


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


def required_bev_tiles(selection, level: int = MIN_LEVEL, margin_m: float = MARGIN_M):
    """
    Liste der 512er-Kacheln (e_key, n_key, level, row, col), die das (ggf. gedrehte)
    Rechteck beruehren. Nicht die Bounding-Box, sondern nur die tatsaechlich belegten Kacheln.
    """

    corners = list(selection.corners_latlon())

    if len(corners) != 4:
        raise Dgm1Error("Der Kartenausschnitt hat keine vier Ecken.")

    pts = []
    for lat, lon in corners:
        e, n = latlon_to_laea(lat, lon)
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

    pixel_m = level_pixel_size(FILE_PIXELS // (2 ** level))
    step_m = TILE_PX * pixel_m / 2.0

    mu = margin_m / len_u
    mv = margin_m / len_v

    nu = int(math.ceil(len_u * (1 + 2 * mu) / step_m)) + 1
    nv = int(math.ceil(len_v * (1 + 2 * mv) / step_m)) + 1

    uu, vv = np.meshgrid(np.linspace(-mu, 1 + mu, nu), np.linspace(-mv, 1 + mv, nv))

    e = p0[0] + uu * pu[0] + vv * pv[0]
    n = p0[1] + uu * pu[1] + vv * pv[1]

    result = set()

    for ee, nn in zip(e.ravel(), n.ravel()):
        e_key = int(math.floor(ee / FILE_SIZE_M)) * FILE_SIZE_M
        n_key = int(math.floor(nn / FILE_SIZE_M)) * FILE_SIZE_M
        col, row = _to_pixel(ee, nn, e_key, n_key, level)
        result.add((e_key, n_key, level, int(max(0, row)) // TILE_PX, int(max(0, col)) // TILE_PX))

    return sorted(result)


def _to_pixel(e, n, e_key, n_key, level):
    """Ost/Nord -> (Spalte, Zeile) als Dezimalzahlen im Raster der Ebene (Pixelmitte = ganze Zahl)."""

    ps = level_pixel_size(FILE_PIXELS // (2 ** level))

    col = (e - (e_key + ORIGIN_E)) / ps - 0.5
    row = ((n_key + FILE_SIZE_M + ORIGIN_N) - n) / ps - 0.5

    return col, row


# ---------------------------------------------------------------------------
# LZW und Gleitkomma-Predictor
# ---------------------------------------------------------------------------


def lzw_decode(data: bytes, expected: int) -> bytes:
    """TIFF-LZW (MSB zuerst, 9 bis 12 Bit, Early Change) bis zu expected Bytes."""

    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    bits = 9
    buf = 0
    nbits = 0
    pos = 0
    prev = None
    n = len(data)

    while len(out) < expected:

        while nbits < bits and pos < n:
            buf = (buf << 8) | data[pos]
            pos += 1
            nbits += 8

        if nbits < bits:
            break

        code = (buf >> (nbits - bits)) & ((1 << bits) - 1)
        nbits -= bits
        buf &= (1 << nbits) - 1

        if code == 257:
            break

        if code == 256:
            del table[258:]
            bits = 9
            prev = None
            continue

        if prev is None:
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        else:
            entry = prev + prev[:1]
            table.append(entry)

        out += entry
        prev = entry

        size = len(table)
        if size >= 2047:
            bits = 12
        elif size >= 1023:
            bits = 11
        elif size >= 511:
            bits = 10
        else:
            bits = 9

    return bytes(out)


def decode_tile(data: bytes, width: int = TILE_PX, height: int = TILE_PX) -> np.ndarray:
    """Eine komprimierte 512er-Kachel -> float32-Array (Zeilen von Norden nach Sueden)."""

    raw = lzw_decode(data, width * height * 4)

    if len(raw) != width * height * 4:
        raise Dgm1Error(tr("BEV-Kachel ist beschädigt (falsche Größe nach dem Entpacken)."))

    a = np.frombuffer(raw, dtype=np.uint8).reshape(height, width * 4).copy()

    # Predictor 3: waagerechte Differenzen ueber die Bytes einer Zeile aufheben ...
    np.cumsum(a, axis=1, dtype=np.uint8, out=a)

    # ... und die vier Byte-Ebenen (hoechstwertiges Byte zuerst) wieder zusammensetzen
    planes = a.reshape(height, 4, width)
    be = np.ascontiguousarray(planes.transpose(0, 2, 1))

    return be.view(">f4").reshape(height, width).astype(np.float32)


def clean_heights(arr: np.ndarray) -> np.ndarray:
    """Nodata und unmoegliche Werte -> NaN (in place)."""

    bad = ~np.isfinite(arr) | (arr < VALID_MIN_M) | (arr > VALID_MAX_M) | np.isclose(arr, NODATA)
    arr[bad] = np.nan

    return arr


# ---------------------------------------------------------------------------
# Abruf (HTTP-Range)
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

        if response.status_code == 404:
            raise FileNotFoundError(url)

        if response.status_code != 206:
            raise Dgm1Error(
                tr("BEV antwortet mit HTTP {status} (erwartet 206, Teilabruf) für {url}.").format(
                    status=response.status_code, url=url
                )
            )

        if len(response.content) != length:
            last_error = tr("unvollständige Antwort")
            sleep(2.0)
            continue

        return response.content

    raise Dgm1Error(tr("BEV nicht erreichbar ({error}).").format(error=last_error or tr("unbekannter Fehler")))


_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8, 17: 8, 18: 8}
_FMT = {1: "B", 3: "H", 4: "I", 16: "Q", 17: "q"}


def _read_ifd(get, off):
    n = struct.unpack("<Q", get(off, 8))[0]
    raw = get(off + 8, n * 20 + 8)
    tags = {}
    for i in range(n):
        entry = raw[i * 20:(i + 1) * 20]
        tag, typ, count = struct.unpack("<HHQ", entry[:12])
        tags[tag] = (typ, count, entry[12:20])
    return tags, struct.unpack("<Q", raw[n * 20:n * 20 + 8])[0]


def _scalar(tags, tag):
    typ, _count, value = tags[tag]
    fmt = {3: "<H", 4: "<I", 16: "<Q"}[typ]
    return struct.unpack(fmt, value[:struct.calcsize(fmt)])[0]


def _array(get, tags, tag):
    typ, count, value = tags[tag]
    size = _SIZES[typ] * count
    if size <= 8:
        data = value[:size]
    else:
        data = get(struct.unpack("<Q", value)[0], size)
    return list(struct.unpack("<%d%s" % (count, _FMT[typ]), data))


def read_level_header(get, level: int) -> dict:
    """Liest die Kachel-Tabellen der Ebene aus dem Kopf der Datei (wenige KB)."""

    head = get(0, 16)

    if head[:2] != b"II" or struct.unpack("<H", head[2:4])[0] != 43:
        raise Dgm1Error(tr("Die BEV-Datei ist kein BigTIFF, das Studio kann sie nicht lesen."))

    off = struct.unpack("<Q", head[8:16])[0]

    for _ in range(level):
        tags, off = _read_ifd(get, off)
        if not off:
            raise Dgm1Error(tr("Die BEV-Datei hat keine Ebene {level}.").format(level=level))

    tags, _next = _read_ifd(get, off)

    if _scalar(tags, 259) != 5 or _scalar(tags, 317) != 3:
        raise Dgm1Error(tr("Die BEV-Datei nutzt eine unbekannte Kompression."))

    return {
        "w": _scalar(tags, 256),
        "h": _scalar(tags, 257),
        "tile": _scalar(tags, 322),
        "offsets": _array(get, tags, 324),
        "counts": _array(get, tags, 325),
    }


# ---------------------------------------------------------------------------
# Zwischenspeicher
# ---------------------------------------------------------------------------


def tile_path(cache_dir: Path, e_key: int, n_key: int, level: int, row: int, col: int) -> Path:
    return Path(cache_dir) / file_name(e_key, n_key) / f"L{level}_{row}_{col}.npy"


def _none_path(cache_dir: Path, e_key: int, n_key: int, level: int, row: int, col: int) -> Path:
    return tile_path(cache_dir, e_key, n_key, level, row, col).with_suffix(".none")


def tile_is_cached(cache_dir: Path, tile) -> bool:
    e_key, n_key, level, row, col = tile
    return tile_path(cache_dir, *tile).exists() or _none_path(cache_dir, *tile).exists()


def _header_path(cache_dir: Path, e_key: int, n_key: int, level: int) -> Path:
    return Path(cache_dir) / file_name(e_key, n_key) / f"header_L{level}.json"


def _save_npy(path: Path, arr: np.ndarray) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.part")
    try:
        with open(tmp, "wb") as f:
            np.save(f, arr)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


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
    fragt den Abbruchwunsch ab (Dgm1Cancelled). Kacheln ausserhalb der Daten werden als
    "keine Daten" vermerkt.
    """

    cache_dir = Path(cache_dir)
    level = level_for_selection(selection) if level is None else level

    tiles = required_bev_tiles(selection, level)
    summary = FetchSummary(total=len(tiles))

    todo = []

    for tile in tiles:
        if tile_is_cached(cache_dir, tile):
            if _none_path(cache_dir, *tile).exists():
                summary.no_data += 1
            else:
                summary.already_cached += 1
        else:
            todo.append(tile)

    done = len(tiles) - len(todo)

    def report(text):
        if progress is not None:
            progress(done, len(tiles), text)

    if not todo:
        report("Fertig")
        return summary

    headers: dict[tuple[int, int], dict] = {}
    last_request = None

    for e_key, n_key, lvl, row, col in todo:

        if cancelled is not None and cancelled():
            raise Dgm1Cancelled("Abgebrochen.")

        report(tr("Kachel {value} von {count}").format(value=done + 1, count=len(tiles)))

        url = file_url(e_key, n_key)

        def get(start, length, _url=url):
            return (get_range or http_range)(_url, start, length)

        folder = Path(cache_dir) / file_name(e_key, n_key)
        folder.mkdir(parents=True, exist_ok=True)

        key = (e_key, n_key)

        if key not in headers:
            header_file = _header_path(cache_dir, e_key, n_key, lvl)
            if header_file.exists():
                headers[key] = json.loads(header_file.read_text(encoding="utf-8"))
            else:
                try:
                    headers[key] = read_level_header(get, lvl)
                except FileNotFoundError:
                    headers[key] = {"missing": True}
                else:
                    _write_atomic(header_file, json.dumps(headers[key]).encode("utf-8"))

        header = headers[key]

        if header.get("missing"):
            _write_atomic(_none_path(cache_dir, e_key, n_key, lvl, row, col), b"keine Daten")
            summary.no_data += 1
            done += 1
            continue

        tiles_x = math.ceil(header["w"] / header["tile"])
        tiles_y = math.ceil(header["h"] / header["tile"])

        if row >= tiles_y or col >= tiles_x:
            _write_atomic(_none_path(cache_dir, e_key, n_key, lvl, row, col), b"ausserhalb")
            summary.no_data += 1
            done += 1
            continue

        index = row * tiles_x + col

        if last_request is not None:
            wait = min_interval_s - (time.monotonic() - last_request)
            if wait > 0:
                sleep(wait)
        last_request = time.monotonic()

        data = get(header["offsets"][index], header["counts"][index])

        arr = clean_heights(decode_tile(data, header["tile"], header["tile"]))

        _save_npy(tile_path(cache_dir, e_key, n_key, lvl, row, col), arr)

        summary.fetched += 1
        done += 1

    report("Fertig")

    return summary


class BevFetchJob(Dgm1FetchJob):
    """Fuehrt fetch_tiles_for_selection in einem Hintergrund-Thread aus (gleiche Schnittstelle
    wie Dgm1FetchJob, damit das Fortschrittsfenster beide nutzen kann)."""

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


class BevMosaic:
    """Zwischengespeicherte BEV-Kacheln, angesprochen wie eine einzige Hoehenquelle (sample_grid)."""

    # Mehrere Threads duerfen gleichzeitig abfragen (Kachel-Speicher ist abgesichert).
    parallel_safe = True

    def __init__(self, cache_dir: Path, level: int, tiles, missing: int = 0):
        self.cache_dir = Path(cache_dir)
        self.level = level
        self.missing_slots = missing
        self._have = {t for t in tiles if tile_path(self.cache_dir, *t).exists()}
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
    def from_cache(cls, selection, cache_dir: Path, level: int | None = None) -> "BevMosaic":
        level = level_for_selection(selection) if level is None else level
        tiles = required_bev_tiles(selection, level)
        missing = sum(1 for t in tiles if not tile_path(cache_dir, *t).exists())
        return cls(cache_dir, level, tiles, missing)

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

    def _gather(self, e_key, n_key, rows, cols):
        """Werte an ganzzahligen Pixelpositionen einer Datei; NaN ohne geladene Kachel."""

        out = np.full(rows.shape, np.nan, dtype=np.float32)

        tr_ = rows // TILE_PX
        tc_ = cols // TILE_PX
        keys = tr_ * 100000 + tc_

        for key in np.unique(keys):
            tile = (e_key, n_key, self.level, int(key // 100000), int(key % 100000))
            if tile not in self._have:
                continue
            sel = keys == key
            arr = self._array(tile)
            out[sel] = arr[rows[sel] - tile[3] * TILE_PX, cols[sel] - tile[4] * TILE_PX]

        return out

    def sample_grid(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """Bilineare Hoehenabfrage; NaN dort, wo keine Kachel vorhanden ist."""

        lat = np.asarray(lat)
        lon = np.asarray(lon)

        e, n = latlon_to_laea(lat.ravel(), lon.ravel())

        out = np.full(e.shape, np.nan, dtype=np.float32)

        e_keys = np.floor(e / FILE_SIZE_M).astype(np.int64) * FILE_SIZE_M
        n_keys = np.floor(n / FILE_SIZE_M).astype(np.int64) * FILE_SIZE_M

        width = FILE_PIXELS // (2 ** self.level)
        ps = level_pixel_size(width)

        file_ids = e_keys * 10_000_000 + n_keys // FILE_SIZE_M

        for fid in np.unique(file_ids):

            idx = np.nonzero(file_ids == fid)[0]
            e_key = int(e_keys[idx[0]])
            n_key = int(n_keys[idx[0]])

            col = (e[idx] - (e_key + ORIGIN_E)) / ps - 0.5
            row = ((n_key + FILE_SIZE_M + ORIGIN_N) - n[idx]) / ps - 0.5

            col = np.clip(col, 0, width - 1)
            row = np.clip(row, 0, width - 1)

            c0 = np.minimum(np.floor(col).astype(np.int64), width - 2)
            r0 = np.minimum(np.floor(row).astype(np.int64), width - 2)
            c1 = c0 + 1
            r1 = r0 + 1
            fc = (col - c0).astype(np.float32)
            fr = (row - r0).astype(np.float32)

            v00 = self._gather(e_key, n_key, r0, c0)
            v01 = self._gather(e_key, n_key, r0, c1)
            v10 = self._gather(e_key, n_key, r1, c0)
            v11 = self._gather(e_key, n_key, r1, c1)

            top = v00 * (1 - fc) + v01 * fc
            bottom = v10 * (1 - fc) + v11 * fc

            out[idx] = top * (1 - fr) + bottom * fr

        return out.reshape(lat.shape)


def attribution_text(attributions: list[str]) -> str:
    """Quellenvermerk fuer veroeffentlichte Karten."""

    return "\n".join(attributions)
