"""
Lange Berechnungen im Hintergrund-Thread ausfuehren, waehrend ein Fenster mit
Fortschrittsbalken, Restzeit und "Abbrechen" angezeigt wird.

run_with_progress() blockiert den Aufrufer (wie eine normale Funktion) und gibt
das Ergebnis zurueck - die Oberflaeche bleibt dabei aber bedienbar
(Windows meldet kein "Keine Rueckmeldung"), und der Benutzer kann abbrechen.
Bricht er ab, wirft die Funktion TaskCancelled.

Die Berechnung (work(control)) laeuft in einem eigenen Thread und darf NICHT
auf Widgets zugreifen - alle Einstellungen vorher im GUI-Thread auslesen.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.core.task_control import TaskCancelled, TaskControl, format_remaining
from src.i18n import tr

PROGRESS_STEPS = 1000


class _ProgressDialog(QDialog):

    def __init__(self, parent, title: str, label: str, control: TaskControl, cancelable: bool, busy: bool = False):
        super().__init__(parent)

        self._control = control
        self._finished = False
        self._label = label

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        layout = QVBoxLayout(self)

        self.text_label = QLabel(label)
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label)

        self.bar = QProgressBar()
        # busy: Fortschritt unbekannt -> laufender Balken ohne Prozentangabe
        self.bar.setRange(0, 0 if busy else PROGRESS_STEPS)
        layout.addWidget(self.bar)

        self.time_label = QLabel("")
        layout.addWidget(self.time_label)

        self.cancel_button = QPushButton(tr("Abbrechen"))
        self.cancel_button.setVisible(cancelable)
        self.cancel_button.clicked.connect(self._cancel)
        layout.addWidget(self.cancel_button)

        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _cancel(self):

        self._control.cancel()
        self.cancel_button.setEnabled(False)
        self.text_label.setText(tr("Wird abgebrochen... (der aktuelle Schritt wird noch beendet)"))

    def _refresh(self):

        fraction, text = self._control.snapshot()

        self.bar.setValue(int(fraction * PROGRESS_STEPS))

        if not self._control.cancelled:
            self.text_label.setText(text or self._label)

        remaining = format_remaining(self._control.seconds_left())

        if remaining and not self._control.cancelled:
            self.time_label.setText(
                tr("Noch etwa {time}").format(time=remaining)
            )
        else:
            self.time_label.setText("")

    def finish(self):

        self._finished = True
        self._timer.stop()
        self.accept()

    def reject(self):
        # Esc / Schliessen: wie "Abbrechen", das Fenster bleibt bis zum Ende offen.
        if not self._finished and self.cancel_button.isVisible():
            self._cancel()

    def closeEvent(self, event):

        if self._finished:
            event.accept()
        else:
            event.ignore()


def run_with_progress(
    parent,
    title: str,
    label: str,
    work: Callable[[TaskControl], Any],
    cancelable: bool = True,
    busy: bool = False,
) -> Any:
    """
    Fuehrt work(control) im Hintergrund aus und zeigt dabei ein Fortschrittsfenster.
    Gibt das Ergebnis zurueck, reicht Fehler der Berechnung weiter und wirft
    TaskCancelled, wenn abgebrochen wurde.
    """

    control = TaskControl()
    control.report(0.0, label)

    state = {"done": False, "result": None, "error": None}

    def target():

        try:
            state["result"] = work(control)
        except BaseException as exc:  # noqa: BLE001 - wird im GUI-Thread weitergereicht
            state["error"] = exc
        finally:
            state["done"] = True

    thread = threading.Thread(target=target, name="map-studio-berechnung", daemon=True)

    dialog = _ProgressDialog(parent, title, label, control, cancelable, busy)

    poll = QTimer(dialog)
    poll.setInterval(50)

    def check_done():
        if state["done"]:
            poll.stop()
            dialog.finish()

    poll.timeout.connect(check_done)
    poll.start()

    thread.start()
    dialog.exec()

    thread.join()

    if state["error"] is not None:
        raise state["error"]

    return state["result"]
