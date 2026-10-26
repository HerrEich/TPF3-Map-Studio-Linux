"""Steigungs-Overlay fuer die Vorschau.

Zeigt, wie steil das Gelaende im Spiel ist (Prozent = Hoehenunterschied je
100 m Strecke). Nach den Biome-Tests von alaric_stormblade wird ein Gebirgs-
Biom ungefaehr ab 24 % Steigung bei 4 m je Pixel erzeugt; die Stufen sind
Schaetzwerte fuer die Vorschau, nicht fuer den Export.
"""

from __future__ import annotations

import numpy as np

# Obergrenzen der Stufen in Prozent: flach, leicht, mittel, steil; darueber
# sehr steil (~ Gebirge).
SLOPE_LIMITS_PERCENT = (4.0, 10.0, 24.0)

# Farben je Stufe (RGB): gruen, gelb, orange, rot.
SLOPE_COLORS = (
    (60, 170, 80),
    (210, 200, 60),
    (230, 140, 40),
    (200, 40, 40),
)
# Die flachste Stufe (unter 4 %) wird nicht eingefaerbt.


def slope_percent(heightmap: np.ndarray, pixel_size_m: float) -> np.ndarray:
    """Steigung in Prozent je Pixel (Betrag des Gefaelles)."""

    h = np.asarray(heightmap, dtype=np.float32)
    if h.ndim != 2 or h.size == 0 or pixel_size_m <= 0:
        return np.zeros(h.shape, dtype=np.float32)

    gy, gx = np.gradient(h, pixel_size_m)
    return (np.hypot(gx, gy) * 100.0).astype(np.float32)


def slope_class(percent: np.ndarray) -> np.ndarray:
    """Stufe 0 (flach) bis 3 (sehr steil) je Pixel."""

    return np.digitize(percent, SLOPE_LIMITS_PERCENT).astype(np.uint8)


def slope_overlay_rgba(
    heightmap: np.ndarray, pixel_size_m: float, alpha: int = 170
) -> np.ndarray:
    """RGBA-Bild; Stufe 0 bleibt durchsichtig."""

    cls = slope_class(slope_percent(heightmap, pixel_size_m))
    out = np.zeros(cls.shape + (4,), dtype=np.uint8)
    for i, color in enumerate(SLOPE_COLORS, start=1):
        m = cls == i
        out[m, :3] = color
        out[m, 3] = alpha
    return out


def slope_shares(heightmap: np.ndarray, pixel_size_m: float) -> dict:
    """Anteile (0-100) je Stufe sowie Maximum in Prozent."""

    p = slope_percent(heightmap, pixel_size_m)
    if p.size == 0:
        return {"flat": 0.0, "mild": 0.0, "medium": 0.0, "steep": 0.0, "max": 0.0}
    cls = slope_class(p)
    n = float(cls.size)
    return {
        "flat": float((cls == 0).sum()) * 100.0 / n,
        "mild": float((cls == 1).sum()) * 100.0 / n,
        "medium": float((cls == 2).sum()) * 100.0 / n,
        "steep": float((cls == 3).sum()) * 100.0 / n,
        "max": float(p.max()),
    }
