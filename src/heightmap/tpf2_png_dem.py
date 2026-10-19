"""
TPF2-Heightmap (PNG) als Hoehenquelle fuer das Kartenband (Szenario B, v0.6.0).

Die PNG liegt schon im Spielraster (4 m/Pixel). Damit Gefaelle-Ausgleich,
OSM-Wasser und Biome unveraendert darauf laufen, verhaelt sie sich wie ein
Hoehenmodell: sample_grid(lat, lon) rechnet jeden Punkt ueber dieselbe
Geometrie wie _sample_grid() zurueck in Pixel und mischt bilinear.
Bei scale 1, Drehung egal, ohne Oversampling trifft jeder Abtastpunkt genau
eine Pixelmitte -> die Hoehen bleiben unveraendert.
"""

from __future__ import annotations

import numpy as np

from src.heightmap.tpf2_heightmap_import import raw_to_meters


class Tpf2PngSizeError(ValueError):
    """PNG-Groesse passt nicht zum Kartenband."""


class Tpf2PngMosaic:
    parallel_safe = True   # nur lesende Zugriffe auf feste Arrays

    def __init__(self, raw, low_m, high_m, geometry, center, width_m, height_m,
                 scale=1.0):
        if not high_m > low_m:
            raise ValueError("Max muss ueber Min liegen")
        self.h = raw_to_meters(raw, low_m, high_m).astype(np.float32)
        self.rows, self.cols = self.h.shape
        self.g = geometry
        self.center_lat, self.center_lon = center
        self.scale = float(scale or 1.0)
        self.pitch_x = width_m / self.cols
        self.pitch_y = height_m / self.rows
        self.hx, self.hy = width_m / 2, height_m / 2
        rx, ry = geometry.right_vector[0], geometry.right_vector[1]
        ux, uy = geometry.up_vector[0], geometry.up_vector[1]
        det = rx * uy - ux * ry
        if abs(det) < 1e-12:
            raise ValueError("Ungueltige Geometrie")
        self._inv = (uy / det, -ux / det, -ry / det, rx / det)

    def sample_grid(self, lat, lon):
        g = self.g
        n = (lat - self.center_lat) * g.METERS_PER_DEGREE_LAT
        e = (lon - self.center_lon) * g.longitude_scale
        a, b, c, d = self._inv
        xl = (a * e + b * n) / self.scale
        yl = (c * e + d * n) / self.scale
        col = (xl + self.hx) / self.pitch_x - 0.5
        row = (self.hy - yl) / self.pitch_y - 0.5
        out = np.full(np.shape(lat), np.nan, dtype=np.float32)
        ok = ((col >= -0.5) & (col <= self.cols - 0.5)
              & (row >= -0.5) & (row <= self.rows - 0.5))
        c0 = np.clip(col, 0, self.cols - 1)
        r0 = np.clip(row, 0, self.rows - 1)
        ci = np.minimum(np.floor(c0).astype(int), self.cols - 2 if self.cols > 1 else 0)
        ri = np.minimum(np.floor(r0).astype(int), self.rows - 2 if self.rows > 1 else 0)
        fc = (c0 - ci).astype(np.float32)
        fr = (r0 - ri).astype(np.float32)
        c1 = np.minimum(ci + 1, self.cols - 1)
        r1 = np.minimum(ri + 1, self.rows - 1)
        h = self.h
        v = ((h[ri, ci] * (1 - fc) + h[ri, c1] * fc) * (1 - fr)
             + (h[r1, ci] * (1 - fc) + h[r1, c1] * fc) * fr)
        out[ok] = v[ok]
        return out
