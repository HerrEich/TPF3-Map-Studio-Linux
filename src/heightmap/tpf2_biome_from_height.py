"""
Biom-Maske und Wasser-Maske aus einer TPF2-Heightmap (Baustein 2, v0.6.0).

Grundlage: Rohwerte 0..65535 aus tpf2_heightmap_import (keine Meter).

Biome nach Hoehen-ANTEIL (Entscheidung 18.10.2026, Variante B): Die
Grenzen sind Anteile 0..1 der LAND-Hoehe, gemessen von der Wasserhoehe
(bzw. dem tiefsten Land) bis zur hoechsten Stelle. Ausreisser werden ueber
Perzentile abgeschnitten, damit einzelne Spitzen die Grenzen nicht
verschieben. Das passt auch, wenn die Hoehenskala nur geschaetzt ist.

Fels und Schnee sind KEINE Biome: das Spiel faerbt steile Haenge und
grosse Hoehen selbst (im Spiel gesehen). Die Maske steuert nur den Bewuchs.

Die Standard-Zuordnung in DEFAULT_BANDS ist ein VORSCHLAG und im Spiel
noch nicht geprueft. Grauwerte kommen aus biome_mask.BIOME_GRAY, damit das
Format mit dem OSM-Biom-Export identisch bleibt.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from src.heightmap.biome_mask import BACKGROUND_BIOME, BIOME_GRAY

RAW_MAX = 65535

# (obere Grenze als Anteil der Landhoehe, Biom-Index), aufsteigend, letzte = 1.0
DEFAULT_BANDS: tuple[tuple[float, int], ...] = (
    (0.30, 0),   # Niederung: helle Wiese
    (0.70, 1),   # mittlere Lagen: Wiese mit Baumgruppen
    (1.00, 2),   # oben: dunkle Wiese
)

LOW_PERCENTILE = 0.5
HIGH_PERCENTILE = 99.5


class BiomeBandError(ValueError):
    """Ungueltige Biom-Grenzen. `code` fuer die Oberflaeche."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def meters_to_raw(meters: float, low_m: float, high_m: float) -> float:
    """Meter -> Rohwert (Umkehrung von raw_to_meters), nicht begrenzt."""
    if high_m <= low_m:
        raise BiomeBandError("scale", "Hoechster Wert muss groesser als tiefster sein")
    return (meters - low_m) / (high_m - low_m) * RAW_MAX


def water_mask(raw: np.ndarray, water_raw: float | None) -> np.ndarray:
    """True = geflutet (Rohwert unter der Wasserhoehe). None = kein Wasser."""
    if water_raw is None:
        return np.zeros(raw.shape, dtype=bool)
    return raw < water_raw


def flooded_share(raw: np.ndarray, water_raw: float | None) -> float:
    """Anteil gefluteter Pixel 0..1 (fuer die Vorschau-Anzeige)."""
    if raw.size == 0:
        return 0.0
    return float(water_mask(raw, water_raw).mean())


def validate_bands(bands) -> tuple[tuple[float, int], ...]:
    """Prueft die Grenzen und gibt sie als Tupel zurueck."""
    out = tuple((float(f), int(b)) for f, b in bands)
    if not out:
        raise BiomeBandError("empty", "Keine Biom-Grenzen angegeben")
    last = 0.0
    for frac, biome in out:
        if not 0 <= biome < len(BIOME_GRAY):
            raise BiomeBandError("biome", "Biom-Index %d gibt es nicht" % biome)
        if frac <= last or frac > 1.0:
            raise BiomeBandError("order", "Grenzen muessen aufsteigend zwischen 0 und 1 liegen")
        last = frac
    if abs(out[-1][0] - 1.0) > 1e-9:
        raise BiomeBandError("last", "Die letzte Grenze muss 1,0 sein")
    return out


def land_range(raw: np.ndarray, water_raw: float | None = None) -> tuple[float, float]:
    """(tief, hoch) der Landhoehe in Rohwerten, Ausreisser abgeschnitten."""
    land = raw[~water_mask(raw, water_raw)]
    if land.size == 0:
        return (float(RAW_MAX), float(RAW_MAX))
    lo = float(np.percentile(land, LOW_PERCENTILE))
    hi = float(np.percentile(land, HIGH_PERCENTILE))
    if water_raw is not None:
        lo = max(lo, float(water_raw))
    return lo, max(hi, lo)


def biome_index_from_height(
    raw: np.ndarray,
    bands=DEFAULT_BANDS,
    water_raw: float | None = None,
    water_biome: int = BACKGROUND_BIOME,
) -> np.ndarray:
    """Biom-Index (uint8, 0..4) je Pixel."""
    bands = validate_bands(bands)
    lo, hi = land_range(raw, water_raw)
    span = hi - lo
    if span <= 0:
        frac = np.zeros(raw.shape, dtype=np.float32)
    else:
        frac = np.clip((raw.astype(np.float32) - np.float32(lo)) / np.float32(span), 0.0, 1.0)
    out = np.full(raw.shape, bands[-1][1], dtype=np.uint8)
    # von oben nach unten ueberschreiben: niedrigere Baender gewinnen
    for upper, biome in reversed(bands[:-1]):
        out[frac <= upper] = biome
    out[water_mask(raw, water_raw)] = water_biome
    return out


def biome_gray(indices: np.ndarray) -> np.ndarray:
    """Biom-Index -> 8-Bit-Grauwert fuer den TPF3-Biom-Import."""
    lut = np.array(BIOME_GRAY, dtype=np.uint8)
    return lut[indices]


def save_biome_mask(path: str | Path, gray: np.ndarray) -> Path:
    """Graustufenbild (8 Bit) als PNG speichern."""
    p = Path(path)
    Image.fromarray(np.ascontiguousarray(gray, dtype=np.uint8)).save(p)
    return p
