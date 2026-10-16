"""Counts distinguish cached, partially cached and new tiles throughout a run."""
import tempfile
import unittest
from unittest import mock

from src.map.objects.selection import Selection
from src.osm import overpass_client as oc
from src.osm.overpass_query_builder import CATEGORY_FLAGS, OverpassQueryConfig, build_query, area_filter
from src.osm.tile_cache import TileCache


def config(**enabled):
    values={key:False for key in CATEGORY_FLAGS}
    values.update(enabled)
    return OverpassQueryConfig(**values)


class Response:
    status_code=200
    headers={}
    def raise_for_status(self):pass
    def json(self):return {'elements':[]}


class CacheProgressTest(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.client=oc.OverpassClient()
        self.client.tile_cache=TileCache(folder.name)
        self.client.SERVERS=['https://test.invalid/api']
        self.tiles=[Selection.from_center(50.5+n*.02,9,1000,1000) for n in range(3)]
        self.both=config(highways=True,water=True)
        self.roads=config(highways=True)
        self.client.tile_cache.put(build_query(self.tiles[0],self.both),{'elements':[]})
        query=build_query(self.tiles[1],self.roads)
        self.client.tile_cache.put(query,{'elements':[]})
        self.client.tile_cache.register(area_filter(self.tiles[1]),{'highways'},query)
        self.states=[]
        self.client.on_cache_status=self.states.append

    def test_initial_classification_and_live_counts_are_consistent(self):
        requests=[]
        self.client._post=lambda server,query:(requests.append(query) or Response())
        with mock.patch.object(oc,'plan_tiles',return_value=self.tiles):
            self.client.download(self.tiles[0],self.both)
        self.assertEqual(len(requests),2)
        self.assertEqual(len(self.states),3)
        start=self.states[0]
        self.assertEqual((start['cached'],start['partial'],start['new'],start['done']),(1,1,1,1))
        self.assertEqual((self.states[-1]['partial'],self.states[-1]['new'],self.states[-1]['done']),(0,0,3))
        for state in self.states:
            self.assertEqual(state['done']+state['partial']+state['new'],state['total'])
            self.assertEqual((state['cached'],state['initial_partial'],state['initial_new']),(1,1,1))
        # Earlier snapshots must not be mutated by subsequent worker completions.
        self.assertEqual(start['done'],1)

    def test_fully_cached_run_reports_no_pending_downloads(self):
        for tile in self.tiles:
            self.client.tile_cache.put(build_query(tile,self.both),{'elements':[]})
        self.client._post=mock.Mock(side_effect=AssertionError('Network must not be used'))
        with mock.patch.object(oc,'plan_tiles',return_value=self.tiles):
            self.client.download(self.tiles[0],self.both)
        self.assertEqual(len(self.states),1)
        self.assertEqual((self.states[0]['cached'],self.states[0]['partial'],self.states[0]['new']),(3,0,0))
        self.client._post.assert_not_called()

    def test_height_factor_change_reuses_same_osm_cache(self):
        first=Selection.from_center(50.5,9,1000,1000,scale_factor=3,height_scale=1/3)
        second=Selection.from_center(50.5,9,1000,1000,scale_factor=3,height_scale=1.0)
        self.client._post=mock.Mock(return_value=Response())
        self.client.download(first,self.both)
        self.client._post.reset_mock()
        self.client.download(second,self.both)
        self.client._post.assert_not_called()
        self.assertEqual(self.states[-1]['cached'],1)
