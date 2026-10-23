"""
Ablauf "TPF2-Karte uebernehmen" (Szenario A, v0.6.0) ohne Oberflaeche.

Fuer fiktive TPF2-Karten: Dort liegt alles Wasser auf EINER Ebene, ein
Fluss-Gefaelle gibt es nicht. Der Ablauf ist deshalb:
  1. Hoehenskala (Min/Max) und Wasserhoehe gibt der Nutzer an (die PNG
     enthaelt keine Meter), Kontrolle ueber die Wasser-Vorschau.
  2. Optional Ufer bereinigen (tpf2_water_cleanup): Pfuetzen weg, Land
     knapp ueber Wasser anheben, flaches Wasser vertiefen.
  3. Biom-Maske nach Hoehen-Anteil (tpf2_biome_from_height).
Die Hoehenskala bleibt dabei gleich: im TPF3-Import werden dieselben
Werte fuer Min, Max und Wasserhoehe eingetragen.

Karten nach echten Hoehendaten (Fluesse mit Gefaelle) gehoeren zu
Szenario B (Gewaesser aus OSM) - automatische Erkennung aus der Heightmap
war im Test (18.10.2026, Halle-Leipzig) nicht zuverlaessig.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.heightmap.biome_mask import BACKGROUND_BIOME
from src.heightmap.tpf2_biome_from_height import (
    DEFAULT_BANDS,
    biome_index_from_height,
    flooded_share,
    meters_to_raw,
    validate_bands,
)
from src.heightmap.tpf2_heightmap_import import raw_to_meters
from src.heightmap.tpf2_water_cleanup import (
    DEFAULT_DEPTH_M,
    DEFAULT_MARGIN_M,
    DEFAULT_MIN_AREA_PX,
    CleanupResult,
    clean_water,
)

# Grenzen des TPF3-Heightmap-Imports (im Spiel getestet, Okt. 2026)
TPF3_MIN_M = -100.0
TPF3_MAX_M = 3177.0

PIXEL_M = 4.0


class ImportSettingsError(ValueError):
    """Ungueltige Einstellungen. `code` fuer die Oberflaeche."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ImportSettings:
    low_m: float
    high_m: float
    water_m: float
    cleanup: bool = True
    margin_m: float = DEFAULT_MARGIN_M
    depth_m: float = DEFAULT_DEPTH_M
    min_area_px: int = DEFAULT_MIN_AREA_PX
    bands: tuple[tuple[float, int], ...] = field(default=DEFAULT_BANDS)
    water_biome: int = BACKGROUND_BIOME


@dataclass(frozen=True)
class ImportResult:
    settings: ImportSettings
    raw: np.ndarray                    # uint16, zu speichernde Heightmap
    biome_index: np.ndarray            # uint8, Biom je Pixel
    flooded_share: float               # Anteil Wasser 0..1 im Ergebnis
    cleanup: CleanupResult | None      # None = nicht bereinigt


def validate_settings(s: ImportSettings) -> None:
    if not (TPF3_MIN_M <= s.low_m <= TPF3_MAX_M and TPF3_MIN_M <= s.high_m <= TPF3_MAX_M):
        raise ImportSettingsError("limits", "Hoehen ausserhalb -100 bis 3177 m")
    if s.high_m <= s.low_m:
        raise ImportSettingsError("order", "Maximalhoehe muss groesser als Mindesthoehe sein")
    if not s.low_m <= s.water_m <= s.high_m:
        raise ImportSettingsError("water", "Wasserhoehe muss zwischen Min und Max liegen")
    validate_bands(s.bands)


def water_raw(s: ImportSettings) -> float | None:
    """Wasserhoehe als Rohwert; None, wenn sie auf/unter Min liegt (kein Wasser)."""
    if s.water_m <= s.low_m:
        return None
    return meters_to_raw(s.water_m, s.low_m, s.high_m)


def run_import(raw: np.ndarray, s: ImportSettings) -> ImportResult:
    """Ganzer Ablauf auf voller Aufloesung."""
    validate_settings(s)
    w_raw = water_raw(s)
    result_cleanup = None
    out = raw
    if s.cleanup and w_raw is not None:
        result_cleanup = clean_water(
            raw, s.low_m, s.high_m, s.water_m,
            margin_m=s.margin_m, depth_m=s.depth_m, min_area_px=s.min_area_px,
        )
        out = result_cleanup.raw
    index = biome_index_from_height(out, s.bands, water_raw=w_raw, water_biome=s.water_biome)
    return ImportResult(
        settings=s,
        raw=out,
        biome_index=index,
        flooded_share=flooded_share(out, w_raw),
        cleanup=result_cleanup,
    )


def _shade(meters: np.ndarray, pixel_m: float) -> np.ndarray:
    gy, gx = np.gradient(meters, pixel_m)
    return np.clip(0.6 + 4.0 * (-gx - gy) / np.sqrt(2.0), 0.15, 1.0)


def water_preview_rgb(raw: np.ndarray, s: ImportSettings, step: int = 4) -> np.ndarray:
    """Relief grau, Wasser blau (jedes `step`-te Pixel), uint8 HxWx3."""
    small = raw[::step, ::step]
    meters = raw_to_meters(small, s.low_m, s.high_m)
    gray = (_shade(meters, PIXEL_M * step) * 220).astype(np.uint8)
    rgb = np.stack([gray, gray, gray], axis=-1)
    w_raw = water_raw(s)
    if w_raw is not None:
        rgb[small < w_raw] = (40, 110, 220)
    return np.ascontiguousarray(rgb)


# Kraeftige, gut unterscheidbare Farben fuer die Ueberlagerung (Index = Biom)
BIOME_OVERLAY_RGB = (
    (255, 220, 60),    # 0 gelb
    (40, 170, 90),     # 1 gruen
    (150, 80, 200),    # 2 violett
    (235, 130, 40),    # 3 orange
    (200, 60, 60),     # 4 rot
)


def overlay_preview_rgb(
    raw: np.ndarray,
    s: ImportSettings,
    biome_index: np.ndarray,
    step: int = 4,
    alpha: float = 0.5,
) -> np.ndarray:
    """Relief grau mit halbtransparenter Biom-Faerbung, Wasser bleibt blau.

    `alpha` ist die Deckkraft der Biom-Farben (0 = nur Relief, 1 = nur Biome).
    """
    alpha = float(min(max(alpha, 0.0), 1.0))
    base = water_preview_rgb(raw, s, step=step)
    index = biome_index[::step, ::step]
    colors = np.array(BIOME_OVERLAY_RGB, dtype=np.float32)[
        np.clip(index, 0, len(BIOME_OVERLAY_RGB) - 1)
    ]
    mixed = base.astype(np.float32) * (1.0 - alpha) + colors * alpha
    w_raw = water_raw(s)
    if w_raw is not None:
        flooded = raw[::step, ::step] < w_raw
        mixed[flooded] = base[flooded]
    return np.ascontiguousarray(np.clip(mixed + 0.5, 0, 255).astype(np.uint8))


def default_output_name(source: str | Path, suffix: str) -> str:
    """Vorschlag fuer den Dateinamen, z. B. 'meine_karte_tpf3.png'."""
    return "%s_%s.png" % (Path(source).stem, suffix)
