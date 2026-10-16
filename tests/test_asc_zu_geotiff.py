"""Test fuer tools/asc_zu_geotiff.py: ASC-Kacheln -> eine GeoTIFF, die das Studio liest."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.heightmap import dgm1_dem

ROOT = Path(__file__).resolve().parent.parent


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "asc_zu_geotiff", ROOT / "tools" / "asc_zu_geotiff.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_asc(path, x0, y0, n=1200, cell=2):
    xs = x0 + (np.arange(n) + 0.5) * cell
    ys = y0 + (np.arange(n)[::-1] + 0.5) * cell
    z = (0.01 * (xs[None, :] - 650000) + 0.02 * (ys[:, None] - 5100000)).astype(np.float32)
    z[5:10, 5:10] = -9999
    with open(path, "w") as handle:
        handle.write(
            f"ncols {n}\nnrows {n}\nxllcorner {x0}\nyllcorner {y0}\n"
            f"cellsize {cell}\nNODATA_value -9999\n"
        )
        np.savetxt(handle, z, fmt="%.2f")


class AscToGeoTiffTest(unittest.TestCase):

    def test_two_overlapping_tiles_become_one_aligned_geotiff(self):
        tool = _load_tool()

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _write_asc(tmp / "a.asc", 650321, 5100517)
            _write_asc(tmp / "b.asc", 651900, 5100517)
            out = tmp / "out.tif"

            tool.main([str(tmp), str(out), "--epsg", "25832", "--pixel", "4"])

            info = dgm1_dem.read_raster_info(out)
            self.assertEqual(info.zone, 32)
            self.assertEqual(info.px, 4.0)
            self.assertEqual(info.e_ul % 1000, 0)
            self.assertEqual(info.n_ul % 1000, 0)
            self.assertEqual(info.e_ul, 650000)

            arr = dgm1_dem.read_raster_array(info)
            col = int((651002 - info.e_ul) / 4)
            row = int((info.n_ul - 5101002) / 4)
            self.assertAlmostEqual(
                float(arr[row, col]),
                0.01 * (651002 - 650000) + 0.02 * (5101002 - 5100000),
                delta=0.3,
            )

            slots = dgm1_dem.slots_from_raster(info, 4.0)
            self.assertGreater(len(slots), 0)

    def test_no_asc_files_exits(self):
        tool = _load_tool()

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                tool.main([tmp, str(Path(tmp) / "x.tif")])


if __name__ == "__main__":
    unittest.main()
