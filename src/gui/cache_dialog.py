"""Dialog "Cache verwalten": Groesse der Hoehendaten-Caches anzeigen und leeren."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.core.cache_manager import (
    CACHE_KEYS,
    CacheError,
    cache_labels,
    clear_cache,
    default_app_dir,
    format_size,
    list_caches,
)
from src.i18n import get_language, tr


class CacheDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(tr("Cache verwalten"))
        self.setMinimumWidth(640)

        self._app_dir = default_app_dir()
        self._infos = {}
        self._rows = {}

        layout = QVBoxLayout(self)

        intro = QLabel(
            tr("Heruntergeladene H\u00f6hendaten werden zwischengespeichert, damit sie "
            "nicht erneut geladen werden m\u00fcssen. Leeren schafft Platz; die Daten "
            "werden bei Bedarf neu heruntergeladen (bei DGM1 kann das dauern). "
            "Projekte, Einstellungen und Logs bleiben unber\u00fchrt.")
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)

        labels = cache_labels()

        for row, key in enumerate(CACHE_KEYS):

            name_label = QLabel(labels[key])
            info_label = QLabel("")
            clear_button = QPushButton(tr("Leeren..."))
            open_button = QPushButton(tr("Ordner \u00f6ffnen"))

            clear_button.clicked.connect(
                lambda checked=False, k=key: self._clear(k)
            )
            open_button.clicked.connect(
                lambda checked=False, k=key: self._open_folder(k)
            )

            grid.addWidget(name_label, row, 0)
            grid.addWidget(info_label, row, 1)
            grid.addWidget(clear_button, row, 2)
            grid.addWidget(open_button, row, 3)

            self._rows[key] = (info_label, clear_button)

        self._total_label = QLabel("")
        layout.addWidget(self._total_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        refresh_button = QPushButton(tr("Aktualisieren"))
        refresh_button.clicked.connect(self._refresh)

        close_button = QPushButton(tr("Schlie\u00dfen"))
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)

        buttons.addWidget(refresh_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self._refresh()

    def _comma(self) -> bool:
        return get_language() == "de"

    def _refresh(self, *_):

        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            infos = list_caches(self._app_dir)
        finally:
            QApplication.restoreOverrideCursor()

        comma = self._comma()
        total = 0
        self._infos = {}

        for info in infos:

            total += info.size_bytes
            self._infos[info.key] = info

            label, clear_button = self._rows[info.key]

            if info.files:
                label.setText(
                    tr("{files} Dateien, {size}").format(
                        files=info.files,
                        size=format_size(info.size_bytes, comma),
                    )
                )
            else:
                label.setText(tr("leer"))

            clear_button.setEnabled(info.files > 0)

        self._total_label.setText(
            tr("Gesamt: {size}").format(size=format_size(total, comma))
        )

    def _clear(self, key):

        info = self._infos.get(key)

        if info is None or not info.files:
            return

        comma = self._comma()

        answer = QMessageBox.question(
            self,
            tr("Cache leeren"),
            tr("Den Cache \"{name}\" leeren?\n\n{size} ({files} Dateien) werden "
            "gel\u00f6scht. Die Daten werden bei Bedarf erneut heruntergeladen.").format(
                name=info.label,
                size=format_size(info.size_bytes, comma),
                files=info.files,
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        error = ""
        result = None

        QApplication.setOverrideCursor(Qt.WaitCursor)

        try:
            result = clear_cache(key, self._app_dir)
        except CacheError as exc:
            error = str(exc)
        finally:
            QApplication.restoreOverrideCursor()

        self._refresh()

        if result is None:
            QMessageBox.critical(self, tr("Fehler"), error)
            return

        text = tr("{count} Dateien gel\u00f6scht, {size} freigegeben.").format(
            count=result.deleted_files,
            size=format_size(result.freed_bytes, comma),
        )

        problems = result.failed_files + result.skipped_links

        if problems:
            text += "\n\n" + tr(
                "{count} Dateien konnten nicht gel\u00f6scht werden (vermutlich in "
                "Benutzung). Bitte das Studio neu starten und es erneut versuchen."
            ).format(count=problems)

            QMessageBox.warning(self, tr("Cache geleert"), text)

        else:
            QMessageBox.information(self, tr("Cache geleert"), text)

    def _open_folder(self, key):

        path = self._app_dir / key

        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(
                self,
                tr("Fehler"),
                tr("Der Ordner konnte nicht ge\u00f6ffnet werden:\n{path}").format(path=path)
            )