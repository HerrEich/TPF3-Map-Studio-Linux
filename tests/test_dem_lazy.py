import unittest
from pathlib import Path

import numpy as np

from src.heightmap.copernicus_dem import (
    MAX_CACHED_TILES,
    DemMosaic,
    DemTile,
    LazyDemTile,
)


def _lazy_mosaic(count, loads):
    """count Kacheln nebeneinander (je 1 Grad breit, 10 x 10 Pixel)."""

    def loader(path):
        loads.append(Path(path).name)
        index = int(Path(path).stem)
        return np.full((10, 10), float(index * 100), dtype=np.float32)

    tiles = [
        LazyDemTile(
            path="%d.tif" % i,
            lon0=float(i),
            lat0=1.0,
            dlon=0.1,
            dlat=0.1,
            shape=(10, 10),
            loader=loader,
        )
        for i in range(count)
    ]
    return DemMosaic(tiles)


class LazyDemTests(unittest.TestCase):
    def test_loads_only_tiles_that_are_queried(self):
        loads = []
        mosaic = _lazy_mosaic(10, loads)
        self.assertEqual(loads, [])
        lat = np.array([[0.55]])
        lon = np.array([[3.55]])
        value = mosaic.sample_grid(lat, lon)
        self.assertAlmostEqual(float(value[0, 0]), 300.0, places=3)
        self.assertEqual(loads, ["3.tif"])

    def test_memory_stays_bounded(self):
        loads = []
        mosaic = _lazy_mosaic(12, loads)
        for i in range(12):
            mosaic.sample_grid(np.array([[0.55]]), np.array([[i + 0.55]]))
            self.assertLessEqual(len(mosaic._cache), MAX_CACHED_TILES)
        self.assertEqual(len(loads), 12)

    def test_recent_tile_is_not_reloaded(self):
        loads = []
        mosaic = _lazy_mosaic(3, loads)
        for _ in range(5):
            mosaic.sample_grid(np.array([[0.55]]), np.array([[1.55]]))
        self.assertEqual(loads, ["1.tif"])

    def test_eager_tiles_still_work(self):
        tile = DemTile(
            array=np.full((10, 10), 7.0, dtype=np.float32),
            lon0=0.0, lat0=1.0, dlon=0.1, dlat=0.1,
        )
        mosaic = DemMosaic([tile])
        value = mosaic.sample_grid(np.array([[0.55]]), np.array([[0.55]]))
        self.assertAlmostEqual(float(value[0, 0]), 7.0, places=3)

    def test_outside_is_nan(self):
        mosaic = _lazy_mosaic(2, [])
        value = mosaic.sample_grid(np.array([[0.55]]), np.array([[50.0]]))
        self.assertTrue(np.isnan(value[0, 0]))


if __name__ == "__main__":
    unittest.main()
