"""Wasser-Check: Wie viel vom OSM-Wasser wird im Spiel wirklich Wasser?

Das Spiel kennt nur EINEN Wasserspiegel. enforce_osm_water laesst Gewaesser,
die hoeher als Wasserspiegel + Grenze liegen (Baeche, Bergseen), unveraendert.
Dieser Check zaehlt, wie viel der Wassermaske davon betroffen ist und wie
tief die uebrigen Gewaesser im Mittel abgesenkt werden muessen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class WaterCheck:
    water_px: int
    active_px: int
    high_px: int
    high_share: float      # Anteil der Wassermaske ueber der Grenze (0..1)
    mean_cut_m: float      # mittlere Absenkung der aktiven Gewaesser
    p95_cut_m: float       # 95-%-Absenkung der aktiven Gewaesser


def check_water(
    heightmap: np.ndarray,
    water_mask: np.ndarray,
    water_level_m: float,
    max_rise_m: float,
) -> WaterCheck | None:
    """None, wenn die Maske kein Wasser enthaelt oder die Formen nicht passen."""

    if heightmap is None or water_mask is None:
        return None

    if heightmap.shape != water_mask.shape:
        return None

    water = water_mask.astype(bool, copy=False)
    water_px = int(water.sum())

    if water_px == 0:
        return None

    heights = heightmap[water].astype(np.float32, copy=False)
    limit = np.float32(water_level_m + max_rise_m)

    high = heights > limit
    high_px = int(high.sum())

    active = heights[~high]
    active_px = int(active.size)

    if active_px:
        cut = np.maximum(active - np.float32(water_level_m), 0.0)
        mean_cut = float(cut.mean())
        p95_cut = float(np.percentile(cut, 95))
    else:
        mean_cut = 0.0
        p95_cut = 0.0

    return WaterCheck(
        water_px=water_px,
        active_px=active_px,
        high_px=high_px,
        high_share=high_px / water_px,
        mean_cut_m=mean_cut,
        p95_cut_m=p95_cut,
    )
