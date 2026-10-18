"""Rechnung fuer die zoombare 2D-Vorschau (ohne Qt, damit testbar).

Ein Bild (pw x ph) wird in ein Fenster (w x h) eingepasst (zoom 1 = ganzes
Bild sichtbar). Bei zoom > 1 zeigt das Fenster einen Ausschnitt um den
Mittelpunkt (cx, cy) in Bildkoordinaten.
"""

from __future__ import annotations

MAX_ZOOM = 40.0


def fit_scale(pw, ph, w, h):
    return min(w / pw, h / ph)


def scale_for(pw, ph, w, h, zoom):
    return fit_scale(pw, ph, w, h) * zoom


def clamp_center(pw, ph, w, h, s, cx, cy):
    """Mittelpunkt so begrenzen, dass kein leerer Rand entsteht. Ist das Bild
    in einer Richtung kleiner als das Fenster, bleibt es dort mittig."""
    hw, hh = w / (2 * s), h / (2 * s)
    cx = pw / 2 if pw <= 2 * hw else min(max(cx, hw), pw - hw)
    cy = ph / 2 if ph <= 2 * hh else min(max(cy, hh), ph - hh)
    return cx, cy


def zoom_at(pw, ph, w, h, zoom, cx, cy, factor, mx, my):
    """Zoom um den Punkt (mx, my) im Fenster; der Bildpunkt darunter bleibt
    stehen. Gibt (zoom, cx, cy) zurueck."""
    new_zoom = min(max(zoom * factor, 1.0), MAX_ZOOM)
    s_old = scale_for(pw, ph, w, h, zoom)
    s_new = scale_for(pw, ph, w, h, new_zoom)
    dx, dy = mx - w / 2, my - h / 2
    px, py = cx + dx / s_old, cy + dy / s_old
    ncx, ncy = px - dx / s_new, py - dy / s_new
    ncx, ncy = clamp_center(pw, ph, w, h, s_new, ncx, ncy)
    return new_zoom, ncx, ncy


def pan(pw, ph, w, h, zoom, cx, cy, dx_screen, dy_screen):
    """Bild um (dx, dy) Bildschirmpixel mit der Maus ziehen."""
    s = scale_for(pw, ph, w, h, zoom)
    return clamp_center(pw, ph, w, h, s, cx - dx_screen / s, cy - dy_screen / s)


def visible_rects(pw, ph, w, h, zoom, cx, cy):
    """(Quellrechteck im Bild, Zielrechteck im Fenster), je (x, y, breite, hoehe)."""
    s = scale_for(pw, ph, w, h, zoom)
    cx, cy = clamp_center(pw, ph, w, h, s, cx, cy)
    sx0 = max(cx - w / (2 * s), 0.0)
    sy0 = max(cy - h / (2 * s), 0.0)
    sx1 = min(cx + w / (2 * s), float(pw))
    sy1 = min(cy + h / (2 * s), float(ph))
    src = (sx0, sy0, sx1 - sx0, sy1 - sy0)
    dst = (w / 2 + (sx0 - cx) * s, h / 2 + (sy0 - cy) * s,
           (sx1 - sx0) * s, (sy1 - sy0) * s)
    return src, dst
