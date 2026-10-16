"""Visible per-worker download diagnostics; no download scheduling lives here."""
from urllib.parse import urlsplit

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from src.i18n import tr


def format_download_event(event):
    """Format plain text so server errors cannot inject markup into the UI."""
    fields = dict(event)
    fields['server'] = urlsplit(event.get('server', '')).netloc
    fields['next_server'] = urlsplit(event.get('next_server', '')).netloc
    state = event['state']
    if state == 'error':
        reasons = {
            429: tr('Server überlastet (HTTP 429)'),
            500: tr('Interner Serverfehler (HTTP 500)'),
            502: tr('Fehler am Server-Gateway (HTTP 502)'),
            503: tr('Server nicht verfügbar (HTTP 503)'),
            504: tr('Zeitüberschreitung am Server (HTTP 504)'),
        }
        if event.get('http_status') in reasons:
            fields['error'] = reasons[event['http_status']]
        elif event.get('error_type') in ('Timeout', 'ReadTimeout', 'ConnectTimeout'):
            fields['error'] = tr('Zeitüberschreitung bei der Verbindung')
        elif event.get('error_type') == 'ConnectionError':
            fields['error'] = tr('Verbindung fehlgeschlagen')
    prefix = tr('Spur {lane} · Kachel {tile} · Versuch {attempt}').format(lane=fields['lane'], tile=fields['tile'], attempt=fields['attempt'])
    if state == 'queued':
        detail = tr('{server}: wartet auf einen freien Anfrageplatz').format(server=fields['server'])
    elif state == 'request':
        detail = tr('{server}: Anfrage läuft').format(server=fields['server'])
    elif state == 'error':
        detail = tr('{server}: Fehler — {error}').format(server=fields['server'], error=fields['error'])
    elif state == 'switch':
        detail = tr('Serverwechsel: {server} → {next_server}').format(server=fields['server'], next_server=fields['next_server'])
    elif state in ('retry', 'countdown'):
        detail = tr('Alle Server versucht; neuer Durchgang in {seconds} s').format(seconds=fields['seconds'])
    elif state == 'complete':
        detail = tr('{server}: erfolgreich, Kachel gespeichert').format(server=fields['server'])
    elif state == 'throttled':
        detail = tr('Überlastungsbremse: höchstens eine Serveranfrage gleichzeitig')
    else:
        detail = state
    return prefix + ' — ' + detail


class OsmDownloadStatus(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(tr('OSM-Download: Server und Verlauf'), parent)
        self.setObjectName('osmDownloadStatus')
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        body = QWidget(self)
        layout = QVBoxLayout(body)
        self.summary = QLabel(body)
        self.summary.setTextFormat(Qt.PlainText)
        layout.addWidget(self.summary)
        self.cache_info = QLabel(body)
        self.cache_info.setTextFormat(Qt.PlainText)
        self.cache_info.setWordWrap(True)
        self.cache_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.cache_info)
        self.lanes = {}
        for lane in (1, 2):
            label = QLabel(body)
            label.setWordWrap(True)
            label.setTextFormat(Qt.PlainText)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.lanes[lane] = label
            layout.addWidget(label)
        self.history = QPlainTextEdit(body)
        self.history.setReadOnly(True)
        self.history.setMaximumBlockCount(500)
        self.history.setMinimumHeight(90)
        layout.addWidget(self.history)
        self.setWidget(body)

    def start(self):
        self.history.clear()
        self.cache_info.clear()
        self.summary.setText(tr('OSM-Download wird vorbereitet…'))
        for lane, label in self.lanes.items():
            label.setText(tr('Spur {lane}: bereit').format(lane=lane))
        self.show()

    def set_progress(self, done, total):
        self.summary.setText(tr('OSM: {done} von {total} Kacheln fertig').format(done=done, total=total))

    def set_cache_status(self, status):
        initial = tr("Beim Start: {cached} vollständig im Cache · {partial} teilweise vorhanden · {new} neu zu laden").format(
            cached=status['cached'], partial=status['initial_partial'], new=status['initial_new'])
        remaining = tr("Noch zu ergänzen: {partial} · Noch vollständig zu laden: {new}").format(
            partial=status['partial'], new=status['new'])
        self.cache_info.setText(initial + "\n" + remaining)
        self.set_progress(status['done'], status['total'])
        if status['done'] == status['cached']:
            needed = min(2, status['partial'] + status['new'])
            for lane in range(needed + 1, 3):
                self.lanes[lane].setText(tr("Spur {lane}: nicht benötigt – keine weitere Kachel offen").format(lane=lane))

    def update_event(self, event):
        text = format_download_event(event)
        self.lanes[event['lane']].setText(text)
        if event['state'] != 'countdown':
            scroll = self.history.verticalScrollBar()
            at_bottom = scroll.value() >= scroll.maximum() - 4
            previous = scroll.value()
            self.history.appendPlainText(event['time'] + '  ' + text)
            scroll.setValue(scroll.maximum() if at_bottom else previous)

    def finish(self, message):
        self.summary.setText(message)
        self.history.appendPlainText(message)
        for lane, label in self.lanes.items():
            label.setText(tr('Spur {lane}: Download beendet.').format(lane=lane))
