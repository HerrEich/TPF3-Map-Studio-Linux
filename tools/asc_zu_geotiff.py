"""
ASC-Kacheln (ESRI ASCII Grid) zu EINER GeoTIFF fuer das Map Studio.

Das Studio erledigt das beim Waehlen eines Ordners mit ASC-Dateien auch selbst
(Heightmap-Dialog, Quelle "DGM1 aus eigenen GeoTIFF-Kacheln"). Dieses Skript ist
die Kommandozeilen-Variante, aufzurufen im Projektordner:

    python tools\\asc_zu_geotiff.py ORDNER_MIT_ASC AUSGABE.tif [--epsg 25832] [--pixel 4]

Benoetigt nur numpy und Pillow.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.heightmap import asc_import  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("ordner")
    ap.add_argument("ausgabe")
    ap.add_argument("--epsg", type=int, default=25832)
    ap.add_argument("--pixel", type=float, default=4.0)
    args = ap.parse_args(argv)

    def progress(done, total, name):
        if name:
            print(f"  {done}/{total} {name}")

    try:
        out = asc_import.convert_folder(
            args.ordner, args.ausgabe, epsg=args.epsg, pixel=args.pixel, on_progress=progress
        )
    except asc_import.AscImportError as exc:
        sys.exit(str(exc))

    print(f"Fertig: {out}")


if __name__ == "__main__":
    main()
