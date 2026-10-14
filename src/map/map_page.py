"""Seite des Kartenfensters: zeigt nur lokale Seiten, externe Links gehen in den Browser."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage

from src.map.link_guard import is_internal_url, opens_in_browser


class MapPage(QWebEnginePage):
    """
    Ohne diese Regel ersetzt ein Klick auf "Leaflet" unten rechts in der Karte das
    Kartenfenster durch die Website von Leaflet, und es gibt keinen Weg zurueck.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Links mit target="_blank" und window.open.
        self.newWindowRequested.connect(self._on_new_window)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):

        if not is_main_frame:
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        target = url.toString()

        if is_internal_url(target):
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        clicked = nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked

        self._open_in_browser(target, clicked)

        return False

    def _on_new_window(self, request):

        self._open_in_browser(
            request.requestedUrl().toString(), request.isUserInitiated()
        )

    @staticmethod
    def _open_in_browser(target, user_initiated):
        """Nur nach einem echten Klick: eine Seite darf nicht von selbst Fenster oeffnen."""

        if user_initiated and opens_in_browser(target):
            print("Externer Link im Browser:", target)
            QDesktopServices.openUrl(QUrl(target))
        else:
            print("Navigation im Kartenfenster blockiert:", target)
