import threading
import unittest
from pathlib import Path

import numpy as np

from src.core.task_control import (
    TaskCancelled,
    TaskControl,
    format_remaining,
    sub_control,
)
from src.heightmap.copernicus_dem import DemMosaic, LazyDemTile
from src.heightmap.heightmap_exporter import _sample_grid
from src.heightmap.terrain_smoothing import smooth_terrain
from src.map.objects.selection import Selection


def _mosaic(loads, n_side=4):
    """n_side x n_side Kacheln (je 0,1 Grad) mit glattem Hoehenverlauf."""

    def loader(path):
        loads.append(Path(path).name)
        i, j = (int(x) for x in Path(path).stem.split("_"))
        rows = np.arange(20, dtype=np.float32)[:, None]
        cols = np.arange(20, dtype=np.float32)[None, :]
        return (100.0 * i + 10.0 * j + rows + 2.0 * cols).astype(np.float32)

    tiles = []
    for i in range(n_side):
        for j in range(n_side):
            tiles.append(
                LazyDemTile(
                    path="%d_%d.tif" % (i, j),
                    lon0=10.0 + 0.1 * j,
                    lat0=50.0 + 0.1 * (i + 1),
                    dlon=0.005,
                    dlat=0.005,
                    shape=(20, 20),
                    loader=loader,
                )
            )
    return DemMosaic(tiles)


def _selection():
    return Selection.from_center(
        50.2, 10.2, 6000.0, 8000.0, 30.0, 0.0, scale_factor=3.0
    )


class SampleGridParallelTests(unittest.TestCase):

    def test_parallel_equals_serial(self):
        sel = _selection()
        serial = _sample_grid(sel, _mosaic([]), 120, 160, chunk=40, oversample=3, workers=1)
        parallel = _sample_grid(sel, _mosaic([]), 120, 160, chunk=40, oversample=3, workers=3)
        self.assertTrue(np.isfinite(serial).all())
        self.assertTrue(np.array_equal(serial, parallel))

    def test_oversample_loads_each_tile_once_per_strip(self):
        sel = _selection()
        loads_single = []
        _sample_grid(sel, _mosaic(loads_single), 120, 160, chunk=160, oversample=1, workers=1)
        loads_over = []
        _sample_grid(sel, _mosaic(loads_over), 120, 160, chunk=160, oversample=3, workers=1)
        # Mit neunfacher Mittelung werden nicht mehr Kacheln geladen als ohne.
        self.assertLessEqual(len(loads_over), len(loads_single))

    def test_progress_reaches_one(self):
        control = TaskControl()
        _sample_grid(_selection(), _mosaic([]), 120, 160, chunk=40, workers=2, control=control)
        self.assertAlmostEqual(control.snapshot()[0], 1.0)

    def test_cancel_stops_with_task_cancelled(self):
        control = TaskControl()
        control.cancel()
        with self.assertRaises(TaskCancelled):
            _sample_grid(_selection(), _mosaic([]), 120, 160, chunk=40, workers=2, control=control)

    def test_cache_stays_bounded_with_threads(self):
        mosaic = _mosaic([])
        _sample_grid(_selection(), mosaic, 120, 160, chunk=40, workers=3)
        self.assertLessEqual(len(mosaic._cache), 6)


class SmoothingParallelTests(unittest.TestCase):

    def test_same_result_serial_and_parallel(self):
        rng = np.random.default_rng(1)
        array = (rng.random((2400, 1200)) * 800).astype(np.float32)
        serial = smooth_terrain(array, 15.0, 4.0, workers=1)
        parallel = smooth_terrain(array, 15.0, 4.0, workers=3)
        self.assertTrue(np.array_equal(serial, parallel))
        self.assertEqual(parallel.dtype, array.dtype)

    def test_input_unchanged(self):
        array = (np.random.default_rng(2).random((2400, 1200)) * 800).astype(np.float32)
        copy = array.copy()
        smooth_terrain(array, 15.0, 4.0, workers=2)
        self.assertTrue(np.array_equal(array, copy))

    def test_zero_sigma_is_copy(self):
        array = np.ones((10, 10), dtype=np.float32)
        out = smooth_terrain(array, 0.0, 4.0)
        self.assertTrue(np.array_equal(out, array))
        self.assertIsNot(out, array)

    def test_cancel(self):
        array = np.ones((2400, 1200), dtype=np.float32)
        control = TaskControl()
        control.cancel()
        with self.assertRaises(TaskCancelled):
            smooth_terrain(array, 15.0, 4.0, workers=2, control=control)


class TaskControlTests(unittest.TestCase):

    def test_report_is_clamped(self):
        control = TaskControl()
        control.report(2.0, "x")
        self.assertEqual(control.snapshot(), (1.0, "x"))
        control.report(-1.0)
        self.assertEqual(control.snapshot()[0], 0.0)

    def test_sub_control_maps_range(self):
        control = TaskControl()
        sub_control(control, 0.5, 1.0)(0.5)
        self.assertAlmostEqual(control.snapshot()[0], 0.75)

    def test_sub_control_none_is_harmless(self):
        sub_control(None, 0.0, 1.0)(0.5)

    def test_remaining_text(self):
        self.assertEqual(format_remaining(None), "")
        self.assertEqual(format_remaining(40), "40 s")
        self.assertEqual(format_remaining(600), "10 min")

    def test_cancel_from_other_thread(self):
        control = TaskControl()
        t = threading.Thread(target=control.cancel)
        t.start(); t.join()
        with self.assertRaises(TaskCancelled):
            control.check()


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# DGM1 / swissALTI3D / AHN (Dgm1Mosaic), BEV und das Copernicus-Fallback-Mosaik
# ---------------------------------------------------------------------------

