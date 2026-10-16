"""Server diagnostics must follow actual requests without altering retries."""
import tempfile
import unittest
from unittest import mock

from src.osm import overpass_client as oc
from src.osm.tile_cache import TileCache
from src.gui.osm_download_status import format_download_event
from src.i18n import set_language


class Response:
    def __init__(self, status=200):
        self.status_code = status
        self.headers = {}
    def raise_for_status(self):
        if self.status_code >= 400:
            raise oc.requests.HTTPError(response=self)
    def json(self):
        return {'elements': []}


class DownloadStatusTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.client = oc.OverpassClient()
        self.client.tile_cache = TileCache(directory.name)
        self.client.SERVERS = ['https://one.invalid/api', 'https://two.invalid/api']
        self.events = []
        self.client.on_status = self.events.append
        set_language('de')

    def test_server_switch_and_attempts_match_actual_requests(self):
        c = self.client
        c._post = mock.Mock(side_effect=[Response(504), Response()])
        c._load_tile(7, 'q')
        requests = [e for e in self.events if e['state'] == 'request']
        self.assertEqual([e['server'] for e in requests], c.SERVERS)
        self.assertEqual([e['attempt'] for e in requests], [1,2])
        self.assertTrue(all(e['tile'] == 8 and e['lane'] == 1 for e in self.events))
        error = next(e for e in self.events if e['state'] == 'error')
        self.assertEqual(error['http_status'], 504)
        switch = next(e for e in self.events if e['state'] == 'switch')
        self.assertEqual(switch['next_server'], c.SERVERS[1])
        self.assertIn('Zeitüberschreitung', format_download_event(error))
        self.assertEqual(self.events[-1]['state'], 'complete')
        self.assertEqual(self.events[-1]['server'], c.SERVERS[1])

    def test_countdown_then_retry_retains_tile_and_increments_attempt(self):
        c = self.client
        c.SERVERS = c.SERVERS[:1]
        c._post = mock.Mock(side_effect=[Response(503), Response()])
        c._sleep = lambda seconds: None
        c._load_tile(2, 'q')
        waits = [e['seconds'] for e in self.events if e['state'] == 'countdown']
        self.assertEqual(waits, list(range(10,0,-1)))
        self.assertEqual([e['attempt'] for e in self.events if e['state'] == 'request'], [1,2])
        self.assertTrue(all(e['tile'] == 3 for e in self.events))
        self.assertTrue(all(len(e['time']) == 8 for e in self.events))

    def test_queued_is_distinct_from_actual_request(self):
        c = self.client
        c._post = mock.Mock(return_value=Response())
        c._load_tile(0, 'q')
        self.assertEqual([e['state'] for e in self.events], ['queued','request','complete'])
        self.assertIn('freien Anfrageplatz', format_download_event(self.events[0]))
        self.assertIn('Anfrage läuft', format_download_event(self.events[1]))
        self.assertNotIn('/api', format_download_event(self.events[1]))
