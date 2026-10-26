"""Obergrenzen und Wichtigkeit der Objekte pro Kartenebene.

Hintergrund (Fehlerbericht zu v0.7.1): Beim Einschalten der Ebene "Fluesse"
wurden 300.000 Linien auf einmal in die Kartenansicht gelegt, die Ansicht
hing und blieb leer. Darum gelten jetzt je Ebene kleinere Grenzen, und wenn
gekuerzt werden muss, bleiben die wichtigsten Objekte (z. B. grosse Fluesse
vor kleinen Baechen, Autobahnen vor Feldwegen).

Die Grenzen betreffen nur die Anzeige in der Karte. Export und Berechnungen
arbeiten weiter mit allen geladenen OSM-Daten.
"""

from src.map.layer import Layer

# Obergrenze der angezeigten Objekte je Ebene.
LAYER_LIMITS = {
    Layer.ROADS: 80_000,
    Layer.RAILWAYS: 80_000,
    Layer.BUILDINGS: 80_000,
    Layer.WATER: 60_000,
    Layer.WATERWAYS: 60_000,
    Layer.PARKS: 60_000,
    Layer.LANDUSE: 60_000,
    Layer.VEGETATION: 60_000,
}

DEFAULT_LIMIT = 60_000

_WATERWAY_RANK = {
    "river": 0,
    "canal": 1,
    "stream": 2,
    "tidal_channel": 2,
    "drain": 3,
    "ditch": 4,
}

_HIGHWAY_RANK = {
    "motorway": 0,
    "motorway_link": 0,
    "trunk": 1,
    "trunk_link": 1,
    "primary": 2,
    "primary_link": 2,
    "secondary": 3,
    "secondary_link": 3,
    "tertiary": 4,
    "tertiary_link": 4,
    "unclassified": 5,
    "residential": 5,
    "living_street": 6,
    "service": 7,
    "track": 8,
    "path": 9,
    "footway": 9,
    "cycleway": 9,
    "bridleway": 9,
    "steps": 9,
}


def limit_for(layer) -> int:
    """Obergrenze fuer eine Ebene (Layer-Wert)."""

    return LAYER_LIMITS.get(layer, DEFAULT_LIMIT)


def _tag(obj, key):
    tags = getattr(obj, "tags", None) or {}
    return tags.get(key)


def _waterway_rank(obj) -> int:
    return _WATERWAY_RANK.get(_tag(obj, "waterway"), 5)


def _highway_rank(obj) -> int:
    return _HIGHWAY_RANK.get(_tag(obj, "highway"), 10)


def rank_for(layer):
    """Sortierschluessel (kleiner = wichtiger) oder None (OSM-Reihenfolge)."""

    if layer == Layer.WATERWAYS:
        return _waterway_rank

    if layer == Layer.ROADS:
        return _highway_rank

    return None
