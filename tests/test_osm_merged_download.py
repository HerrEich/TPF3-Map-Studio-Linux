"""Regressions for upstream's incremental cache combined with our retries."""
import tempfile
import types
import unittest
from collections import Counter

from src.map.objects.selection import Selection
from src.osm import overpass_client as oc
from src.osm.overpass_query_builder import OverpassQueryConfig, CATEGORY_FLAGS, build_query, area_filter
from src.osm.tile_cache import TileCache


def config(**flags):
    values = {key: False for key in CATEGORY_FLAGS}
    values.update(flags)
    return OverpassQueryConfig(**values)


class Response:
    def __init__(self, code=200):
        self.status_code=code
        self.headers={}
    def raise_for_status(self):
        if self.status_code >= 400:
            raise oc.requests.HTTPError(response=self)
    def json(self):
        return {'elements':[]}


class MergedDownloadTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory=directory.name
        self.c=self.client()
        self.calls=[]
        self.c._post=lambda server, query: (self.calls.append(query) or Response())

    def client(self):
        c=oc.OverpassClient()
        c.tile_cache=TileCache(self.directory)
        c.SERVERS=['https://one.invalid/api']
        c._sleep=lambda seconds:None
        return c

    def test_larger_selection_downloads_only_missing_groups_or_new_tiles(self):
        small=Selection.from_center(50.5,9,40000,40000)
        large=Selection.from_center(50.5,9,40000,40000,scale_factor=1.5)
        roads=config(highways=True)
        both=config(highways=True,water=True)
        water=config(water=True)
        first_tiles=oc.plan_tiles(small)
        self.c.download(small,roads)
        self.assertEqual(len(self.calls),len(first_tiles))
        self.calls.clear()
        old={area_filter(t) for t in first_tiles}
        expected=[build_query(t,water if area_filter(t) in old else both) for t in oc.plan_tiles(large)]
        self.c.download(large,both)
        self.assertEqual(Counter(self.calls),Counter(expected))
        # A new app/client must recover the full combination from disk, no requests.
        restarted=self.client()
        restarted._post=lambda *args:self.fail('Unexpected HTTP request after cache reload')
        restarted.download(large,both)
        self.assertEqual(restarted.last_cache_hits,len(oc.plan_tiles(large)))

    def test_incremental_request_keeps_retrying_only_missing_group(self):
        selection=Selection.from_center(50.5,9,3000,3000)
        self.c.download(selection,config(highways=True))
        self.calls.clear()
        events=[]
        self.c.on_status=events.append
        def post(server,query):
            self.calls.append(query)
            return Response(503 if len(self.calls)<=7 else 200)
        self.c._post=post
        self.c.download(selection,config(highways=True,water=True))
        self.assertEqual(len(self.calls),8)
        self.assertTrue(all('way["waterway"]' in q and 'way["highway"]' not in q for q in self.calls))
        self.assertTrue(any(e['state']=='retry' and e['seconds']==180 for e in events))
        self.assertEqual([e['attempt'] for e in events if e['state']=='request'],list(range(1,9)))
        self.assertEqual(events[-1]['state'],'complete')
        self.calls.clear()
        self.c.download(selection,config(highways=True,water=True))
        self.assertEqual(self.calls,[])

    def test_cancel_missing_group_preserves_roads_and_restart_fetches_water_only(self):
        selection=Selection.from_center(50.5,9,3000,3000)
        roads=config(highways=True)
        both=config(highways=True,water=True)
        self.c.download(selection,roads)
        self.c._post=lambda *args:Response(503)
        self.c.on_retry=lambda *args:self.c.cancel()
        with self.assertRaises(oc.OverpassCancelled):
            self.c.download(selection,both)
        self.assertIsNotNone(self.c.tile_cache.get(build_query(selection,roads)))
        self.calls.clear()
        self.c.on_retry=None
        self.c._post=lambda server,query:(self.calls.append(query) or Response())
        self.c.download(selection,both)
        self.assertEqual(len(self.calls),1)
        self.assertNotIn('way["highway"]',self.calls[0])
        self.assertIn('way["waterway"]',self.calls[0])
