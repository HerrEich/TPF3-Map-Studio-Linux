"""
Gewaesser einer TPF2-Heightmap fuer TPF3 bereinigen (Baustein 3, v0.6.0).

Problem (im Spiel gesehen, 18.10.2026, Halle-Leipzig, 70/250/96 m): Neben
Fluessen liegt flaches Land nur knapp ueber der Wasserhoehe. Jede
Wasserhoehe, die die Fluesse fuellt, setzt dort Pfuetzen und laesst die
Fluesse ueberlaufen; dazu grobe dunkle Flecken (vermutlich die Ufer-
Textur des Spiels auf Land knapp ueber dem Wasser - nicht bestaetigt).

Abhilfe, alles in Metern gerechnet und mit derselben Skala zurueck in
Rohwerte (im Spiel bleiben Min/Max/Wasserhoehe gleich):
  1. Pfuetzen: zusammenhaengende Wasserflaechen unter min_area_px -> Land.
  2. Land: mindestens `margin_m` ueber der Wasserhoehe; direkt am Ufer
     als Rampe ueber `ramp_px` Pixel.
  3. Wasser: mindestens `depth_m` unter der Wasserhoehe, zum Ufer hin
     ebenfalls als Rampe.
Pixel, die weiter als margin_m ueber bzw. depth_m unter dem Wasser liegen,
bleiben unveraendert.

Die Standardwerte sind ein Vorschlag und im Spiel noch nicht geprueft.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from src.heightmap.tpf2_heightmap_import import RAW_MAX, raw_to_meters

DEFAULT_MARGIN_M = 1.5
DEFAULT_DEPTH_M = 2.0
DEFAULT_MIN_AREA_PX = 500     # 500 Pixel = 0,8 ha bei 4 m/Pixel
DEFAULT_RAMP_PX = 3           # 12 m weicher Uebergang

_EIGHT = np.ones((3, 3), dtype=bool)


@dataclass(frozen=True)
class CleanupResult:
    raw: np.ndarray          # uint16, neue Heightmap
    puddles_removed: int     # Anzahl entfernter Wasserflecken
    puddle_px: int           # deren Pixel
    raised_px: int           # angehobene Landpixel
    lowered_px: int          # abgesenkte Wasserpixel
    water_px: int            # Wasserpixel im Ergebnis


def _ring_distance(mask: np.ndarray, max_steps: int) -> np.ndarray:
    """Abstand (1..max_steps) jedes Pixels AUSSERHALB von mask zur Maske,
    in Pixelschritten (8er-Nachbarschaft); weiter weg = max_steps + 1."""
    dist = np.full(mask.shape, max_steps + 1, dtype=np.int16)
    grown = mask
    for step in range(1, max_steps + 1):
        nxt = ndimage.binary_dilation(grown, structure=_EIGHT)
        dist[nxt & ~grown] = step
        grown = nxt
    dist[mask] = 0
    return dist


def remove_puddles(water: np.ndarray, min_area_px: int) -> tuple[np.ndarray, int, int]:
    """Wasserflecken unter min_area_px entfernen. Gibt (Wasser, Anzahl, Pixel)."""
    if min_area_px <= 1 or not water.any():
        return water.copy(), 0, 0
    labels, n = ndimage.label(water, structure=_EIGHT)
    if n == 0:
        return water.copy(), 0, 0
    sizes = np.bincount(labels.ravel())
    small = sizes < min_area_px
    small[0] = False
    puddle = small[labels]
    return water & ~puddle, int(small.sum()), int(puddle.sum())


def clean_water(
    raw: np.ndarray,
    low_m: float,
    high_m: float,
    water_m: float,
    margin_m: float = DEFAULT_MARGIN_M,
    depth_m: float = DEFAULT_DEPTH_M,
    min_area_px: int = DEFAULT_MIN_AREA_PX,
    ramp_px: int = DEFAULT_RAMP_PX,
) -> CleanupResult:
    """Neue Heightmap (gleiche Skala) mit sauberen Ufern."""
    if not low_m <= water_m <= high_m:
        raise ValueError("Wasserhoehe muss zwischen Min und Max liegen")
    if margin_m < 0 or depth_m < 0 or ramp_px < 1:
        raise ValueError("Abstand, Tiefe und Rampe duerfen nicht negativ sein")

    h = raw_to_meters(raw, low_m, high_m)
    water, n_puddles, puddle_px = remove_puddles(h < water_m, min_area_px)
    land = ~water

    # Rampenfaktor 0..1 je nach Abstand zum Ufer (1 = volle Wirkung)
    d_land = _ring_distance(water, ramp_px)       # Land: Abstand zum Wasser
    d_water = _ring_distance(land, ramp_px)       # Wasser: Abstand zum Land
    f_land = np.minimum(d_land, ramp_px).astype(np.float32) / ramp_px
    f_water = np.minimum(d_water, ramp_px).astype(np.float32) / ramp_px

    target_land = np.float32(water_m) + np.float32(margin_m) * f_land
    target_water = np.float32(water_m) - np.float32(depth_m) * f_water
    # am Ufer selbst knapp ueber/unter dem Wasser bleiben
    eps = np.float32(0.05)
    target_land = np.maximum(target_land, np.float32(water_m) + eps)
    target_water = np.minimum(target_water, np.float32(water_m) - eps)

    out = h.copy()
    raise_px = land & (h < target_land)
    lower_px = water & (h > target_water)
    out[raise_px] = target_land[raise_px]
    out[lower_px] = target_water[lower_px]

    scale = RAW_MAX / (high_m - low_m)
    new_raw = np.clip(np.rint((out - np.float32(low_m)) * np.float32(scale)), 0, RAW_MAX)
    new_raw = new_raw.astype(np.uint16)
    return CleanupResult(
        raw=new_raw,
        puddles_removed=n_puddles,
        puddle_px=puddle_px,
        raised_px=int(raise_px.sum()),
        lowered_px=int(lower_px.sum()),
        water_px=int(water.sum()),
    )


def save_heightmap(path: str | Path, raw: np.ndarray) -> Path:
    """16-Bit-Graustufen-PNG speichern (TPF2/TPF3-Format)."""
    p = Path(path)
    Image.fromarray(np.ascontiguousarray(raw, dtype=np.uint16)).save(p)
    return p
