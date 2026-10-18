"""2D-Vorschau mit Zoom: Mausrad zoomt, Ziehen verschiebt, Doppelklick setzt
zurueck. Ersetzt das einfache QLabel im Heightmap-Dialog."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QLabel

from src.gui import zoom_math as zm
from src.i18n import tr

WHEEL_STEP = 1.25


class ZoomPreviewLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._src = None
        self._zoom = 1.0
        self._cx = 0.0
        self._cy = 0.0
        self._drag = None
        self.setMouseTracking(False)
        self.setToolTip(
            tr("Mausrad: zoomen. Mit gedrückter Maustaste ziehen: verschieben. "
               "Doppelklick: ganze Karte.")
        )

    # ---- Bild setzen -------------------------------------------------
    def set_source(self, pixmap: QPixmap) -> None:
        """Neues Bild; der Zoom bleibt erhalten, wenn die Bildgroesse gleich ist."""
        same = (
            self._src is not None
            and self._src.width() == pixmap.width()
            and self._src.height() == pixmap.height()
        )
        self._src = pixmap
        if not same:
            self._reset_view()
        super().clear()
        self.updateGeometry()
        self.update()

    def clear(self):
        self._src = None
        super().clear()

    def setText(self, text):
        self._src = None
        super().setText(text)

    def _reset_view(self):
        self._zoom = 1.0
        if self._src is not None:
            self._cx = self._src.width() / 2
            self._cy = self._src.height() / 2

    # ---- Groesse -----------------------------------------------------
    def sizeHint(self):
        if self._src is None or self._src.height() == 0:
            return super().sizeHint()
        h = 400
        return QSize(max(int(h * self._src.width() / self._src.height()), 100), h)

    def minimumSizeHint(self):
        return QSize(100, 100)

    # ---- Zeichnen ----------------------------------------------------
    def paintEvent(self, event):
        if self._src is None:
            super().paintEvent(event)
            return
        pw, ph = self._src.width(), self._src.height()
        w, h = self.width(), self.height()
        if pw == 0 or ph == 0 or w == 0 or h == 0:
            return
        src, dst = zm.visible_rects(pw, ph, w, h, self._zoom, self._cx, self._cy)
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(QRectF(*dst), self._src, QRectF(*src))
        p.end()

    # ---- Maus --------------------------------------------------------
    def wheelEvent(self, event):
        if self._src is None:
            event.ignore()
            return
        steps = event.angleDelta().y() / 120.0
        if steps == 0:
            event.ignore()
            return
        pos = event.position()
        self._zoom, self._cx, self._cy = zm.zoom_at(
            self._src.width(), self._src.height(), self.width(), self.height(),
            self._zoom, self._cx, self._cy, WHEEL_STEP ** steps, pos.x(), pos.y(),
        )
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._src is not None:
            self._drag = QPointF(event.position())
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is None or self._src is None:
            super().mouseMoveEvent(event)
            return
        pos = QPointF(event.position())
        d = pos - self._drag
        self._drag = pos
        self._cx, self._cy = zm.pan(
            self._src.width(), self._src.height(), self.width(), self.height(),
            self._zoom, self._cx, self._cy, d.x(), d.y(),
        )
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag is not None:
            self._drag = None
            self.unsetCursor()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._src is not None:
            self._reset_view()
            self.update()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
