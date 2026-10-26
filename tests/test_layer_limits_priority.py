import unittest

from src.map.layer import Layer
from src.map.renderer.base_renderer import MAX_ITEMS_PER_LAYER
from src.map.renderer.layer_limits import LAYER_LIMITS, limit_for, rank_for
from src.map.renderer.pipeline import RenderPipeline


class _Obj:
    def __init__(self, i, tags):
        self.id = i
        self.tags = tags


class _Osm:
    def get_geometry(self, _id):
        return [[0, 0]]


class _Style:
    def to_dict(self):
        return {}


class _Resolver:
    def resolve(self, obj, zoom=None):
        return _Style()


def _pipe(objs):
    return RenderPipeline(
        selector=lambda osm: iter(objs),
        style_resolver=_Resolver(),
        geometry_type=type("G", (), {"value": "polyline"})(),
    )


class LayerLimitsTest(unittest.TestCase):

    def test_alle_ebenen_haben_grenze_unter_maximum(self):
        for layer in (
            Layer.ROADS, Layer.RAILWAYS, Layer.BUILDINGS, Layer.WATER,
            Layer.WATERWAYS, Layer.PARKS, Layer.LANDUSE, Layer.VEGETATION,
        ):
            self.assertIn(layer, LAYER_LIMITS)
            self.assertLessEqual(limit_for(layer), MAX_ITEMS_PER_LAYER)
            self.assertGreater(limit_for(layer), 0)

    def test_fluesse_grenze_deutlich_kleiner_als_300000(self):
        self.assertLessEqual(limit_for(Layer.WATERWAYS), 100_000)

    def test_wichtige_fluesse_bleiben(self):
        objs = [_Obj(i, {"waterway": "ditch"}) for i in range(10)]
        objs += [_Obj(100, {"waterway": "river"}), _Obj(101, {"waterway": "stream"})]
        items = _pipe(objs).build(_Osm(), limit=3, rank=rank_for(Layer.WATERWAYS))
        ids = [it.id for it in items]
        self.assertEqual(ids[:2], [100, 101])
        self.assertEqual(len(ids), 3)

    def test_strassen_autobahn_zuerst(self):
        objs = [_Obj(1, {"highway": "track"}), _Obj(2, {"highway": "motorway"}),
                _Obj(3, {"highway": "residential"})]
        items = _pipe(objs).build(_Osm(), limit=2, rank=rank_for(Layer.ROADS))
        self.assertEqual([it.id for it in items], [2, 3])

    def test_unter_dem_limit_bleibt_reihenfolge(self):
        objs = [_Obj(1, {"waterway": "stream"}), _Obj(2, {"waterway": "river"})]
        items = _pipe(objs).build(_Osm(), limit=10, rank=rank_for(Layer.WATERWAYS))
        self.assertEqual([it.id for it in items], [1, 2])

    def test_ohne_rank_wie_bisher(self):
        objs = [_Obj(i, {}) for i in range(5)]
        items = _pipe(objs).build(_Osm(), limit=3)
        self.assertEqual([it.id for it in items], [0, 1, 2])

    def test_gebaeude_ohne_rank(self):
        self.assertIsNone(rank_for(Layer.BUILDINGS))


if __name__ == "__main__":
    unittest.main()
