from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """Einklappbare Gruppe: Kopfzeile zum Anklicken, darunter der Inhalt.

    Inhalt in body_layout legen. Eingeklappt sind die Widgets nur
    versteckt, ihre Werte und Signale bleiben unveraendert.
    """

    def __init__(self, title, collapsed=True, parent=None):
        super().__init__(parent)
        self._title = title

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 2, 0, 2)
        outer.setSpacing(0)

        self.header = QPushButton()
        self.header.setCheckable(True)
        self.header.setFlat(True)
        self.header.setStyleSheet("text-align: left; padding: 6px 4px;")
        self.header.toggled.connect(self._on_toggled)
        outer.addWidget(self.header)

        self.body = QFrame()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 0, 0, 6)
        outer.addWidget(self.body)

        self.header.setChecked(not collapsed)
        self._on_toggled(not collapsed)

    def set_expanded(self, expanded):
        self.header.setChecked(bool(expanded))

    def is_expanded(self):
        return self.header.isChecked()

    def _on_toggled(self, expanded):
        self.header.setText(("\u25be " if expanded else "\u25b8 ") + self._title)
        self.body.setVisible(expanded)
