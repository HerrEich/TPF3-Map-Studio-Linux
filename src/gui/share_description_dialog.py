"""
Dialog "Beschreibung zum Teilen": zeigt den erzeugten Text zum Kopieren.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from src.i18n import get_language, tr
from src.share_description import build_share_description


class ShareDescriptionDialog(QDialog):

    def __init__(self, parent, selection, info, params, osm_available):
        super().__init__(parent)

        self._selection = selection
        self._info = info
        self._params = dict(params)

        self.setWindowTitle(tr("Beschreibung zum Teilen"))
        self.resize(720, 560)

        layout = QVBoxLayout(self)

        format_row = QHBoxLayout()
        format_row.addWidget(QLabel(tr("Ausgabeformat:")))

        self.format_combo = QComboBox()
        self.format_combo.addItem("Markdown", "markdown")
        self.format_combo.addItem("Steam (BBCode)", "bbcode")
        self.format_combo.addItem(tr("Klartext"), "text")
        format_row.addWidget(self.format_combo, 1)
        layout.addLayout(format_row)

        language_row = QHBoxLayout()
        language_row.addWidget(QLabel(tr("Sprache des Textes:")))

        self.language_combo = QComboBox()
        self.language_combo.addItem("Deutsch", "de")
        self.language_combo.addItem("English", "en")
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(get_language()))
        )
        language_row.addWidget(self.language_combo, 1)
        layout.addLayout(language_row)

        self.osm_checkbox = QCheckBox(tr("OpenStreetMap-Hinweis aufnehmen"))
        self.osm_checkbox.setChecked(bool(osm_available))
        layout.addWidget(self.osm_checkbox)

        self.text_edit = QPlainTextEdit()
        layout.addWidget(self.text_edit, 1)

        note = QLabel(
            tr(
                "Der Text ersetzt nicht die Lizenzbedingungen der Quellen, "
                "bitte die Bedingungen der jeweiligen Quelle selbst prüfen. "
                "Beim Wechsel von Format oder Haken wird der Text neu "
                "erzeugt, eigene Änderungen gehen dabei verloren."
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        button_row = QHBoxLayout()

        self.copy_button = QPushButton(tr("In Zwischenablage kopieren"))
        self.copy_button.clicked.connect(self._copy)
        button_row.addWidget(self.copy_button)

        self.status_label = QLabel("")
        button_row.addWidget(self.status_label, 1)

        close_button = QPushButton(tr("Schließen"))
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)

        layout.addLayout(button_row)

        self._refresh()

        self.format_combo.currentIndexChanged.connect(self._refresh)
        self.language_combo.currentIndexChanged.connect(self._refresh)
        self.osm_checkbox.toggled.connect(self._refresh)

    def _refresh(self, *_):
        text = build_share_description(
            self._selection,
            self._info,
            fmt=self.format_combo.currentData(),
            osm_used=self.osm_checkbox.isChecked(),
            language=self.language_combo.currentData(),
            **self._params,
        )

        self.text_edit.setPlainText(text)
        self.status_label.setText("")

    def _copy(self):
        QApplication.clipboard().setText(self.text_edit.toPlainText())
        self.status_label.setText(tr("Kopiert."))
