"""
Netz fuer die 3D-Vorschau: Raster herunterrechnen, Hoehen ueber Wasser,
Zonenfarben pro Punkt. Reine Berechnung ohne Qt.
"""

from __future__ import annotations

import base64

import numpy as np

from src.heightmap.height_zones import (
    COLOR_GREEN,
    COLOR_ROCK,
    COLOR_SNOW,
    classify_zones,
    normalize_limits,
)

MESH_SIZE = 512

# Fenster, das der Karteneditor von TPF3 beim Import annimmt (Meter).
EDITOR_MIN_M = -100.0
EDITOR_MAX_M = 3177.0


def target_shape(rows: int, cols: int, size: int = MESH_SIZE) -> tuple[int, int]:
    """Zielgroesse: laengste Seite hoechstens size, nie hochgerechnet."""
    scale = min(1.0, float(size) / float(max(rows, cols)))
    return (
        max(2, min(rows, int(round(rows * scale)))),
        max(2, min(cols, int(round(cols * scale)))),
    )


def downsample_heights(heights, size: int = MESH_SIZE) -> np.ndarray:
    array = np.asarray(heights, dtype=np.float32)
    if array.ndim != 2 or min(array.shape) < 2:
        raise ValueError("Raster braucht mindestens 2 x 2 Punkte")
    rows, cols = array.shape
    target_rows, target_cols = target_shape(rows, cols, size)
    row_index = np.linspace(0, rows - 1, target_rows).round().astype(int)
    col_index = np.linspace(0, cols - 1, target_cols).round().astype(int)
    return array[np.ix_(row_index, col_index)]


def resample_index(index, rows: int, cols: int) -> np.ndarray:
    """Biom-Raster auf die Netzgroesse bringen (naechster Nachbar, uint8)."""
    array = np.asarray(index)
    if array.ndim != 2 or min(array.shape) < 1:
        raise ValueError("Biom-Raster muss zweidimensional sein")
    row_index = np.linspace(0, array.shape[0] - 1, rows).round().astype(int)
    col_index = np.linspace(0, array.shape[1] - 1, cols).round().astype(int)
    return np.ascontiguousarray(array[np.ix_(row_index, col_index)].astype(np.uint8))


def resample_mask(mask, rows: int, cols: int, min_share: float = 0.08) -> np.ndarray:
    """
    Wassermaske auf die Netzgroesse bringen. Eine Netzzelle gilt als Wasser,
    wenn mindestens `min_share` ihrer Quellpixel Wasser sind, damit schmale
    Fluesse beim Verkleinern nicht verschwinden. Ergebnis uint8 (0/1).
    """
    from PIL import Image

    array = np.asarray(mask).astype(bool)
    if array.ndim != 2 or min(array.shape) < 1:
        raise ValueError("Maske muss zweidimensional sein")
    image = Image.fromarray(array.astype(np.uint8) * 255, mode="L")
    small = np.asarray(image.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32) / 255.0
    return np.ascontiguousarray((small >= min_share).astype(np.uint8))


def biome_legend(index, palette, names) -> list[dict]:
    """Vorkommende Biome mit Farbe und Flaechenanteil in Prozent."""
    array = np.asarray(index)
    counts = np.bincount(array.ravel(), minlength=len(names))
    total = max(1, int(counts.sum()))
    return [
        {
            "id": i,
            "name": str(names[i]),
            "rgb": [int(v) for v in palette[i]],
            "pct": 100.0 * float(counts[i]) / total,
        }
        for i in range(min(len(names), len(counts)))
        if counts[i] > 0
    ]


