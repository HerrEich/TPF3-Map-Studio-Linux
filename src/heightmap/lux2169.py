"""
Umrechnung WGS84 (Breite/Laenge in Grad) <-> Luxemburger Landeskoordinaten LUREF / Luxembourg TM
(EPSG:2169), ohne pyproj.

LUREF liegt auf dem internationalen Ellipsoid von 1924 (Hayford). Zuerst wird WGS84 mit einer
7-Parameter-Transformation (EPSG:5486, "LUREF to WGS 84 (3)", Genauigkeit rund 1 m) auf dieses
Ellipsoid umgerechnet, danach folgt die Transversale Mercator-Abbildung (Kruegersche Reihen).
Beides vektorisiert auf numpy-Arrays. Fuer Heightmaps mit 4 m pro Pixel ist das mehr als genau genug.
"""

from __future__ import annotations

import math

import numpy as np

# Kennzahl der luxemburgischen Daten (EPSG-Code)
LUX_EPSG = 2169

# Grober Umriss von Luxemburg (Breite von/bis, Laenge von/bis); nur dafuer, die Auswahl
# bei passenden Karten anzubieten.
LU_BOUNDS = (49.44, 50.19, 5.73, 6.53)

# Internationales Ellipsoid 1924
_A_INTL = 6378388.0
_F_INTL = 1.0 / 297.0

# WGS84
_A_WGS = 6378137.0
_F_WGS = 1.0 / 298.257223563

# Abbildung (Transversale Mercator)
_LAT0 = math.radians(49.0 + 50.0 / 60.0)
_LON0 = math.radians(6.0 + 10.0 / 60.0)
_K0 = 1.0
_FALSE_E = 80000.0
_FALSE_N = 100000.0

# LUREF -> WGS84, Positionsvektor-Form (EPSG:5486): Verschiebung in m, Drehung in Bogensekunden,
# Massstab in ppm
_TX, _TY, _TZ = -189.6806, 18.3463, -42.7695
_RX, _RY, _RZ = -0.33746, -3.09264, 2.53861
_SCALE_PPM = 0.4598

_ARCSEC = math.pi / (180.0 * 3600.0)


def _ellipsoid(a: float, f: float):
    return a, f, 2.0 * f - f * f


def _geodetic_to_xyz(lat, lon, a, e2):
    s, c = np.sin(lat), np.cos(lat)
    n = a / np.sqrt(1.0 - e2 * s * s)
    return n * c * np.cos(lon), n * c * np.sin(lon), n * (1.0 - e2) * s


def _xyz_to_geodetic(x, y, z, a, e2, iterations: int = 6):
    lon = np.arctan2(y, x)
    p = np.hypot(x, y)
    lat = np.arctan2(z, p * (1.0 - e2))

    for _ in range(iterations):
        s = np.sin(lat)
        n = a / np.sqrt(1.0 - e2 * s * s)
        lat = np.arctan2(z + e2 * n * s, p)

    return lat, lon


def _helmert(x, y, z, forward: bool):
    """Positionsvektor-Transformation LUREF -> WGS84 (forward) oder zurueck."""

    rx, ry, rz = _RX * _ARCSEC, _RY * _ARCSEC, _RZ * _ARCSEC
    m = 1.0 + _SCALE_PPM * 1e-6

    if forward:
        return (
            _TX + m * (x - rz * y + ry * z),
            _TY + m * (rz * x + y - rx * z),
            _TZ + m * (-ry * x + rx * y + z),
        )

    # Umkehrung: erst die Verschiebung abziehen, dann die (kleine) Drehung rueckwaerts anwenden
    x0, y0, z0 = (x - _TX) / m, (y - _TY) / m, (z - _TZ) / m

    return (
        x0 + rz * y0 - ry * z0,
        -rz * x0 + y0 + rx * z0,
        ry * x0 - rx * y0 + z0,
    )


# ---------------------------------------------------------------------------
# Transversale Mercator (Kruegersche n-Reihen)
# ---------------------------------------------------------------------------

_, _F, _E2 = _ellipsoid(_A_INTL, _F_INTL)
_N = _F / (2.0 - _F)
_A_HAT = _A_INTL / (1.0 + _N) * (1.0 + _N**2 / 4.0 + _N**4 / 64.0)

