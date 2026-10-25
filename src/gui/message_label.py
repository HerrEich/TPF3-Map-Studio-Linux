import re

from PySide6.QtWidgets import QLabel

# Signalfarben: Grundfarbe und Schriftfarbe des Studios bleiben unveraendert,
# nur Streifen links und eine leicht getoente Flaeche zeigen die Art der Meldung.
LEVEL_COLORS = {
    "ok": ("#3fb27f", "#12291f"),
    "warn": ("#e0a030", "#2b2412"),
    "error": ("#e05555", "#2e1717"),
    "info": ("#1796dc", "#12283a"),
}

_ERROR = re.compile(r"fehlgeschlagen|failed", re.IGNORECASE)
_WARN = re.compile(
    r"Achtung|Warnung|Warning|Attention|zu hoch|too high|"
    r"Keine OSM-Daten|No OSM data|keine Wirkung|no effect",
    re.IGNORECASE,
)
_OK = re.compile(r"^(Geladen|Loaded)")


class MessageLabel(QLabel):
    """Label, das sich nach dem Text einfaerbt (ok, warn, error, info).

    Ohne default_level bleibt ein Text ohne Signalwort unveraendert
    (normales Label). Leerer Text blendet das Label aus.
    """

    def __init__(self, text="", default_level=None, parent=None):
        super().__init__(parent)
        self._default_level = default_level
        self.setWordWrap(True)
        self.setText(text)

    def level_for(self, text):
        if _ERROR.search(text):
            return "error"
        if _WARN.search(text):
            return "warn"
        if _OK.search(text):
            return "ok"
        return self._default_level

    def setText(self, text):
        super().setText(text)
        level = self.level_for(text) if text else None
        if level is None:
            self.setStyleSheet("")
        else:
            bar, fill = LEVEL_COLORS[level]
            self.setStyleSheet(
                "QLabel { background-color: %s; border-left: 4px solid %s; "
                "border-radius: 4px; padding: 6px 10px; }" % (fill, bar)
            )
        if self._default_level is not None:
            self.setVisible(bool(text))
