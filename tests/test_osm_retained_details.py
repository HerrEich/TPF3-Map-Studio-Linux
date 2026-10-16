"""Regression for reusing richer tiles after a restart or reduced selection."""
from pathlib import Path
import tempfile
import types
import unittest
from src.map.objects.selection import Selection
from src.osm import overpass_client as oc
from src.osm.tile_cache import TileCache
from src.osm.overpass_query_builder import CATEGORY_FLAGS,OverpassQueryConfig,build_query,area_filter,query_categories


def cfg(**flags):
    values={key:False for key in CATEGORY_FLAGS}
    values.update(flags)
    return OverpassQueryConfig(**values)


class Response:
    status_code=200;headers={}
    def __init__(self,ids):self.ids=ids
    def raise_for_status(self):pass
    def json(self):return {'elements':[{'type':'way','id':i} for i in self.ids]}


class RetainedDetailsTest(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.client=oc.OverpassClient();self.client.tile_cache=TileCache(folder.name)
        self.client.parser=types.SimpleNamespace(parse=lambda data:types.SimpleNamespace(elements=data['elements']))
        self.tile=Selection.from_center(50.5,9,3000,3000)
        self.calls=[]
        self.client._post=lambda server,query:(self.calls.append(query) or Response([3]))

    def seed(self,tile,config,ids):
        query=build_query(tile,config)
        self.client.tile_cache.put(query,Response(ids).json())
        self.client.tile_cache.register(area_filter(tile),query_categories(config),query)

    def test_all_categories_selected_by_default(self):
        self.assertTrue(all(v for k,v in OverpassQueryConfig().to_dict().items() if k!='nature_details'))

    def test_richer_cache_wins_even_with_exact_smaller_entry(self):
        roads=cfg(highways=True);both=cfg(highways=True,buildings=True)
        self.seed(self.tile,roads,[1]);self.seed(self.tile,both,[1,2])
        paths=list(self.client.tile_cache.directory.glob('*.json.gz'))
        before={p.name:p.stat().st_mtime_ns for p in paths}
        osm=self.client.download(self.tile,roads)
        self.assertEqual(sorted(e['id'] for e in osm.elements),[1,2])
        self.assertEqual(self.calls,[])
        self.assertEqual(before,{p.name:p.stat().st_mtime_ns for p in paths})

    def test_disjoint_cached_groups_are_retained_when_adding_water(self):
        self.seed(self.tile,cfg(highways=True),[1])
        self.seed(self.tile,cfg(buildings=True),[2])
        osm=self.client.download(self.tile,cfg(water=True))
        self.assertEqual(sorted(e['id'] for e in osm.elements),[1,2,3])
        self.assertEqual(len(self.calls),1)
        self.assertIn('way["waterway"]',self.calls[0])
        self.assertNotIn('way["highway"]',self.calls[0])
        self.calls.clear()
        osm=self.client.download(self.tile,cfg(highways=True,buildings=True,water=True))
        self.assertEqual(self.calls,[])
        self.assertEqual(sorted(e['id'] for e in osm.elements),[1,2,3])

    def test_33_of_49_tiles_survive_reduced_categories(self):
        args=(50.58693557282398,8.674647510051729,16384,16384)
        small=Selection.from_center(*args,scale_factor=3,height_scale=1)
        large=Selection.from_center(*args,scale_factor=4,height_scale=1)
        tiles=oc.plan_tiles(small)
        self.assertEqual(len(tiles),33)
        self.assertEqual(len(oc.plan_tiles(large)),49)
        for i,tile in enumerate(tiles):self.seed(tile,OverpassQueryConfig(),[100+i])
        osm=self.client.download(large,OverpassQueryConfig(nature_details=False))
        self.assertEqual(self.client.last_cache_hits,33)
        self.assertEqual(len(self.calls),16)
        self.assertTrue(set(range(100,133)) <= {e['id'] for e in osm.elements})

    def test_full_railways_satisfy_no_tram_request_without_discarding_trams(self):
        self.seed(self.tile,cfg(railways=True),[1,2])
        osm=self.client.download(self.tile,cfg(railways=True,include_tram=False))
        self.assertEqual(self.calls,[])
        self.assertEqual(sorted(e['id'] for e in osm.elements),[1,2])