_ALPHA = (
    _N / 2.0 - 2.0 * _N**2 / 3.0 + 5.0 * _N**3 / 16.0,
    13.0 * _N**2 / 48.0 - 3.0 * _N**3 / 5.0,
    61.0 * _N**3 / 240.0,
)
_BETA = (
    _N / 2.0 - 2.0 * _N**2 / 3.0 + 37.0 * _N**3 / 96.0,
    _N**2 / 48.0 + _N**3 / 15.0,
    17.0 * _N**3 / 480.0,
)
_DELTA = (
    2.0 * _N - 2.0 * _N**2 / 3.0 - 2.0 * _N**3,
    7.0 * _N**2 / 3.0 - 8.0 * _N**3 / 5.0,
    56.0 * _N**3 / 15.0,
)

_E_SQRT = math.sqrt(_E2)


def _conformal_lat_t(lat):
    """t = sinh(Isometrische Breite im Kugelbild) fuer die geodaetische Breite lat."""

    s = np.sin(lat)
    k = 2.0 * math.sqrt(_N) / (1.0 + _N)
    return np.sinh(np.arctanh(s) - k * np.arctanh(k * s))


def _xi_of_lat(lat, dl):
    t = _conformal_lat_t(lat)
    return np.arctan2(t, np.cos(dl)), np.arctanh(np.sin(dl) / np.sqrt(1.0 + t * t))


_XI0, _ = _xi_of_lat(np.array(_LAT0), np.array(0.0))
_M0 = float(_A_HAT * (_XI0 + sum(a * np.sin(2.0 * (j + 1) * _XI0) for j, a in enumerate(_ALPHA))))


def _tm_forward(lat, lon):
    dl = lon - _LON0
    xi1, eta1 = _xi_of_lat(lat, dl)

    xi = xi1.copy()
    eta = eta1.copy()

    for j, a in enumerate(_ALPHA, start=1):
        xi = xi + a * np.sin(2 * j * xi1) * np.cosh(2 * j * eta1)
        eta = eta + a * np.cos(2 * j * xi1) * np.sinh(2 * j * eta1)

    east = _FALSE_E + _K0 * _A_HAT * eta
    north = _FALSE_N + _K0 * (_A_HAT * xi - _M0)

    return east, north


def _tm_inverse(east, north):
    xi = (north - _FALSE_N + _K0 * _M0) / (_K0 * _A_HAT)
    eta = (east - _FALSE_E) / (_K0 * _A_HAT)

    xi1 = xi.copy()
    eta1 = eta.copy()

    for j, b in enumerate(_BETA, start=1):
        xi1 = xi1 - b * np.sin(2 * j * xi) * np.cosh(2 * j * eta)
        eta1 = eta1 - b * np.cos(2 * j * xi) * np.sinh(2 * j * eta)

    chi = np.arcsin(np.sin(xi1) / np.cosh(eta1))

    lat = chi.copy()
    for j, d in enumerate(_DELTA, start=1):
        lat = lat + d * np.sin(2 * j * chi)

    lon = _LON0 + np.arctan2(np.sinh(eta1), np.cos(xi1))

    return lat, lon


# ---------------------------------------------------------------------------
# Oeffentliche Funktionen
# ---------------------------------------------------------------------------


def latlon_to_lux(lat, lon):
    """(Breite, Laenge) in Grad (WGS84) -> (Ost, Nord) in Metern, LUREF / EPSG:2169."""

    lat = np.radians(np.asarray(lat, dtype=np.float64))
    lon = np.radians(np.asarray(lon, dtype=np.float64))

    a_w, _f, e2_w = _ellipsoid(_A_WGS, _F_WGS)
    a_i, _f2, e2_i = _ellipsoid(_A_INTL, _F_INTL)

    x, y, z = _geodetic_to_xyz(lat, lon, a_w, e2_w)
    x, y, z = _helmert(x, y, z, forward=False)
    lat_i, lon_i = _xyz_to_geodetic(x, y, z, a_i, e2_i)

    return _tm_forward(lat_i, lon_i)


def lux_to_latlon(east, north):
    """(Ost, Nord) in Metern, LUREF / EPSG:2169 -> (Breite, Laenge) in Grad (WGS84)."""

    east = np.asarray(east, dtype=np.float64)
    north = np.asarray(north, dtype=np.float64)

    lat_i, lon_i = _tm_inverse(east, north)

    a_w, _f, e2_w = _ellipsoid(_A_WGS, _F_WGS)
    a_i, _f2, e2_i = _ellipsoid(_A_INTL, _F_INTL)

    x, y, z = _geodetic_to_xyz(lat_i, lon_i, a_i, e2_i)
    x, y, z = _helmert(x, y, z, forward=True)
    lat, lon = _xyz_to_geodetic(x, y, z, a_w, e2_w)

    return np.degrees(lat), np.degrees(lon)
