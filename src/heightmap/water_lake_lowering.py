"""
Hoeher gelegene Seen sanft mitsenken ("Gelaende sanft mitsenken").

Problem: TPF2/TPF3 kennen nur EINEN Wasserspiegel. Liegt ein See hoeher als
dieser (Beispiel Tegernsee/Schliersee: der Schliersee liegt rund 50 m ueber dem
Tegernsee), gibt es zwei schlechte Loesungen: der See bleibt ausserhalb des
Wasserspiegels (trocken), oder man drueckt ihn samt direktem Umfeld nach unten
und bekommt rund um den See eine steile Kante (Steilkueste).

Dieses Modul senkt das Gelaende um jeden solchen See um dessen Hoehe ueber dem
Wasserspiegel ab und laesst die Absenkung mit dem Abstand zum Ufer sanft auf
null auslaufen (glatte Ueberblendung ueber `falloff_m` Meter). Der See selbst
liegt danach genau auf dem Wasserspiegel, weit entfernte Berge bleiben
unveraendert, die Neigung der Absenkung ist hoechstens drop / falloff_m.

Die Wirkung ist auf einem groben Raster berechnet (wie beim Gefaelle-Ausgleich)
und erst danach auf die volle Aufloesung hochgerechnet.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, distance_transform_edt, label

DEFAULT_FALLOFF_M = 1500.0
DEFAULT_MIN_ABOVE_M = 3.0          # Seen hoechstens so viel ueber Wasser: nicht anfassen
DEFAULT_MIN_AREA_PX = 200          # kleinere Gewaesser sind kein Bezug
FIELD_PIXEL_SIZE_M = 32.0


def _smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lake_drop_field(
    heightmap: np.ndarray,
    water_mask: np.ndarray,
    water_level_m: float,
    pixel_size_m: float,
    falloff_m: float = DEFAULT_FALLOFF_M,
    min_above_m: float = DEFAULT_MIN_ABOVE_M,
    max_drop_m: float | None = None,
    min_area_px: int = DEFAULT_MIN_AREA_PX,
    field_pixel_size_m: float = FIELD_PIXEL_SIZE_M,
) -> np.ndarray | None:
    """Absenkung in Metern je Pixel (float32, >= 0) oder None, wenn nichts zu tun ist.

    Jeder zusammenhaengende See mit mindestens `min_area_px` Pixeln, dessen
    mittlere Hoehe mehr als `min_above_m` ueber `water_level_m` liegt, liefert
    eine Absenkung `drop = hoehe - water_level_m` (bei `max_drop_m` gekappt),
    die vom Ufer aus ueber `falloff_m` Meter glatt auf null ausblendet. Wo sich
    mehrere Seen ueberlagern, gilt das Maximum.
    """
    if heightmap.shape != water_mask.shape:
        raise ValueError("heightmap und water_mask müssen dieselbe Form haben")
    if falloff_m <= 0:
        raise ValueError("falloff_m muss größer als 0 sein")

    h, w = heightmap.shape
    factor = max(1, int(round(field_pixel_size_m / pixel_size_m)))
    low_h, low_w = -(-h // factor), -(-w // factor)

    # Wasser auf das grobe Raster verdichten (Zelle = Wasser, wenn die Mehrheit Wasser ist)
    pad_r, pad_c = (-h) % factor, (-w) % factor
    mask = np.pad(water_mask, ((0, pad_r), (0, pad_c)))
    height = np.pad(heightmap.astype(np.float32), ((0, pad_r), (0, pad_c)))
    blocks = mask.reshape(low_h, factor, low_w, factor)
    counts = blocks.sum(axis=(1, 3))
    low_water = counts * 2 > factor * factor
    height_sum = (height * mask).reshape(low_h, factor, low_w, factor).sum(axis=(1, 3), dtype=np.float64)
    low_height = np.where(counts > 0, height_sum / np.maximum(counts, 1), 0.0)

    labels, n = label(low_water)
    if n == 0:
        return None

    cell_m = factor * pixel_size_m
    min_cells = max(1, int(min_area_px / (factor * factor)))
    field = np.zeros((low_h, low_w), dtype=np.float32)
    radius_cells = int(np.ceil(falloff_m / cell_m)) + 1
    found = False

    objects = _bounding_slices(labels, n)
    for index, sl in enumerate(objects, start=1):
        if sl is None:
            continue
        r0 = max(0, sl[0].start - radius_cells)
        r1 = min(low_h, sl[0].stop + radius_cells)
        c0 = max(0, sl[1].start - radius_cells)
        c1 = min(low_w, sl[1].stop + radius_cells)
        sub_labels = labels[r0:r1, c0:c1] == index
        cells = int(sub_labels.sum())
        if cells < min_cells:
            continue
        lake_h = float(low_height[r0:r1, c0:c1][sub_labels].mean())
        drop = lake_h - water_level_m
        if drop <= min_above_m:
            continue
        if max_drop_m is not None:
            drop = min(drop, float(max_drop_m))

        distance = distance_transform_edt(~sub_labels) * cell_m
        weight = _smoothstep(1.0 - distance / falloff_m).astype(np.float32)
        part = np.float32(drop) * weight
        view = field[r0:r1, c0:c1]
        np.maximum(view, part, out=view)
        found = True

    if not found:
        return None

    image = Image.fromarray(field).resize((low_w * factor, low_h * factor), Image.Resampling.BILINEAR)
    full = np.array(image, dtype=np.float32)[:h, :w]
    return np.ascontiguousarray(full)


def _bounding_slices(labels: np.ndarray, n: int):
    from scipy.ndimage import find_objects
    return find_objects(labels, max_label=n)


def lower_terrain_around_lakes(
    heightmap: np.ndarray,
    water_mask: np.ndarray,
    water_level_m: float,
    pixel_size_m: float,
    falloff_m: float = DEFAULT_FALLOFF_M,
    min_above_m: float = DEFAULT_MIN_ABOVE_M,
    max_drop_m: float | None = None,
    min_area_px: int = DEFAULT_MIN_AREA_PX,
) -> np.ndarray:
    """Liefert eine NEUE Kopie der Hoehen mit sanft abgesenktem Umfeld hoher Seen."""
    drop = lake_drop_field(
        heightmap, water_mask, water_level_m, pixel_size_m,
        falloff_m=falloff_m, min_above_m=min_above_m,
        max_drop_m=max_drop_m, min_area_px=min_area_px,
    )
    if drop is None:
        return heightmap.copy()
    result = heightmap.astype(np.float32) - drop
    return result.astype(heightmap.dtype, copy=False)
