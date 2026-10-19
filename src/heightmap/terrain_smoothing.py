"""
Geländeglättung gegen Treppenstufen und Facetten.

Das Copernicus-Höhenmodell hat nur etwa 30 m pro Pixel, die Heightmap für das
Spiel aber 4 m pro Pixel. Beim Hochrechnen (bilineare Interpolation) entstehen
ebene Flächen von etwa 30 m Kantenlänge mit Knicken dazwischen: Hänge sehen im
Spiel wie Treppen oder Kristallflächen aus. Eine leichte Gauß-Glättung in der
Größenordnung der Datenauflösung entfernt das, ohne das Relief zu verändern.
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy.ndimage import gaussian_filter

from src.core.task_control import TaskControl

# Ab so vielen Pixeln lohnt es sich, das Raster in Streifen auf mehreren
# Kernen zu glaetten (scipy gibt dabei die GIL frei).
PARALLEL_MIN_PIXELS = 2_000_000
STRIPE_ROWS = 512

# Auf dieser Größenordnung liegt die echte Datenauflösung (Copernicus GLO-30).
DEFAULT_SMOOTHING_SIGMA_M = 15.0


def _worker_count(workers: int | None) -> int:

    if workers is not None:
        return max(1, int(workers))

    return max(1, min(8, os.cpu_count() or 1))


def smooth_terrain(
    heightmap: np.ndarray,
    sigma_m: float,
    pixel_size_m: float,
    workers: int | None = None,
    control: TaskControl | None = None,
) -> np.ndarray:
    """
    Glaettet das Hoehenraster mit einem Gauss-Filter der Breite sigma_m.
    Liefert eine NEUE Kopie, heightmap bleibt unveraendert. sigma_m <= 0
    bedeutet keine Glaettung.

    Grosse Raster werden in Zeilenstreifen (mit Rand, damit keine Naehte
    entstehen) auf mehreren Kernen gerechnet; das Ergebnis ist identisch zur
    einfachen Rechnung. control (optional) bekommt Fortschritt und kann
    abbrechen (TaskCancelled).
    """

    if sigma_m <= 0:
        return heightmap.copy()

    sigma_px = sigma_m / pixel_size_m
    truncate = 3.0

    source = heightmap.astype(np.float32, copy=False)

    rows = source.shape[0]
    n_workers = _worker_count(workers)

    if n_workers <= 1 or source.size < PARALLEL_MIN_PIXELS or rows < 2 * STRIPE_ROWS:

        if control is not None:
            control.check()

        smoothed = gaussian_filter(
            source, sigma=sigma_px, mode="nearest", truncate=truncate,
        )

        if control is not None:
            control.report(1.0)

        return smoothed.astype(heightmap.dtype, copy=False)

    halo = int(math.ceil(truncate * sigma_px)) + 1
    result = np.empty(source.shape, dtype=np.float32)
    stripes = [(r0, min(rows, r0 + STRIPE_ROWS)) for r0 in range(0, rows, STRIPE_ROWS)]
    done = [0]

    def work(stripe):

        r0, r1 = stripe

        if control is not None:
            control.check()

        a = max(0, r0 - halo)
        b = min(rows, r1 + halo)

        part = gaussian_filter(
            source[a:b], sigma=sigma_px, mode="nearest", truncate=truncate,
        )

        result[r0:r1] = part[r0 - a:r0 - a + (r1 - r0)]

        done[0] += 1

        if control is not None:
            control.report(done[0] / len(stripes))

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = [pool.submit(work, s) for s in stripes]
        try:
            for f in futures:
                f.result()
        except BaseException:
            for f in futures:
                f.cancel()
            raise

    return result.astype(heightmap.dtype, copy=False)


# Bis zu diesem Anteil der neuen Gipfelhoehe (ueber dem Wasser) bleibt das
# Gelaende unveraendert. Erst darueber wird weich gestaucht.
COMPRESS_KNEE_SHARE = 0.6


def _log_compress(excess: np.ndarray, scale: float) -> np.ndarray:
    return scale * np.log1p(excess / scale)


def compress_heights(
    heightmap: np.ndarray,
    water_level_m: float,
    factor: float,
) -> np.ndarray:
    """
    Begrenzt die Hoehen ueber dem Wasserspiegel "mit Knie": Die hoechste Stelle
    landet auf factor (0..1) ihrer urspruenglichen Hoehe ueber dem Wasser.
    Unterhalb des Knies (COMPRESS_KNEE_SHARE der neuen Gipfelhoehe) bleibt das
    Gelaende UNVERAENDERT - Talhaenge und Schluchtwaende behalten ihre Steilheit.
    Darueber wird logarithmisch (weich, ohne Knick in der Steigung) gestaucht,
    so dass Hochflaechen unter der Schnee-/Felsgrenze des Spiels bleiben und
    ihr Relief trotzdem nicht flachgedrueckt wird.

    Das Wasserniveau selbst bleibt unveraendert, der Uebergang ist stetig.
    Liefert eine NEUE Kopie. factor >= 1 bedeutet keine Veraenderung.
    """

    if factor >= 1.0:
        return heightmap.copy()

    heights = heightmap.astype(np.float32, copy=False)

    level = np.float32(water_level_m)

    max_above = float(heights.max()) - float(level)

    cap = max_above * float(factor)

    knee = cap * COMPRESS_KNEE_SHARE

    # Nichts zu tun, wenn schon alles unter dem Knie liegt.
    if max_above <= knee or cap <= 0.0:
        return heightmap.copy()

    # Skalenwert so bestimmen, dass die hoechste Stelle genau auf cap landet
    # (Bisektion; die Kurve waechst mit dem Skalenwert stetig an).
    top_excess = max_above - knee
    target = cap - knee

    low, high = 1e-3, max(top_excess, 1.0)

    for _ in range(60):
        mid = 0.5 * (low + high)
        if float(_log_compress(np.float64(top_excess), mid)) < target:
            low = mid
        else:
            high = mid

    scale = 0.5 * (low + high)

    above = heights - level

    excess = np.maximum(above - np.float32(knee), 0.0)

    compressed = np.float32(knee) + _log_compress(excess, np.float32(scale))

    result = np.where(
        above > np.float32(knee),
        level + compressed,
        heights,
    )

    return result.astype(heightmap.dtype, copy=False)
