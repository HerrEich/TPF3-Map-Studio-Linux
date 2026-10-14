import unittest

from src.map import leaflet_api as api


class ShortScriptTests(unittest.TestCase):

    def test_kurzes_skript_bleibt(self):
        self.assertEqual(api._short_script("window.MapApi.x();"), "window.MapApi.x();")

    def test_langes_skript_wird_gekuerzt(self):
        script = "window.MapApi.removeObjects('water', [" + ", ".join(str(i) for i in range(5000)) + "]);"
        short = api._short_script(script)

        self.assertLess(len(short), api.MAX_LOG_SCRIPT_CHARS + 60)
        self.assertTrue(short.startswith("window.MapApi.removeObjects('water'"))
        self.assertIn("%d Zeichen" % len(script), short)

    def test_genau_an_der_grenze(self):
        script = "x" * api.MAX_LOG_SCRIPT_CHARS
        self.assertEqual(api._short_script(script), script)