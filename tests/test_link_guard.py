"""Tests fuer die Link-Regel des Kartenfensters (ohne Qt)."""

import unittest
from pathlib import Path

from src.map.link_guard import is_internal_url, opens_in_browser


class InternalUrlTests(unittest.TestCase):

    def test_local_server_is_internal(self):
        for url in (
            "http://127.0.0.1:8000/",
            "http://127.0.0.1:8000/index.html?x=1#a",
            "http://localhost:51234/web/map.html",
            "http://[::1]:8000/",
            "HTTP://127.0.0.1:8000/",
        ):
            self.assertTrue(is_internal_url(url), url)

    def test_links_from_the_map_are_external(self):
        for url in (
            "https://leafletjs.com/",
            "https://www.openstreetmap.org/copyright",
            "https://opentopomap.org/",
            "http://example.com/",
        ):
            self.assertFalse(is_internal_url(url), url)

    def test_tricks_with_local_names_are_external(self):
        for url in (
            "http://127.0.0.1@evil.example/",
            "http://localhost.evil.example/",
            "https://127.0.0.1.evil.example/",
            "http://evil.example/127.0.0.1",
        ):
            self.assertFalse(is_internal_url(url), url)

    def test_internal_schemes(self):
        for url in ("about:blank", "data:text/html,x", "blob:http://127.0.0.1:8000/x"):
            self.assertTrue(is_internal_url(url), url)

    def test_unknown_and_broken(self):
        for url in ("file:///C:/x.html", "javascript:alert(1)", "", "http://[bad"):
            self.assertFalse(is_internal_url(url), url)


class BrowserTests(unittest.TestCase):

    def test_web_links_open_in_browser(self):
        self.assertTrue(opens_in_browser("https://leafletjs.com/"))
        self.assertTrue(opens_in_browser("mailto:a@example.com"))

    def test_local_and_odd_schemes_do_not(self):
        self.assertFalse(opens_in_browser("http://127.0.0.1:8000/"))
        self.assertFalse(opens_in_browser("file:///C:/x.html"))
        self.assertFalse(opens_in_browser("javascript:alert(1)"))


class WiringTests(unittest.TestCase):

    def test_map_widget_uses_the_guarded_page(self):
        path = Path(__file__).resolve().parents[1] / "src" / "map" / "map_widget.py"
        text = path.read_text(encoding="utf-8")

        self.assertIn("from src.map.map_page import MapPage", text)
        self.assertIn("self.setPage(MapPage(self))", text)
        # Die Seite muss vor der Entwicklerkonsole gesetzt werden.
        self.assertLess(
            text.index("self.setPage(MapPage(self))"),
            text.index("setDevToolsPage"),
        )


if __name__ == "__main__":
    unittest.main()
