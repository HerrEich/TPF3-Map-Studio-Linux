"""Vorschlag fuer die Masken Berge, Seen und Saempfe aus der Hoehenkarte.

Der Karteneditor von TPF3 nimmt im Biome-Tab Masken fuer Berge, Seen und
Saempfe. Wie das Spiel sie bildet, ist nicht bekannt. Die Test-Masken von
alaric_stormblade (zwei Karten, Oktober 2026) sind glatte, fleckige Gebiete,
die nur grob an der Hoehenkarte haengen. Die Regeln hier sind darum
Naeherungen, an diesen Testkarten abgestimmt:

- Berge: die hoechsten ~35 % der geglaetteten Hoehe (Glaettung ~1,5 % der
  Kartenbreite). Deckung mit den Test-Masken (IoU): 0,62 und 0,80.
- Seen: flaches Wasser kurz unter dem Wasserspiegel (7 % bis 23 % der Tiefe
  zwischen Wasserspiegel und tiefstem Punkt); der tiefste Bereich (Meer,
  abgeschnittene Tiefen) zaehlt nicht dazu. IoU nur ~0,35.
- Saempfe: flaches Land direkt am Wasserspiegel (bis etwa 0,6 % ueber der
  Wasserhoehe, auf die Tiefe bezogen), ohne Seen. IoU nur ~0,34.

Die Masken sind ein Ausgangspunkt zum Nachmalen, kein fertiges Ergebnis.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

DEFAULT_MOUNTAIN_SHARE = 0.35
MOUNTAIN_SIGMA_FRACTION = 0.018   # von der groesseren Kartenseite

LAKE_DEPTH_FROM = 0.07     # Anteil der Tiefe (Wasserspiegel -> tiefster Punkt)
LAKE_DEPTH_TO = 0.23
SWAMP_ABOVE = 0.006
EDGE_SIGMA_FRACTION = 0.004

WORK_SIZE_PX = 1024        # grosse Karten werden fuer die Rechnung verkleinert

MASK_NAMES = ("mountains", "lakes", "swamps")


def _downscale(a: np.ndarray, size: int) -> tuple[np.ndarray, float]:
    step = max(1, max(a.shape) // size)
    return a[::step, ::step], float(step)


def _upscale_mask(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if mask.shape == shape:
        return mask
    zoom = (shape[0] / mask.shape[0], shape[1] / mask.shape[1])
    out = ndi.zoom(mask.astype(np.float32), zoom, order=1)
    out = out[: shape[0], : shape[1]]
    if out.shape != shape:
        padded = np.zeros(shape, dtype=np.float32)
        padded[: out.shape[0], : out.shape[1]] = out
        out = padded
    return out > 0.5


def suggest_masks(
    heightmap: np.ndarray,
    water_level_m: float,
    mountain_share: float = DEFAULT_MOUNTAIN_SHARE,
) -> dict[str, np.ndarray]:
    """Gibt {"mountains", "lakes", "swamps"} als Bool-Raster der Groesse der
    Hoehenkarte zurueck (leere Masken, wenn die Karte zu klein oder flach
    ist)."""

    h_full = np.asarray(heightmap, dtype=np.float32)
    shape = h_full.shape
    empty = {k: np.zeros(shape, dtype=bool) for k in MASK_NAMES}

    if h_full.ndim != 2 or min(shape) < 8:
        return empty

    h, _ = _downscale(h_full, WORK_SIZE_PX)
    longer = float(max(h.shape))

    result = dict(empty)

    # Berge: hoechster Anteil der geglaetteten Hoehe
    share = float(np.clip(mountain_share, 0.0, 1.0))
    if share > 0.0 and float(h.max() - h.min()) > 1e-6:
        blurred = ndi.gaussian_filter(h, MOUNTAIN_SIGMA_FRACTION * longer)
        limit = np.percentile(blurred, 100.0 * (1.0 - share))
        result["mountains"] = _upscale_mask(blurred > limit, shape)

    # Seen und Saempfe: bezogen auf die Tiefe unter dem Wasserspiegel
    low = float(h.min())
    depth = float(water_level_m) - low
    if depth > 1.0:
        u = (h - low) / depth          # 0 = tiefster Punkt, 1 = Wasserspiegel
        sigma = EDGE_SIGMA_FRACTION * longer

        lake = (u > 1.0 - LAKE_DEPTH_TO) & (u < 1.0 - LAKE_DEPTH_FROM)
        swamp = (u >= 1.0 - LAKE_DEPTH_FROM) & (u < 1.0 + SWAMP_ABOVE)

        lake = ndi.gaussian_filter(lake.astype(np.float32), sigma) > 0.5
        swamp = ndi.gaussian_filter(swamp.astype(np.float32), sigma * 1.3) > 0.5
        swamp &= ~lake

        result["lakes"] = _upscale_mask(lake, shape)
        result["swamps"] = _upscale_mask(swamp, shape)
        result["swamps"] &= ~result["lakes"]

    return result


def mask_shares(masks: dict[str, np.ndarray]) -> dict[str, float]:
    """Anteil jeder Maske an der Karte in Prozent."""

    return {
        k: (float(v.mean()) * 100.0 if v.size else 0.0)
        for k, v in masks.items()
    }


def write_masks(masks: dict[str, np.ndarray], base_path) -> list[Path]:
    """Schreibt <name>_mountains.png, _lakes.png, _swamps.png (8 Bit, 0/255,
    wie die Masken im Karteneditor). Gibt die Pfade zurueck."""

    from PIL import Image

    base = Path(base_path)
    base.parent.mkdir(parents=True, exist_ok=True)
    stem = base.with_suffix("") if base.suffix.lower() == ".png" else base

    paths = []
    for name in MASK_NAMES:
        path = stem.with_name(f"{stem.name}_{name}.png")
        Image.fromarray((masks[name] * 255).astype(np.uint8), mode="L").save(path)
        paths.append(path)
    return paths
