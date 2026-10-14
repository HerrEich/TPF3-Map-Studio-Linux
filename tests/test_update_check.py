import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path

from src.core import update_check as u


class FakeResponse:

    def __init__(self, data):
        self._data = data

    def read(self, size=-1):
        if size is None or size < 0:
            return self._data
        return self._data[:size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def release(**changes):
    data = {
        "tag_name": "v0.5.0",
        "name": "TPF3 Map Studio v0.5.0",
        "html_url": "https://github.com/sharpi13822/TPF3-Map-Studio/releases/tag/v0.5.0",
        "draft": False,
        "prerelease": False,
    }
    data.update(changes)
    return data


def opener_for(payload, seen=None):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

    def opener(request, timeout=None):
        if seen is not None:
            seen.append((request, timeout))
        return FakeResponse(raw)

    return opener


def failing_opener(error):
    def opener(request, timeout=None):
        raise error

    return opener


class VersionTests(unittest.TestCase):

    def test_gueltige_versionen(self):
        self.assertEqual(u.parse_version("v0.5.0"), (0, 5, 0))
        self.assertEqual(u.parse_version("V1.2.3"), (1, 2, 3))
        self.assertEqual(u.parse_version("0.6"), (0, 6, 0))
        self.assertEqual(u.parse_version(" 0.10.1 "), (0, 10, 1))

    def test_ungueltige_versionen(self):
        for text in ("", "abc", "1", "1.2.3.4", "v0.5.0-beta", None, 5, "1..2"):
            self.assertIsNone(u.parse_version(text), text)

    def test_ist_neuer(self):
        self.assertTrue(u.is_newer("0.5.0", "0.4.0"))
        self.assertTrue(u.is_newer("0.10.0", "0.9.0"))
        self.assertTrue(u.is_newer("v1.0", "0.9.9"))
        self.assertFalse(u.is_newer("0.4.0", "0.4.0"))
        self.assertFalse(u.is_newer("0.3.9", "0.4.0"))
        self.assertFalse(u.is_newer("kaputt", "0.4.0"))
        self.assertFalse(u.is_newer("0.5.0", "kaputt"))

    def test_entscheidung(self):
        self.assertEqual(u.decide_action("0.4.0", "0.5.0", "", False), "update")
        self.assertEqual(u.decide_action("0.4.0", "0.5.0", "0.5.0", False), "skipped")
        self.assertEqual(u.decide_action("0.4.0", "0.5.0", "0.5.0", True), "update")
        self.assertEqual(u.decide_action("0.4.0", "0.6.0", "0.5.0", False), "update")
        self.assertEqual(u.decide_action("0.4.0", "0.4.0", "", True), "current")
        self.assertEqual(u.decide_action("0.5.0", "0.4.0", "", False), "current")


class FetchTests(unittest.TestCase):

    def test_normale_antwort(self):
        info = u.fetch_latest("Test/1", urlopen=opener_for(release()))
        self.assertEqual(info.version, "0.5.0")
        self.assertEqual(info.tag, "v0.5.0")
        self.assertEqual(info.name, "TPF3 Map Studio v0.5.0")
        self.assertEqual(
            info.url,
            "https://github.com/sharpi13822/TPF3-Map-Studio/releases/tag/v0.5.0",
        )

    def test_anfrage(self):
        seen = []
        u.fetch_latest("Test/1", urlopen=opener_for(release(), seen))
        request, timeout = seen[0]
        self.assertEqual(request.full_url, u.API_URL)
        self.assertTrue(u.API_URL.startswith("https://api.github.com/"))
        self.assertEqual(request.get_header("User-agent"), "Test/1")
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertEqual(timeout, u.DEFAULT_TIMEOUT_S)

    def test_fremde_adresse_wird_ersetzt(self):
        for url in (
            "https://evil.example/x",
            "http://github.com/sharpi13822/TPF3-Map-Studio/releases",
            "javascript:alert(1)",
            None,
            5,
        ):
            info = u.fetch_latest("T", urlopen=opener_for(release(html_url=url)))
            self.assertEqual(info.url, u.RELEASES_URL)

    def test_tag_ohne_v(self):
        info = u.fetch_latest("T", urlopen=opener_for(release(tag_name="0.6")))
        self.assertEqual(info.version, "0.6.0")

    def test_name_wird_einzeilig(self):
        info = u.fetch_latest("T", urlopen=opener_for(release(name="a\nb  c")))
        self.assertEqual(info.name, "a b c")

    def test_unbrauchbare_antworten(self):
        bad = [
            b"kein json",
            b"\xff\xfe",
            [1, 2],
            {"name": "x"},
            {"tag_name": 5},
            {"tag_name": "nightly"},
            b" " * (u.MAX_RESPONSE_BYTES + 1),
        ]
        for payload in bad:
            with self.assertRaises(u.UpdateCheckError):
                u.fetch_latest("T", urlopen=opener_for(payload))

    def test_http_fehler(self):
        messages = {}
        for code in (404, 403, 429, 500):
            error = urllib.error.HTTPError("https://x", code, "x", {}, None)
            with self.assertRaises(u.UpdateCheckError) as ctx:
                u.fetch_latest("T", urlopen=failing_opener(error))
            messages[code] = str(ctx.exception)

        self.assertEqual(messages[403], messages[429])
        self.assertNotEqual(messages[404], messages[403])
        self.assertIn("500", messages[500])

    def test_netzwerkfehler(self):
        for error in (urllib.error.URLError("weg"), TimeoutError("zu langsam")):
            with self.assertRaises(u.UpdateCheckError):
                u.fetch_latest("T", urlopen=failing_opener(error))


class SettingsTests(unittest.TestCase):

    def test_standard_ist_aus(self):
        self.assertEqual(
            u.default_settings(), {"auto_check": False, "skipped_version": ""}
        )

    def test_datei_fehlt(self):
        path = os.path.join(tempfile.gettempdir(), "gibt_es_nicht_u.json")
        self.assertEqual(u.load_settings(path), u.default_settings())

    def test_roundtrip_und_ordner_wird_angelegt(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "unter" / "u.json"
            u.save_settings(path, {"auto_check": True, "skipped_version": "v0.5.0"})
            loaded = u.load_settings(path)
            leftovers = [p.name for p in path.parent.iterdir()]

        self.assertEqual(loaded, {"auto_check": True, "skipped_version": "0.5.0"})
        self.assertEqual(leftovers, ["u.json"])

    def test_kaputte_datei(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "u.json"
            path.write_text("{kaputt", encoding="utf-8")
            self.assertEqual(u.load_settings(path), u.default_settings())

    def test_falsche_typen_und_unbekannte_schluessel(self):
        raw = {"auto_check": "ja", "skipped_version": "x", "zukunft": 1}
        self.assertEqual(u.sanitize_settings(raw), u.default_settings())
        self.assertEqual(u.sanitize_settings([1]), u.default_settings())
        self.assertEqual(u.sanitize_settings(None), u.default_settings())