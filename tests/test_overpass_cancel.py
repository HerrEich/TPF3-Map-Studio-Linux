import threading
import time
import unittest
from unittest import mock

from src.osm import overpass_client as oc


class _SlowPost:
    """Antwortet erst nach 'delay' Sekunden (simuliert einen haengenden Server)."""

    def __init__(self, delay):
        self.delay = delay

    def __call__(self, *args, **kwargs):
        time.sleep(self.delay)
        raise oc.requests.ConnectionError("zu spaet")


class CancelTest(unittest.TestCase):

    def _client(self):
        client = oc.OverpassClient()
        return client

    def test_cancel_interrupts_slow_request(self):
        client = self._client()
        with mock.patch.object(oc, "build_query", lambda s, c=None: "q"), \
                mock.patch.object(oc.requests, "post", _SlowPost(10.0)):
            threading.Timer(0.3, client.cancel).start()
            start = time.time()
            with self.assertRaises(oc.OverpassCancelled):
                client.download(object(), None)
            self.assertLess(time.time() - start, 3.0)

    def test_cancel_flag_cleared_after_download(self):
        client = self._client()
        with mock.patch.object(oc, "build_query", lambda s, c=None: "q"), \
                mock.patch.object(oc.requests, "post", _SlowPost(10.0)):
            client.cancel()
            with self.assertRaises(oc.OverpassCancelled):
                client.download(object(), None)
        self.assertFalse(client._cancel.is_set())

    def test_normal_failure_still_runtime_error(self):
        client = self._client()
        with mock.patch.object(oc, "build_query", lambda s, c=None: "q"), \
                mock.patch.object(oc.requests, "post", _SlowPost(0.0)):
            with self.assertRaises(RuntimeError):
                client.download(object(), None)


if __name__ == "__main__":
    unittest.main()
