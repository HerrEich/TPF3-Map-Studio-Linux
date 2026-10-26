"""Kennzahlen zum Stauchfaktor (fuer den Hinweis im Rechteck-Dialog).

Die Hoehenkarte hat im Spiel immer 4 m je Pixel. Bei gestauchter Karte
entspricht ein Pixel entsprechend mehr echtem Gelaende. Fluesse und Kanaele
werden mit fester Pixelbreite gezeichnet (siehe water_terrain_blend), werden
also NICHT mit dem Stauchfaktor schmaler.
"""

from __future__ import annotations

from dataclasses import dataclass

METERS_PER_PIXEL = 4.0
WATERWAY_WIDTH_PX = 3


@dataclass(frozen=True)
class ScaleInfo:
    real_m_per_pixel: float      # echtes Gelaende je Pixel
    river_width_game_m: float    # gezeichnete Flussbreite im Spiel
    river_width_real_m: float    # so breit wuerde der Fluss in echt entsprechen
    height_example_real_m: float
    height_example_game_m: float


def scale_info(scale_factor: float, height_scale: float) -> ScaleInfo:
    scale = max(float(scale_factor or 1.0), 0.0001)
    hs = float(height_scale or 1.0)
    river_game = METERS_PER_PIXEL * WATERWAY_WIDTH_PX

    return ScaleInfo(
        real_m_per_pixel=METERS_PER_PIXEL * scale,
        river_width_game_m=river_game,
        river_width_real_m=river_game * scale,
        height_example_real_m=1000.0,
        height_example_game_m=1000.0 * hs,
    )
