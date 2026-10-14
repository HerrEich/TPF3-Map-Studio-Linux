"""Hintergrund-Thread fuer die Update-Pruefung.

Ein Daemon-Thread haelt das Programm beim Beenden nicht auf. Das Ergebnis
kommt ueber Signale zurueck; sie muessen mit Methoden eines QObjects im
GUI-Thread verbunden werden (keine Lambdas), damit Qt sie dort ausfuehrt.
"""

import threading

from PySide6.QtCore import QObject, Signal

from src.core.update_check import UpdateCheckError, fetch_latest
from src.i18n import tr


class UpdateBridge(QObject):

    result = Signal(object)
    failed = Signal(str)


def _run(bridge, user_agent):

    try:
        info = fetch_latest(user_agent)
    except UpdateCheckError as exc:
        message = str(exc)
        info = None
    except Exception:
        message = tr("Unerwartete Antwort von GitHub.")
        info = None

    try:
        if info is not None:
            bridge.result.emit(info)
        else:
            bridge.failed.emit(message)
    except RuntimeError:
        # Fenster wurde inzwischen geschlossen
        pass


def start_update_check(bridge, user_agent):

    thread = threading.Thread(
        target=_run,
        args=(bridge, user_agent),
        name="update-check",
        daemon=True,
    )

    thread.start()

    return thread