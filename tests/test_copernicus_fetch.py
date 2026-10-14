import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import requests

from src.heightmap import copernicus_dem as c
from src.map.objects.selection import Selection


def selection_at(lon):
    return Selection.from_center(
        center_lat=50.1,
        center_lon=lon,
        width_m=5000.0,
        height_m=5000.0,
        rotation_deg=0.0,
        margin_m=0.0,
    )


def wait(job, seconds=5.0):
    end = time.time() + seconds
    while not job.finished and time.time() < end:
        time.sleep(0.01)
    return job.finished


class FakeResponse:

    def __init__(self, chunks, status=200, headers=None):
        self._chunks = chunks
        self.status_code = status
        self.headers = headers if headers is not None else {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=1):
        for chunk in self._chunks:
            yield chunk


def patch_get(chunks, headers=None, status=200):
    return mock.patch.object(
        c.requests, "get", return_value=FakeResponse(chunks, status, headers)
    )


class TileTests(unittest.TestCase):

    def test_kurzname(self):
        self.assertEqual(
            c.tile_label("Copernicus_DSM_COG_10_N50_00_E007_00_DEM"), "N50 E007"
        )
        self.assertEqual(
            c.tile_label("Copernicus_DSM_COG_10_S03_00_W071_00_DEM"), "S03 W071"
        )

    def test_kurzname_fallback(self):
        self.assertEqual(c.tile_label("irgendwas"), "irgendwas")

    def test_fehlende_kacheln(self):
        selection = selection_at(8.0)
        tiles = c.required_tiles(selection)
        self.assertEqual(len(tiles), 2)

        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(c.missing_tiles(selection, folder), tiles)

            (Path(folder) / (tiles[0] + ".tif")).write_bytes(b"x")
            self.assertEqual(c.missing_tiles(selection, folder), tiles[1:])


class DownloadTileTests(unittest.TestCase):

    def test_alter_aufruf_funktioniert_weiter(self):
        with tempfile.TemporaryDirectory() as folder, patch_get([b"abc"]):
            path = c.download_tile("T", Path(folder))
            self.assertEqual(path.read_bytes(), b"abc")
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["T.tif"])

    def test_fortschritt(self):
        calls = []

        with tempfile.TemporaryDirectory() as folder, patch_get(
            [b"x" * 10, b"y" * 20], {"Content-Length": "30"}
        ):
            c.download_tile(
                "T", Path(folder), on_progress=lambda d, t: calls.append((d, t))
            )

        self.assertEqual(calls, [(10, 30), (30, 30)])

    def test_fortschritt_ohne_laengenangabe(self):
        calls = []

        with tempfile.TemporaryDirectory() as folder, patch_get([b"x" * 10]):
            c.download_tile(
                "T", Path(folder), on_progress=lambda d, t: calls.append((d, t))
            )

        self.assertEqual(calls, [(10, None)])

    def test_abbruch_laesst_keine_datei_zurueck(self):
        state = {"n": 0}

        def should_cancel():
            state["n"] += 1
            return state["n"] > 1

        with tempfile.TemporaryDirectory() as folder, patch_get([b"a", b"b", b"c"]):
            with self.assertRaises(c.DownloadCancelled):
                c.download_tile("T", Path(folder), should_cancel=should_cancel)

            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_wasserkachel_404(self):
        with tempfile.TemporaryDirectory() as folder, patch_get([], status=404):
            with self.assertRaises(FileNotFoundError):
                c.download_tile("T", Path(folder))

            self.assertEqual(list(Path(folder).iterdir()), [])


