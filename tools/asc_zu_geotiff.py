"""
ASC-Kacheln (ESRI ASCII Grid) zu EINER GeoTIFF fuer das Map Studio.

Aufruf:
    python asc_zu_geotiff.py ORDNER_MIT_ASC AUSGABE.tif [--epsg 25832] [--pixel 4]

- liest alle *.asc im Ordner (Ueberlappungen werden gemittelt),
- mittelt auf --pixel Meter (Standard 4, das Studio rechnet ohnehin mit 4 m),
- richtet den Ausschnitt an ganzen Kilometern aus,
- schreibt eine GeoTIFF mit Koordinatensystem EPSG (25832 = ETRS89 / UTM 32N).

Die Ausgabedatei danach in einen leeren Ordner legen und im Heightmap-Dialog
"DGM1 aus eigenen GeoTIFF-Kacheln (Ordner)" waehlen.
Benoetigt nur numpy und Pillow (sind im Studio-Projekt vorhanden).
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, TiffImagePlugin

NODATA_OUT = -9999.0


def read_asc(path):
    with open(path, "r", encoding="ascii", errors="replace") as handle:
        head = {}
        pos = 0

        while len(head) < 6:
            line = handle.readline()

            if not line:
                break

            parts = line.split()

            if len(parts) >= 2 and parts[0].replace("_", "").isalpha():
                head[parts[0].lower()] = float(parts[1])
                pos = handle.tell()
            else:
                break

        handle.seek(pos)
        text = handle.read()

    ncols = int(head["ncols"])
    nrows = int(head["nrows"])
    cell = float(head["cellsize"])

    if "xllcorner" in head:
        x0 = head["xllcorner"]
    else:
        x0 = head["xllcenter"] - cell / 2.0

    if "yllcorner" in head:
        y0 = head["yllcorner"]
    else:
        y0 = head["yllcenter"] - cell / 2.0

    nodata = head.get("nodata_value", -9999.0)

    try:
        values = np.fromstring(text, dtype=np.float32, sep=" ")
    except Exception:  # noqa: BLE001
        values = np.array(text.split(), dtype=np.float32)

    if values.size != ncols * nrows:
        raise ValueError(
            f"{Path(path).name}: {values.size} Werte, erwartet {ncols * nrows}"
        )

    arr = values.reshape(nrows, ncols)
    arr[np.isclose(arr, nodata)] = np.nan

    return arr, x0, y0, cell


def block_mean(arr, block):
    if block <= 1:
        return arr

    h, w = arr.shape
    nh, nw = h // block, w // block
    arr = arr[: nh * block, : nw * block]
    valid = np.isfinite(arr)
    total = np.where(valid, arr, 0.0).reshape(nh, block, nw, block).sum(axis=(1, 3))
    count = valid.reshape(nh, block, nw, block).sum(axis=(1, 3))

    return total, count


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("ordner")
    ap.add_argument("ausgabe")
    ap.add_argument("--epsg", type=int, default=25832)
    ap.add_argument("--pixel", type=float, default=4.0)
    args = ap.parse_args(argv)

    px = float(args.pixel)

    if 1000 % px:
        sys.exit("--pixel muss in 1000 aufgehen (1, 2, 4, 5, 10 ...)")

    files = sorted(Path(args.ordner).glob("*.asc"))

    if not files:
        sys.exit(f"Keine .asc-Dateien in {args.ordner}")

    # 1) Kopfdaten: Gesamtausdehnung
    boxes = []

    for path in files:
        with open(path, "r", encoding="ascii", errors="replace") as handle:
            head = {}
            for _ in range(6):
                parts = handle.readline().split()
                if len(parts) >= 2:
                    head[parts[0].lower()] = float(parts[1])
        cell = head["cellsize"]
        x0 = head.get("xllcorner", head.get("xllcenter", 0) - cell / 2)
        y0 = head.get("yllcorner", head.get("yllcenter", 0) - cell / 2)
        boxes.append((x0, y0, x0 + head["ncols"] * cell, y0 + head["nrows"] * cell))

    xmin = math.floor(min(b[0] for b in boxes) / 1000) * 1000
    ymin = math.floor(min(b[1] for b in boxes) / 1000) * 1000
    xmax = math.ceil(max(b[2] for b in boxes) / 1000) * 1000
    ymax = math.ceil(max(b[3] for b in boxes) / 1000) * 1000

    width = int(round((xmax - xmin) / px))
    height = int(round((ymax - ymin) / px))

    print(f"{len(files)} Dateien, Ausschnitt {xmin:.0f}/{ymin:.0f} bis {xmax:.0f}/{ymax:.0f}, "
          f"{width} x {height} Pixel a {px:g} m")

    total = np.zeros((height, width), dtype=np.float64)
    count = np.zeros((height, width), dtype=np.uint16)

    # 2) Kachel fuer Kachel einfuegen
    for i, path in enumerate(files, 1):
        arr, x0, y0, cell = read_asc(path)
        block = int(round(px / cell))

        if block < 1 or abs(block * cell - px) > 1e-6:
            sys.exit(f"{path.name}: Zellgroesse {cell} m passt nicht zu --pixel {px:g}")

        nrows, ncols = arr.shape

        # Zeilen laufen von oben nach unten. Links und unten auf das Pixelraster beschneiden.
        left = int(round(((-(x0 - xmin)) % px) / cell)) % block
        bottom = int(round(((-(y0 - ymin)) % px) / cell)) % block

        arr = arr[: nrows - bottom, left:]
        s, n = block_mean(arr, block)

        ox = int(round((x0 + left * cell - xmin) / px))
        oy_top = ymax - (y0 + bottom * cell + s.shape[0] * px)
        oy = int(round(oy_top / px))

        h, w = s.shape
        total[oy:oy + h, ox:ox + w] += s
        count[oy:oy + h, ox:ox + w] += n.astype(np.uint16)

        print(f"  {i}/{len(files)} {path.name}")

    # 3) Mittelwert, Luecken = nodata
    out = np.full((height, width), NODATA_OUT, dtype=np.float32)
    ok = count > 0
    out[ok] = (total[ok] / count[ok]).astype(np.float32)

    # 4) GeoTIFF schreiben
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[33550] = (px, px, 0.0)
    ifd.tagtype[33550] = 12
    ifd[33922] = (0.0, 0.0, 0.0, float(xmin), float(ymax), 0.0)
    ifd.tagtype[33922] = 12
    ifd[34735] = (1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, int(args.epsg))
    ifd.tagtype[34735] = 3
    ifd[42113] = "-9999"
    ifd.tagtype[42113] = 2

    Image.fromarray(out, mode="F").save(args.ausgabe, tiffinfo=ifd)

    print(f"Fertig: {args.ausgabe} ({100.0 * ok.mean():.0f} % der Flaeche mit Daten)")


if __name__ == "__main__":
    main()
