"""Kleiner animierter Zug, der den Ladefortschritt anzeigt."""

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from src.gui.train_math import ease, fraction

RAIL = QColor("#55656f")
RAIL_DONE = QColor("#15b9f9")
SLEEPER = QColor("#2a3a46")
BODY = QColor("#0a81c2")
BODY_DARK = QColor("#086aa3")
WAGON = QColor("#1a262e")
WINDOW = QColor("#d5dee5")
WHEEL = QColor("#d5dee5")
SMOKE = QColor("#8ea1af")

WAGONS = 8
LOCO_W = 34.0
WAGON_W = 20.0
GAP = 2.0
HEIGHT = 40


class TrainProgress(QWidget):
    """Gleis mit Zug: Die Zugspitze steht bei done/total."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(HEIGHT)
        self.setMaximumHeight(HEIGHT)
        self._target = 0.0
        self._shown = 0.0
        self._phase = 0.0
        self._puffs = []
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    # ---------------------------------------------------------
    # Steuerung
    # ---------------------------------------------------------

    def reset(self):
        self._target = 0.0
        self._shown = 0.0
        self._puffs = []
        self._wake()
        self.update()

    def set_progress(self, done, total):
        self._target = fraction(done, total)
        self._wake()

    def finish(self):
        """Download fertig: Zug faehrt in den Zielbahnhof."""

        self._target = 1.0
        self._wake()

    def _wake(self):
        if not self._timer.isActive():
            self._clock.start()
            self._timer.start()

    # ---------------------------------------------------------
    # Animation
    # ---------------------------------------------------------

    def _moving(self):
        return abs(self._target - self._shown) >= 0.0005

    def _tick(self):
        dt = self._clock.restart() / 1000.0
        was_moving = self._moving()
        self._shown = ease(self._shown, self._target, dt)
        if was_moving:
            self._phase += dt * 14.0
            if len(self._puffs) < 12 and int(self._phase * 2) % 3 == 0:
                self._puffs.append([0.0, 0.0])
        self._puffs = [
            [age + dt, drift + dt * 14.0]
            for age, drift in self._puffs
            if age < 1.2
        ]
        self.update()
        if not self._moving() and not self._puffs:
            self._timer.stop()

    # ---------------------------------------------------------
    # Zeichnen
    # ---------------------------------------------------------

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        margin = 10.0
        rail_y = h - 8.0
        train_len = LOCO_W + WAGONS * (WAGON_W + GAP)
        left = margin
        right = w - margin
        span = max(right - left - 0.0, 1.0)

        head_x = left + train_len + max(span - train_len, 0.0) * self._shown

        # Schwellen
        painter.setPen(QPen(SLEEPER, 2))
        x = left
        while x <= right:
            painter.drawLine(QPointF(x, rail_y - 3), QPointF(x, rail_y + 3))
            x += 9.0

        # Schiene: fertiger Teil hell, Rest grau
        painter.setPen(QPen(RAIL, 2))
        painter.drawLine(QPointF(left, rail_y), QPointF(right, rail_y))
        painter.setPen(QPen(RAIL_DONE, 2))
        painter.drawLine(QPointF(left, rail_y), QPointF(min(head_x, right), rail_y))

        # Bahnhoefe am Anfang und Ende
        for sx in (left, right):
            painter.setPen(QPen(RAIL, 2))
            painter.drawLine(QPointF(sx, rail_y - 12), QPointF(sx, rail_y + 4))

        # Rauch
        painter.setPen(Qt.NoPen)
        chimney_x = head_x - 6.0
        for age, drift in self._puffs:
            alpha = max(0, int(150 * (1.0 - age / 1.2)))
            color = QColor(SMOKE)
            color.setAlpha(alpha)
            painter.setBrush(color)
            r = 2.0 + age * 4.0
            painter.drawEllipse(
                QPointF(chimney_x - drift, rail_y - 22.0 - age * 8.0), r, r
            )

        # Wagen (hinter der Lok, also links davon)
        x_right = head_x - LOCO_W - GAP
        for _ in range(WAGONS):
            self._wagon(painter, x_right - WAGON_W, rail_y)
            x_right -= WAGON_W + GAP

        # Lok (vorn, rechts)
        self._loco(painter, head_x - LOCO_W, rail_y)

        painter.end()

    def _wheel(self, painter, cx, cy):
        painter.setPen(Qt.NoPen)
        painter.setBrush(WHEEL)
        painter.drawEllipse(QPointF(cx, cy), 3.2, 3.2)
        painter.setPen(QPen(BODY_DARK, 1))
        a = self._phase
        painter.drawLine(
            QPointF(cx - 2.4 * math.cos(a), cy - 2.4 * math.sin(a)),
            QPointF(cx + 2.4 * math.cos(a), cy + 2.4 * math.sin(a)),
        )

    def _wagon(self, painter, x, rail_y):
        painter.setPen(QPen(BODY_DARK, 1))
        painter.setBrush(WAGON)
        painter.drawRoundedRect(QRectF(x, rail_y - 17.0, WAGON_W, 12.0), 2, 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(WINDOW)
        for i in range(2):
            painter.drawRect(QRectF(x + 4.0 + i * 8.0, rail_y - 14.0, 4.0, 4.0))
        self._wheel(painter, x + 5.0, rail_y - 2.0)
        self._wheel(painter, x + WAGON_W - 5.0, rail_y - 2.0)

    def _loco(self, painter, x, rail_y):
        painter.setPen(QPen(BODY_DARK, 1))
        painter.setBrush(BODY)
        # Kessel (Fahrtrichtung ist rechts: vorn Schornstein, hinten Fuehrerhaus)
        painter.drawRoundedRect(QRectF(x + 10.0, rail_y - 18.0, LOCO_W - 10.0, 13.0), 3, 3)
        # Fuehrerhaus hinten (links), hoeher
        painter.drawRect(QRectF(x, rail_y - 24.0, 11.0, 19.0))
        # Schornstein vorn (rechts) und Dampfdom
        painter.drawRect(QRectF(x + LOCO_W - 8.0, rail_y - 25.0, 5.0, 8.0))
        painter.drawRect(QRectF(x + 18.0, rail_y - 22.0, 5.0, 5.0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(WINDOW)
        painter.drawRect(QRectF(x + 2.5, rail_y - 21.0, 5.0, 4.5))
        self._wheel(painter, x + 7.0, rail_y - 2.0)
        self._wheel(painter, x + 17.0, rail_y - 2.0)
        self._wheel(painter, x + LOCO_W - 7.0, rail_y - 2.0)
