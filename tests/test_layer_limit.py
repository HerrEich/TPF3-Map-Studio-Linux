import unittest

from src.map.renderer.base_renderer import (
    BATCH_CHUNK_SIZE,
    MAX_ITEMS_PER_LAYER,
    chunked,
)
from src.map.renderer.pipeline import RenderPipeline


class _Obj:
    def __init__(self, i):
        self.id = i
        self.tags = {}


class _Osm:
    def get_geometry(self, _id):
        return [[0, 0]]


class _Style:
    def to_dict(self):
        return {}


class _Resolver:
    def resolve(self, obj, zoom=None):
        return _Style()


class LayerLimitTest(unittest.TestCase):

    def test_chunked_teilt_in_stuecke(self):
        parts = list(chunked(list(range(12)), 5))
        self.assertEqual([len(p) for p in parts], [5, 5, 2])

    def test_chunked_leer(self):
        self.assertEqual(list(chunked([])), [])

    def test_grenzen_sinnvoll(self):
        self.assertLessEqual(BATCH_CHUNK_SIZE, MAX_ITEMS_PER_LAYER)

    def test_pipeline_limit(self):
        pipe = RenderPipeline(
            selector=lambda osm: (_Obj(i) for i in range(100)),
            style_resolver=_Resolver(),
            geometry_type=type("G", (), {"value": "polyline"})(),
        )
        self.assertEqual(len(pipe.build(_Osm(), limit=10)), 10)
        self.assertEqual(len(pipe.build(_Osm())), 100)


if __name__ == "__main__":
    unittest.main()