class FetchJobTests(unittest.TestCase):

    def test_schnittstelle_fuer_den_dialog(self):
        job = c.CopernicusFetchJob(selection_at(8.0), tempfile.gettempdir())

        for name in (
            "done", "total", "text", "finished", "error", "summary",
            "start", "cancel",
        ):
            self.assertTrue(hasattr(job, name), name)

        self.assertFalse(job.finished)
        self.assertIsNone(job.error)

    def test_alles_im_cache(self):
        selection = selection_at(8.0)
        calls = []

        def fake(tile_id, cache_dir, on_progress=None, should_cancel=None):
            calls.append(tile_id)

        with tempfile.TemporaryDirectory() as folder:
            for tile in c.required_tiles(selection):
                (Path(folder) / (tile + ".tif")).write_bytes(b"x")

            job = c.CopernicusFetchJob(selection, folder, downloader=fake)
            job.start()
            self.assertTrue(wait(job))

        self.assertEqual(calls, [])
        self.assertEqual(job.total, 0)
        self.assertIsNone(job.error)

    def test_erfolg_und_fortschritt(self):
        selection = selection_at(8.0)
        holder = {}
        seen = []

        def fake(tile_id, cache_dir, on_progress=None, should_cancel=None):
            on_progress(50, 100)
            seen.append(round(holder["job"].done, 2))
            on_progress(100, 100)
            seen.append(round(holder["job"].done, 2))
            (Path(cache_dir) / (tile_id + ".tif")).write_bytes(b"x")

        with tempfile.TemporaryDirectory() as folder:
            job = c.CopernicusFetchJob(selection, folder, downloader=fake)
            holder["job"] = job
            job.start()
            self.assertTrue(wait(job))

            files = sorted(p.name for p in Path(folder).iterdir())

        self.assertIsNone(job.error)
        self.assertTrue(job.summary)
        self.assertEqual(job.total, 2)
        self.assertEqual(job.done, 2.0)
        self.assertEqual(seen, [0.5, 1.0, 1.5, 2.0])
        self.assertEqual(len(files), 2)

    def test_wasserkachel_ist_kein_fehler(self):
        selection = selection_at(8.0)

        def fake(tile_id, cache_dir, on_progress=None, should_cancel=None):
            raise FileNotFoundError("nur Wasser")

        with tempfile.TemporaryDirectory() as folder:
            job = c.CopernicusFetchJob(selection, folder, downloader=fake)
            job.start()
            self.assertTrue(wait(job))

        self.assertIsNone(job.error)
        self.assertEqual(job.done, job.total)

    def test_netzwerkfehler_stoppt(self):
        selection = selection_at(8.0)
        calls = []

        def fake(tile_id, cache_dir, on_progress=None, should_cancel=None):
            calls.append(tile_id)
            raise requests.ConnectionError("weg")

        with tempfile.TemporaryDirectory() as folder:
            job = c.CopernicusFetchJob(selection, folder, downloader=fake)
            job.start()
            self.assertTrue(wait(job))

        self.assertTrue(job.error)
        self.assertIn("weg", job.error)
        self.assertEqual(len(calls), 1)

    def test_abbruch_vor_dem_start(self):
        calls = []

        def fake(tile_id, cache_dir, on_progress=None, should_cancel=None):
            calls.append(tile_id)

        with tempfile.TemporaryDirectory() as folder:
            job = c.CopernicusFetchJob(selection_at(8.0), folder, downloader=fake)
            job.cancel()
            job.start()
            self.assertTrue(wait(job))

        self.assertTrue(job.error)
        self.assertEqual(calls, [])

    def test_abbruch_waehrend_des_downloads(self):
        holder = {}
        calls = []

        def fake(tile_id, cache_dir, on_progress=None, should_cancel=None):
            calls.append(tile_id)
            holder["job"].cancel()
            if should_cancel():
                raise c.DownloadCancelled()

        with tempfile.TemporaryDirectory() as folder:
            job = c.CopernicusFetchJob(selection_at(8.0), folder, downloader=fake)
            holder["job"] = job
            job.start()
            self.assertTrue(wait(job))

        self.assertTrue(job.error)
        self.assertEqual(len(calls), 1)


class DialogWiringTests(unittest.TestCase):

    def test_heightmap_dialog_nutzt_den_job(self):
        path = Path(__file__).resolve().parents[1] / "src" / "gui" / "heightmap_dialog.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn("CopernicusFetchJob(self.selection, DEFAULT_CACHE_DIR)", text)