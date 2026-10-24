import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


class UiAufraeumenQuelltextTest(unittest.TestCase):

    def test_info_panel_startet_ausgeblendet(self):
        js = _read("map/web/js/info_panel.js")
        self.assertIn("setPanelVisible(false)", js)
        self.assertIn("setPanelVisible(true)", js)

    def test_layer_zeile_zeigt_prozent(self):
        py = _read("gui/layer_row.py")
        self.assertIn('f"{value} %"', py)
        self.assertIn("value_label", py)

    def test_anleitung_standardmaessig_eingeklappt(self):
        py = _read("gui/docks.py")
        self.assertIn("guide.setVisible(False)", py)
        self.assertIn("guide_toggle.setChecked(False)", py)

    def test_trenner_breiter(self):
        qss = _read("gui/theme.py")
        m = re.search(r"QToolBar::separator \{[^}]*width: (\d+)px", qss)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 2)


try:
    from src.gui.osm_download_status import (
        COLOR_ERROR, COLOR_OK, COLOR_WARN, event_color,
    )
except ImportError:  # PySide6 fehlt
    event_color = None


@unittest.skipIf(event_color is None, "PySide6 nicht verfuegbar")
class EventColorTest(unittest.TestCase):

    def test_farben(self):
        self.assertEqual(event_color("complete"), COLOR_OK)
        self.assertEqual(event_color("error"), COLOR_ERROR)
        self.assertEqual(event_color("switch"), COLOR_WARN)
        self.assertIsNone(event_color("request"))


if __name__ == "__main__":
    unittest.main()
