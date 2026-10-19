"""
Fortschritt und Abbrechen fuer lange Berechnungen - ohne Qt, damit die
Rechenmodule (numpy/scipy) davon abhaengen koennen und es sich ohne
Oberflaeche testen laesst.

Eine Berechnung bekommt ein TaskControl und
  * meldet mit report(anteil, text) ihren Fortschritt (0..1),
  * ruft ab und zu check() auf; nach einem Klick auf "Abbrechen" wirft das
    TaskCancelled, die Berechnung bricht an dieser Stelle sauber ab.
Alles ist thread-sicher (Berechnung in Arbeits-Threads, Anzeige im GUI-Thread).
"""

from __future__ import annotations

import threading
import time


class TaskCancelled(Exception):
    """Der Benutzer hat die Berechnung abgebrochen."""


class TaskControl:

    def __init__(self):
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._fraction = 0.0
        self._text = ""
        self._started = time.monotonic()

    # --- Berechnungsseite -------------------------------------------------

    def report(self, fraction: float | None = None, text: str | None = None):
        with self._lock:
            if fraction is not None:
                self._fraction = min(1.0, max(0.0, float(fraction)))
            if text is not None:
                self._text = text

    def check(self):
        if self._cancel.is_set():
            raise TaskCancelled()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    # --- Anzeigeseite ------------------------------------------------------

    def cancel(self):
        self._cancel.set()

    def snapshot(self) -> tuple[float, str]:
        with self._lock:
            return self._fraction, self._text

    def seconds_left(self) -> float | None:
        """Grobe Restzeit; erst nach ein paar Prozent Fortschritt sinnvoll."""

        fraction, _ = self.snapshot()

        if fraction < 0.03:
            return None

        elapsed = time.monotonic() - self._started

        return elapsed * (1.0 - fraction) / fraction


class ScaledControl:
    """
    Teilbereich start..end des Gesamtfortschritts eines TaskControl, damit ein
    Teilschritt (z. B. die Glaettung) seinen Fortschritt 0..1 melden kann.
    """

    def __init__(self, parent: "TaskControl | None", start: float, end: float):
        self.parent = parent
        self.start = start
        self.end = end

    def report(self, fraction: float | None = None, text: str | None = None):
        if self.parent is None:
            return
        if fraction is None:
            self.parent.report(None, text)
        else:
            self.parent.report(self.start + (self.end - self.start) * fraction, text)

    def check(self):
        if self.parent is not None:
            self.parent.check()

    @property
    def cancelled(self) -> bool:
        return self.parent is not None and self.parent.cancelled


def sub_control(control: "TaskControl | None", start: float, end: float, text: str | None = None):
    """
    Gibt eine Funktion report(anteil) zurueck, die einen Teilschritt auf den
    Bereich start..end des Gesamtfortschritts abbildet. control darf None sein.
    """

    def report(fraction: float):
        if control is not None:
            control.report(start + (end - start) * fraction, text)

    return report


def format_remaining(seconds: float | None) -> str:
    """'etwa 3 min', 'etwa 40 s' oder '' (unbekannt)."""

    if seconds is None:
        return ""

    seconds = max(0.0, seconds)

    if seconds < 90:
        return "%d s" % max(1, round(seconds))

    if seconds < 5400:
        return "%d min" % round(seconds / 60.0)

    return "%.1f h" % (seconds / 3600.0)
