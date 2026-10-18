"""
TPF2-Heightmap einlesen (Baustein 1 fuer den TPF2-Kartenimport, v0.6.0).

Eine TPF2-Heightmap ist ein Graustufen-PNG im selben Raster wie die
TPF3-Heightmaps des Studios: 4 m pro Pixel, Pixelgroesse = Meter / 4 + 1
(geprueft am 18.10.2026: heightmap_halle_leipzig_v2.png, 2689 x 13441 px,
16 Bit, laedt direkt im TPF3-Karteneditor).

Die PNG enthaelt KEINE Meter: 0 = tiefster, 65535 = hoechster Wert der
beim TPF2-Import eingestellten Hoehenskala. Hoehenskala und Wasserhoehe
muss der Nutzer angeben (automatische Erkennung der Wasserhoehe aus der
Werteverteilung war beim Test nicht verlaesslich).

Dieses Modul hat keine Oberflaeche und kein tr(); die Fehlermeldungen
tragen einen festen `code`, den die Oberflaeche uebersetzt anzeigen kann.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from src.gui.map_size_presets import ALL_MAP_SIZES, METERS_PER_PIXEL, MapSize

RAW_MAX = 65535


class Tpf2HeightmapError(ValueError):
    """Datei ist keine brauchbare Heightmap. `code` fuer die Oberflaeche."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Tpf2Heightmap:
    path: Path
    raw: np.ndarray                 # uint16, Form (Hoehe, Breite)
    map_sizes: tuple[MapSize, ...]  # passende Kartengroessen (leer = keine)
    rotated: bool                   # True = Bild liegt quer zur Kartengroesse
    is_8bit: bool                   # True = Quelle war 8 Bit (auf 16 Bit gestreckt)

    @property
    def width_px(self) -> int:
        return int(self.raw.shape[1])

    @property
    def height_px(self) -> int:
        return int(self.raw.shape[0])

    @property
    def width_m(self) -> float:
        return (self.width_px - 1) * METERS_PER_PIXEL

    @property
    def height_m(self) -> float:
        return (self.height_px - 1) * METERS_PER_PIXEL

    @property
    def map_size(self) -> MapSize | None:
        """Erste passende Kartengroesse oder None."""
        return self.map_sizes[0] if self.map_sizes else None

    @property
    def raw_min(self) -> int:
        return int(self.raw.min())

    @property
    def raw_max(self) -> int:
        return int(self.raw.max())


def find_map_sizes(width_px: int, height_px: int) -> tuple[tuple[MapSize, ...], bool]:
    """Kartengroessen mit genau dieser Pixelgroesse.

    Gibt (Treffer, gedreht) zurueck. Gedreht = nur mit vertauschten
    Seiten gefunden. Mehrere Treffer sind moeglich (Winzig 1:3 und 1:4
    haben laut Wiki dieselbe Groesse) - hier wird nicht geraten.
    """
    direct = tuple(m for m in ALL_MAP_SIZES
                   if m.width_px == width_px and m.height_px == height_px)
    if direct:
        return direct, False
    swapped = tuple(m for m in ALL_MAP_SIZES
                    if m.width_px == height_px and m.height_px == width_px)
    return swapped, bool(swapped)


def _to_uint16(im: Image.Image) -> tuple[np.ndarray, bool]:
    mode = im.mode
    if mode in ("I;16", "I;16B", "I;16L"):
        return np.array(im, dtype=np.uint16), False
    if mode == "I":
        a = np.array(im)
        if a.min() < 0 or a.max() > RAW_MAX:
            raise Tpf2HeightmapError(
                "range", "Werte ausserhalb 0..65535 (kein 16-Bit-Graustufenbild)")
        return a.astype(np.uint16), False
    if mode == "L":
        a = np.array(im, dtype=np.uint16)
        return a * 257, True   # 255 -> 65535
    raise Tpf2HeightmapError(
        "mode", "Kein Graustufenbild (Bildmodus %s); erwartet wird 16 Bit grau" % mode)


def load_tpf2_heightmap(path: str | Path) -> Tpf2Heightmap:
    """PNG laden und pruefen. Wirft Tpf2HeightmapError bei Problemen."""
    p = Path(path)
    if not p.is_file():
        raise Tpf2HeightmapError("missing", "Datei nicht gefunden: %s" % p)
    old_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None   # grosse Karten (36 Mio. Pixel) zulassen
    try:
        try:
            im = Image.open(p)
            im.load()
        except Exception as exc:  # noqa: BLE001 - jede Lesefehlerart melden
            raise Tpf2HeightmapError("read", "Bild nicht lesbar: %s" % exc) from exc
        raw, is_8bit = _to_uint16(im)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
    if raw.ndim != 2 or raw.shape[0] < 2 or raw.shape[1] < 2:
        raise Tpf2HeightmapError("shape", "Bild ist zu klein oder hat mehrere Kanaele")
    sizes, rotated = find_map_sizes(raw.shape[1], raw.shape[0])
    return Tpf2Heightmap(path=p, raw=raw, map_sizes=sizes,
                         rotated=rotated, is_8bit=is_8bit)


def raw_to_meters(raw: np.ndarray, low_m: float, high_m: float) -> np.ndarray:
    """Rohwerte in Meter: 0 -> low_m, 65535 -> high_m (float32)."""
    if high_m <= low_m:
        raise Tpf2HeightmapError("scale", "Hoechster Wert muss groesser als tiefster sein")
    scale = (high_m - low_m) / RAW_MAX
    return (raw.astype(np.float32) * np.float32(scale) + np.float32(low_m))
