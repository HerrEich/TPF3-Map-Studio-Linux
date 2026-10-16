"""
ASC-Dateien (ESRI ASCII Grid) zu einer GeoTIFF zusammenfassen.

Manche Landesportale (zum Beispiel die Provinz Trient) liefern Hoehendaten als
ASC-Kacheln. Die Quelle "DGM1 aus eigenen GeoTIFF-Kacheln" liest aber nur
GeoTIFF mit Ecken auf ganzen Kilometern. Dieses Modul liest alle ASC-Dateien
eines Ordners, mittelt Ueberlappungen, rechnet auf die gewuenschte Pixelgroesse
herunter, richtet den Ausschnitt an ganzen Kilometern aus und schreibt eine
GeoTIFF mit Koordinatensystem. Die ASC-Dateien bleiben unveraendert.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, TiffImagePlugin

from src.heightmap.utm import zone_for_lon
from src.i18n import tr

OUTPUT_NAME = "asc_zusammengefuegt.tif"
NODATA_OUT = -9999.0

# (EPSG-Code, Anzeigename). ASC-Dateien tragen kein Koordinatensystem im Kopf.
EPSG_CHOICES = (
    (25832, "ETRS89 / UTM 32N (EPSG:25832)"),
    (25833, "ETRS89 / UTM 33N (EPSG:25833)"),
    (25831, "ETRS89 / UTM 31N (EPSG:25831)"),
)


class AscImportError(RuntimeError):
    """ASC-Dateien konnten nicht umgewandelt werden."""


class AscCancelled(AscImportError):
    """Der Nutzer hat die Umwandlung abgebrochen."""


def asc_files(folder) -> list[Path]:
    return sorted(
        p for p in Path(folder).rglob("*")
        if p.is_file() and p.suffix.lower() == ".asc"
    )


def has_geotiff(folder) -> bool:
    return any(
        p.is_file() and p.suffix.lower() in (".tif", ".tiff")
        for p in Path(folder).rglob("*")
    )


def needs_conversion(folder) -> bool:
    """Ordner mit ASC-Dateien, aber ohne GeoTIFF."""

    return bool(asc_files(folder)) and not has_geotiff(folder)


def default_epsg(lon_deg: float) -> int:
    zone = zone_for_lon(lon_deg)
    return 25800 + zone if zone in (31, 32, 33) else 25832


def _read_header(handle) -> tuple[dict, int]:
    head = {}
    pos = handle.tell()

    while len(head) < 6:
        line = handle.readline()
        parts = line.split()

        if len(parts) >= 2 and parts[0].replace("_", "").isalpha():
            head[parts[0].lower()] = float(parts[1])
            pos = handle.tell()
        else:
            break

    return head, pos


def _geometry(head: dict, name: str):
    try:
        ncols = int(head["ncols"])
        nrows = int(head["nrows"])
        cell = float(head["cellsize"])
    except KeyError as exc:
        raise AscImportError(
            tr("{name}: kein gültiger ASC-Kopf (es fehlt {key}).").format(name=name, key=exc.args[0])
        ) from exc

    x0 = head["xllcorner"] if "xllcorner" in head else head.get("xllcenter", 0.0) - cell / 2.0
    y0 = head["yllcorner"] if "yllcorner" in head else head.get("yllcenter", 0.0) - cell / 2.0

    return ncols, nrows, cell, x0, y0


def read_asc(path):
    """(Hoehen mit NaN fuer 'keine Daten', x_links, y_unten, Zellgroesse)."""

    path = Path(path)

    with open(path, "r", encoding="ascii", errors="replace") as handle:
        head, pos = _read_header(handle)
        handle.seek(pos)
        text = handle.read()

    ncols, nrows, cell, x0, y0 = _geometry(head, path.name)
    nodata = head.get("nodata_value", -9999.0)

    try:
        values = np.fromstring(text, dtype=np.float32, sep=" ")
    except Exception:  # noqa: BLE001
        values = np.array(text.split(), dtype=np.float32)

    if values.size != ncols * nrows:
        raise AscImportError(
            tr("{name}: {found} Werte gefunden, erwartet {expected}.").format(
                name=path.name, found=values.size, expected=ncols * nrows
            )
        )

    arr = values.reshape(nrows, ncols)
    arr[np.isclose(arr, nodata)] = np.nan

    return arr, x0, y0, cell


def _block_sums(arr: np.ndarray, block: int):
    if block <= 1:
        valid = np.isfinite(arr)
        return np.where(valid, arr, 0.0), valid.astype(np.uint16)

    h, w = arr.shape
    nh, nw = h // block, w // block
    arr = arr[: nh * block, : nw * block]
    valid = np.isfinite(arr)
    total = np.where(valid, arr, 0.0).reshape(nh, block, nw, block).sum(axis=(1, 3))
    count = valid.reshape(nh, block, nw, block).sum(axis=(1, 3))

    return total, count.astype(np.uint16)


def convert_folder(folder, out_path, epsg: int = 25832, pixel: float = 4.0, on_progress=None) -> Path:
    """
    Fasst alle ASC-Dateien unter `folder` zu einer GeoTIFF `out_path` zusammen.
    on_progress(fertig, gesamt, dateiname) wird vor der ersten und nach jeder
    Datei aufgerufen und darf AscCancelled werfen. Gibt out_path zurueck.
    """

    px = float(pixel)

    if px <= 0 or 1000 % px:
        raise AscImportError(tr("Die Pixelgröße muss in 1000 m aufgehen (1, 2, 4, 5, 10 ...)."))

    files = asc_files(folder)

    if not files:
        raise AscImportError(tr("Im Ordner {folder} liegen keine ASC-Dateien.").format(folder=folder))

    boxes = []

    for path in files:
        with open(path, "r", encoding="ascii", errors="replace") as handle:
            head, _ = _read_header(handle)

        ncols, nrows, cell, x0, y0 = _geometry(head, path.name)
        boxes.append((x0, y0, x0 + ncols * cell, y0 + nrows * cell))

    xmin = math.floor(min(b[0] for b in boxes) / 1000) * 1000
    ymin = math.floor(min(b[1] for b in boxes) / 1000) * 1000
    xmax = math.ceil(max(b[2] for b in boxes) / 1000) * 1000
    ymax = math.ceil(max(b[3] for b in boxes) / 1000) * 1000

    width = int(round((xmax - xmin) / px))
    height = int(round((ymax - ymin) / px))

    total = np.zeros((height, width), dtype=np.float64)
    count = np.zeros((height, width), dtype=np.uint16)

    if on_progress:
        on_progress(0, len(files), "")

    for index, path in enumerate(files, 1):
        arr, x0, y0, cell = read_asc(path)
        block = int(round(px / cell))

        if block < 1 or abs(block * cell - px) > 1e-6:
            raise AscImportError(
                tr("{name}: Zellgröße {cell} m passt nicht zur Pixelgröße {px} m.").format(
                    name=path.name, cell=cell, px=px
                )
            )

        nrows = arr.shape[0]

        # Links und unten auf das Pixelraster beschneiden (Zeilen laufen von oben nach unten).
        left = int(round(((-(x0 - xmin)) % px) / cell)) % block
        bottom = int(round(((-(y0 - ymin)) % px) / cell)) % block

        s, n = _block_sums(arr[: nrows - bottom, left:], block)

        ox = int(round((x0 + left * cell - xmin) / px))
        oy = int(round((ymax - (y0 + bottom * cell + s.shape[0] * px)) / px))

        h, w = s.shape
        total[oy:oy + h, ox:ox + w] += s
        count[oy:oy + h, ox:ox + w] += n

        if on_progress:
            on_progress(index, len(files), path.name)

    out = np.full((height, width), NODATA_OUT, dtype=np.float32)
    ok = count > 0
    out[ok] = (total[ok] / count[ok]).astype(np.float32)

    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[33550] = (px, px, 0.0)
    ifd.tagtype[33550] = 12
    ifd[33922] = (0.0, 0.0, 0.0, float(xmin), float(ymax), 0.0)
    ifd.tagtype[33922] = 12
    ifd[34735] = (1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, int(epsg))
    ifd.tagtype[34735] = 3
    ifd[42113] = "-9999"
    ifd.tagtype[42113] = 2

    out_path = Path(out_path)
    tmp = out_path.with_name(out_path.name + ".tmp")

    try:
        Image.fromarray(out, mode="F").save(tmp, format="TIFF", tiffinfo=ifd)
        tmp.replace(out_path)
    finally:
        if tmp.exists():
            tmp.unlink()

    return out_path