def scale_segments(
    above,
    rock_m: float,
    snow_m: float,
    index=None,
    palette=None,
    names=None,
    bins: int = 64,
    low: float | None = None,
    high: float | None = None,
) -> list[dict]:
    """
    Farbabschnitte der Hoehenskala von unten nach oben (Meter ueber Wasser):
    Wasser (blau), darueber je Hoehenstufe das dort haeufigste Biom (ohne
    Biome gruen), ab der Felsgrenze Fels, ab der Schneegrenze Schnee.
    Nur der Bereich, den das Gelaende wirklich erreicht, wird gefuellt.
    """
    above = np.asarray(above, dtype=np.float32)
    low = float(above.min()) if low is None else float(low)
    high = float(above.max()) if high is None else float(high)
    segments: list[dict] = []

    def add(a, b, rgb, name):
        if b <= a:
            return
        if segments and segments[-1]["rgb"] == list(rgb) and abs(segments[-1]["b"] - a) < 1e-6:
            segments[-1]["b"] = float(b)
        else:
            segments.append({"a": float(a), "b": float(b), "rgb": [int(v) for v in rgb], "name": name})

    if low < 0:
        add(low, min(0.0, high), (47, 95, 208), "Wasser")
    if high <= 0:
        return segments

    edges = np.linspace(0.0, high, bins + 1)
    flat = above.ravel()
    flat_index = None if index is None else np.asarray(index).ravel()
    for k in range(bins):
        a, b = float(edges[k]), float(edges[k + 1])
        mid = (a + b) / 2.0
        if mid >= snow_m:
            add(a, b, COLOR_SNOW, "Schnee")
        elif mid >= rock_m:
            add(a, b, COLOR_ROCK, "Fels")
        elif flat_index is not None and palette is not None:
            sel = (flat > a) & (flat <= b) if k else (flat > a) & (flat <= b)
            if np.any(sel):
                counts = np.bincount(flat_index[sel], minlength=len(palette))
                biome = int(np.argmax(counts))
                add(a, b, palette[biome], str(names[biome]) if names else f"Biom {biome}")
            elif segments:
                add(a, b, segments[-1]["rgb"], segments[-1]["name"])
        else:
            add(a, b, COLOR_GREEN, "Land")
    return segments


def build_mesh_payload(
    heights,
    water_level_m: float,
    rock_m: float,
    snow_m: float,
    pixel_size_m: float,
    size: int = MESH_SIZE,
    show_zones: bool = True,
    biome_index=None,
    biome_palette=None,
    biome_names=None,
    water_mask=None,
) -> dict:
    """Daten fuer die Web-Seite. Hoehen sind Meter ueber dem Wasserspiegel."""
    source = np.asarray(heights, dtype=np.float32)
    small = downsample_heights(source, size)
    rows, cols = small.shape

    above = small - np.float32(water_level_m)
    zones = classify_zones(small, water_level_m, rock_m, snow_m)
    palette = np.array([COLOR_GREEN, COLOR_ROCK, COLOR_SNOW], dtype=np.uint8)
    colors = palette[zones]
    if not show_zones:
        colors = np.full(colors.shape, 185, dtype=np.uint8)

    cell_m = float(pixel_size_m) * (source.shape[1] - 1) / (cols - 1)

    rock_limit, snow_limit = normalize_limits(rock_m, snow_m)
    # Hoechste/tiefste Stelle aus dem vollen Raster, nicht aus dem verkleinerten
    # Netz: sonst fehlen schmale Gipfel in der Skala und in den Warnungen.
    abs_min = float(source.min())
    abs_max = float(source.max())
    full_min_above = abs_min - float(water_level_m)
    full_max_above = abs_max - float(water_level_m)

    biome_payload = {}
    small_index = None
    palette_array = None
    if biome_index is not None and biome_palette is not None:
        small_index = resample_index(biome_index, rows, cols)
        palette_array = np.asarray(biome_palette, dtype=np.uint8)
        biome_colors = palette_array[np.clip(small_index, 0, len(palette_array) - 1)]
        biome_payload = {
            "biome_colors_b64": base64.b64encode(
                np.ascontiguousarray(biome_colors).tobytes()
            ).decode("ascii"),
            "biomes": biome_legend(
                biome_index, palette_array, biome_names or [f"Biom {i}" for i in range(len(palette_array))]
            ),
        }

    water_payload = {}
    if water_mask is not None:
        small_water = resample_mask(water_mask, rows, cols)
        if small_water.any():
            water_payload = {
                "water_b64": base64.b64encode(small_water.tobytes()).decode("ascii"),
            }

    return {
        **biome_payload,
        **water_payload,
        "scale_segments": scale_segments(
            above,
            rock_limit,
            snow_limit,
            index=small_index,
            palette=palette_array,
            names=biome_names,
            low=full_min_above,
            high=full_max_above,
        ),
        "water_level_m": float(water_level_m),
        "rock_above_m": float(rock_limit),
        "snow_above_m": float(snow_limit),
        "abs_min_m": abs_min,
        "abs_max_m": abs_max,
        "editor_min_m": EDITOR_MIN_M,
        "editor_max_m": EDITOR_MAX_M,
        "rows": int(rows),
        "cols": int(cols),
        "cell_m": cell_m,
        "max_above_m": full_max_above,
        "min_above_m": full_min_above,
        "heights_b64": base64.b64encode(
            np.ascontiguousarray(above.astype("<f4")).tobytes()
        ).decode("ascii"),
        "colors_b64": base64.b64encode(
            np.ascontiguousarray(colors).tobytes()
        ).decode("ascii"),
    }