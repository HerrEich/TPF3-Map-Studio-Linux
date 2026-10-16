"""Tests fuer die ASC-Umwandlung (src/heightmap/asc_import.py und tools/asc_zu_geotiff.py)."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.heightmap import asc_import, dgm1_dem

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


class ConvertTest(unittest.TestCase):

    def test_two_overlapping_tiles_become_one_aligned_geotiff(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _write_asc(tmp / "a.asc", 650321, 5100517)
            _write_asc(tmp / "b.asc", 651900, 5100517)
            out = tmp / "out.tif"
            calls = []

            asc_import.convert_folder(
                tmp, out, epsg=25832, pixel=4,
                on_progress=lambda d, t, n: calls.append((d, t, n)),
            )

            self.assertEqual(calls[0], (0, 2, ""))
            self.assertEqual(calls[-1][:2], (2, 2))

            info = dgm1_dem.read_raster_info(out)
            self.assertEqual(info.zone, 32)
            self.assertEqual(info.px, 4.0)
            self.assertEqual(info.e_ul, 650000)
            self.assertEqual(info.n_ul % 1000, 0)

            arr = dgm1_dem.read_raster_array(info)
            col = int((651002 - info.e_ul) / 4)
            row = int((info.n_ul - 5101002) / 4)
            self.assertAlmostEqual(
                float(arr[row, col]),
                0.01 * (651002 - 650000) + 0.02 * (5101002 - 5100000),
                delta=0.3,
            )
            self.assertGreater(len(dgm1_dem.slots_from_raster(info, 4.0)), 0)

    def test_zone_33_is_written_to_the_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _write_asc(tmp / "a.asc", 300000, 5300000, n=500, cell=2)
            asc_import.convert_folder(tmp, tmp / "o.tif", epsg=25833)
            self.assertEqual(dgm1_dem.read_raster_info(tmp / "o.tif").zone, 33)

    def test_cancel_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _write_asc(tmp / "a.asc", 650000, 5100000, n=500, cell=2)

            def stop(done, total, name):
                if done:
                    raise asc_import.AscCancelled("stop")

            with self.assertRaises(asc_import.AscCancelled):
                asc_import.convert_folder(tmp, tmp / "o.tif", on_progress=stop)

            self.assertEqual([p.name for p in tmp.glob("*.tif*")], [])

    def test_bad_cell_size_and_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with self.assertRaises(asc_import.AscImportError):
                asc_import.convert_folder(tmp, tmp / "o.tif")
            _write_asc(tmp / "a.asc", 650000, 5100000, n=300, cell=3)
            with self.assertRaises(asc_import.AscImportError):
                asc_import.convert_folder(tmp, tmp / "o.tif", pixel=4)


class DetectionTest(unittest.TestCase):

    def test_needs_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.assertFalse(asc_import.needs_conversion(tmp))
            (tmp / "x.ASC").write_text("x")
            self.assertTrue(asc_import.needs_conversion(tmp))
            (tmp / "y.tif").write_bytes(b"")
            self.assertFalse(asc_import.needs_conversion(tmp))

    def test_default_epsg(self):
        self.assertEqual(asc_import.default_epsg(11.1), 25832)
        self.assertEqual(asc_import.default_epsg(13.4), 25833)
        self.assertEqual(asc_import.default_epsg(6.0), 25832)

    def test_epsg_choices_are_utm_zones(self):
        self.assertEqual([c for c, _ in asc_import.EPSG_CHOICES], [25832, 25833, 25831])


class ToolTest(unittest.TestCase):

    def test_command_line_tool(self):
        tool = _load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _write_asc(tmp / "a.asc", 650321, 5100517, n=500, cell=2)
            tool.main([str(tmp), str(tmp / "o.tif")])
            self.assertTrue((tmp / "o.tif").exists())

    def test_no_asc_files_exits(self):
        tool = _load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                tool.main([tmp, str(Path(tmp) / "x.tif")])


if __name__ == "__main__":
    unittest.main()