import tempfile

from src.heightmap.bev_dem import BevMosaic, latlon_to_laea, tile_path
from src.heightmap.dgm1_dem import Dgm1Mosaic, Slot
from src.heightmap.heightmap_exporter import _FallbackMosaic


def _dgm1_mosaic(skip=()):
    """UTM-Zone 32, 1-km-Kacheln mit je 10 x 10 Zellen (100 m); Hoehe = glatte Funktion."""

    slots = []
    for ie in range(560, 615):
        for inn in range(5535, 5595):
            if (ie, inn) in skip:
                continue
            rows = np.arange(10, dtype=np.float32)[:, None]
            cols = np.arange(10, dtype=np.float32)[None, :]
            cells = (ie * 3.0 + inn * 1.0 + cols * 0.3 - rows * 0.2).astype(np.float32)
            slots.append(Slot(zone=32, ie=ie, inn=inn, cell_m=100.0, cells=cells))
    return Dgm1Mosaic(slots)


class _Constant:
    parallel_safe = True

    def sample_grid(self, lat, lon):
        return np.full(np.shape(lat), 42.0, dtype=np.float32)


class OtherSourcesParallelTests(unittest.TestCase):

    def test_dgm1_is_marked_parallel_safe(self):
        self.assertTrue(_dgm1_mosaic().parallel_safe)

    def test_dgm1_parallel_equals_serial(self):
        sel = _selection()
        mosaic = _dgm1_mosaic()
        serial = _sample_grid(sel, mosaic, 120, 160, chunk=40, oversample=3, workers=1)
        parallel = _sample_grid(sel, mosaic, 120, 160, chunk=40, oversample=3, workers=3)
        self.assertTrue(np.isfinite(serial).all())
        self.assertTrue(np.array_equal(serial, parallel))

    def test_fallback_counters_and_result_are_the_same(self):
        sel = _selection()
        skip = {(ie, inn) for ie in range(560, 615) for inn in range(5535, 5565)}

        def run(workers):
            mosaic = _FallbackMosaic(_dgm1_mosaic(skip), lambda: _Constant())
            out = _sample_grid(sel, mosaic, 120, 160, chunk=40, oversample=3, workers=workers)
            return out, mosaic

        out1, m1 = run(1)
        out3, m3 = run(3)
        self.assertTrue(np.array_equal(out1, out3))
        self.assertTrue(np.isfinite(out3).all())
        self.assertEqual(m1.total_pixels, m3.total_pixels)
        self.assertEqual(m1.fallback_pixels, m3.fallback_pixels)
        self.assertGreater(m3.fallback_pixels, 0)
        self.assertEqual(m3.total_pixels, 120 * 160 * 9)

    def test_fallback_is_created_only_once(self):
        made = []

        def make():
            made.append(1)
            return _Constant()

        skip = {(ie, inn) for ie in range(560, 615) for inn in range(5535, 5595)}
        mosaic = _FallbackMosaic(_dgm1_mosaic(skip), make)
        _sample_grid(_selection(), mosaic, 120, 160, chunk=40, workers=3)
        self.assertEqual(len(made), 1)

    def test_fallback_parallel_flag_follows_primary(self):
        self.assertTrue(_FallbackMosaic(_dgm1_mosaic(), lambda: _Constant()).parallel_safe)
        self.assertFalse(_FallbackMosaic(object(), lambda: _Constant()).parallel_safe)

    def test_bev_threads_give_the_same_values_and_bounded_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            tiles = []
            for tc in range(6):
                tile = (4700000, 2650000, 2, 11, 16 + tc)
                rows, cols = np.mgrid[0:512, 0:512]
                arr = (rows * 0.5 + cols * 0.25 + tc * 100).astype(np.float32)
                path = tile_path(Path(tmp), *tile)
                path.parent.mkdir(parents=True, exist_ok=True)
                np.save(path, arr)
                tiles.append(tile)

            mosaic = BevMosaic(Path(tmp), 2, tiles)
            mosaic.prepare_parallel(3)

            lat = np.linspace(47.0700, 47.0730, 4000).reshape(40, 100)
            lon = np.linspace(15.4400, 15.4800, 4000).reshape(40, 100)
            reference = BevMosaic(Path(tmp), 2, tiles).sample_grid(lat, lon)

            results = []

            def work():
                results.append(mosaic.sample_grid(lat, lon))

            threads = [threading.Thread(target=work) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(results), 4)
            for r in results:
                np.testing.assert_array_equal(r, reference)
            self.assertLessEqual(len(mosaic._cache), 6)
            self.assertTrue(mosaic.parallel_safe)
