from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QDoubleSpinBox,
    QComboBox,
    QDialogButtonBox,
    QLabel,
)

from src.gui.map_size_presets import ALL_MAP_SIZES, get_by_label
from src.i18n import tr


class RectangleToolDialog(QDialog):
    """
    Dialog fuer das Rechteck-Tool: Mittelpunkt, TPF2-Kartengroesse und
    Drehwinkel eingeben, um ein (ggf. gedrehtes) Kartenband auf der
    Karte zu platzieren - wie bei "Real Terrain", nur direkt im Studio.
    """

    def __init__(self, parent=None, initial_center=None, initial_selection=None):
        super().__init__(parent)

        self.setWindowTitle(tr("Rechteck-Tool"))

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # -------------------------------------------------
        # Vorbelegung aus einer vorhandenen (z.B. geladenen) Auswahl:
        # initial_selection hat Vorrang vor dem aelteren initial_center,
        # da es zusaetzlich Groesse und Drehwinkel mitbringt. Nur ein
        # gedrehtes Band (width_m/height_m gesetzt) liefert sinnvolle
        # Werte fuer Groesse/Drehung - eine einfache, unrotierte Bbox
        # (z.B. aus einer alten Projektdatei) liefert nur den Mittelpunkt.
        # -------------------------------------------------

        prefill_center = initial_center
        prefill_size = None
        prefill_rotation = None
        prefill_scale = 1.0
        prefill_height = None

        if initial_selection is not None:
            prefill_center = initial_selection.center

            if initial_selection.width_m and initial_selection.height_m:
                prefill_size = (
                    initial_selection.width_m,
                    initial_selection.height_m,
                )
                prefill_rotation = initial_selection.rotation_deg
                prefill_scale = getattr(initial_selection, "scale_factor", 1.0) or 1.0
                prefill_height = getattr(initial_selection, "height_scale", None)

        # Ein explizit uebergebener Mittelpunkt (z.B. die Position eines
        # Markers) hat Vorrang vor dem Mittelpunkt der Auswahl. Groesse
        # und Drehwinkel der Auswahl bleiben dabei erhalten.
        if initial_center is not None:
            prefill_center = initial_center

        # -------------------------------------------------
        # Mittelpunkt
        # -------------------------------------------------

        self.center_lat_input = QDoubleSpinBox()
        self.center_lat_input.setRange(-90.0, 90.0)
        self.center_lat_input.setDecimals(6)
        self.center_lat_input.setSingleStep(0.001)

        self.center_lon_input = QDoubleSpinBox()
        self.center_lon_input.setRange(-180.0, 180.0)
        self.center_lon_input.setDecimals(6)
        self.center_lon_input.setSingleStep(0.001)

        if prefill_center is not None:
            lat, lon = prefill_center
            self.center_lat_input.setValue(lat)
            self.center_lon_input.setValue(lon)

        form.addRow(tr("Mittelpunkt Breite (lat):"), self.center_lat_input)
        form.addRow(tr("Mittelpunkt Länge (lon):"), self.center_lon_input)

        # -------------------------------------------------
        # Kartengröße
        # -------------------------------------------------

        self.size_combo = QComboBox()
        for size in ALL_MAP_SIZES:
            self.size_combo.addItem(size.label)

        if prefill_size is not None:
            # Naehestes Preset zur gespeicherten Groesse waehlen (Rundung
            # beim Speichern/Laden oder minimale Abweichungen sollen die
            # Zuordnung nicht verhindern).
            width_m, height_m = prefill_size
            best = min(
                ALL_MAP_SIZES,
                key=lambda s: abs(s.width_m - width_m) + abs(s.height_m - height_m),
            )
            match_index = self.size_combo.findText(best.label)
            if match_index >= 0:
                self.size_combo.setCurrentIndex(match_index)
        else:
            # Sinnvoller Standard fuer lange, gedrehte Baender, wenn
            # keine vorhandene Auswahl zum Vorbelegen da ist:
            default_size = get_by_label("Größenwahnsinnig 1:5")
            default_index = (
                self.size_combo.findText(default_size.label)
                if default_size is not None
                else -1
            )
            if default_index >= 0:
                self.size_combo.setCurrentIndex(default_index)

        self.size_combo.currentTextChanged.connect(self._update_size_label)

        form.addRow(tr("Kartengröße:"), self.size_combo)

        self.size_label = QLabel()
        form.addRow("", self.size_label)
        self._update_size_label(self.size_combo.currentText())

        # -------------------------------------------------
        # Karte stauchen
        # -------------------------------------------------

        self._setting_height = False
        self._height_manual = False

        self.scale_input = QDoubleSpinBox()
        self.scale_input.setRange(1.0, 200.0)
        self.scale_input.setDecimals(2)
        self.scale_input.setSingleStep(0.5)
        self.scale_input.setValue(max(1.0, float(prefill_scale)))
        self.scale_input.setToolTip(
            tr(
                "Wie oft die Kartengr\u00f6\u00dfe in das reale Gebiet passt. "
                "Beispiel: 3,6 km Spielkarte mit Faktor 20 ergibt 72 km reales Gebiet. "
                "Netz, St\u00e4dte und Gel\u00e4nde werden entsprechend verkleinert."
            )
        )

        form.addRow(
            tr("Stauchfaktor (1 = Originalma\u00dfstab):"), self.scale_input
        )

        self.height_scale_input = QDoubleSpinBox()
        self.height_scale_input.setRange(0.01, 2.0)
        self.height_scale_input.setDecimals(3)
        self.height_scale_input.setSingleStep(0.05)
        self.height_scale_input.setToolTip(
            tr(
                "Vorbelegt mit 1 / Stauchfaktor, damit die Berge im Verh\u00e4ltnis "
                "bleiben. Kleiner = flacher, 1 = reale H\u00f6hen."
            )
        )

        auto_height = round(1.0 / self.scale_input.value(), 3)

        if (
            prefill_height is not None
            and abs(float(prefill_height) - auto_height) > 0.002
        ):
            self._height_manual = True
            self.height_scale_input.setValue(float(prefill_height))
        else:
            self.height_scale_input.setValue(auto_height)

        form.addRow(tr("H\u00f6hen-Faktor:"), self.height_scale_input)

        self.real_label = QLabel()
        form.addRow("", self.real_label)

        self.scale_input.valueChanged.connect(self._on_scale_changed)
        self.height_scale_input.valueChanged.connect(self._on_height_changed)
        self.size_combo.currentTextChanged.connect(
            lambda _text: self._update_real_label()
        )
        self._update_real_label()

        # -------------------------------------------------
        # Drehwinkel
        # -------------------------------------------------

        self.rotation_input = QDoubleSpinBox()
        self.rotation_input.setRange(0.0, 359.99)
        self.rotation_input.setDecimals(2)
        self.rotation_input.setSingleStep(0.5)
        self.rotation_input.setSuffix(" °")

        if prefill_rotation is not None:
            self.rotation_input.setValue(prefill_rotation)

        form.addRow(tr("Drehwinkel:"), self.rotation_input)

        # -------------------------------------------------
        # Sicherheitsrand (fuer nachgelagerte Downloads)
        # -------------------------------------------------

        self.margin_input = QDoubleSpinBox()
        self.margin_input.setRange(0.0, 10_000.0)
        self.margin_input.setDecimals(0)
        self.margin_input.setSingleStep(100.0)
        self.margin_input.setValue(500.0)
        self.margin_input.setSuffix(" m")

        form.addRow(tr("Sicherheitsrand (für Downloads):"), self.margin_input)

        # -------------------------------------------------
        # Buttons
        # -------------------------------------------------

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_size_label(self, label: str):
        size = get_by_label(label)
        if size is not None:
            self.size_label.setText(
                f"{size.width_m/1000:.3f} x {size.height_m/1000:.3f} km "
                f"({size.width_px}x{size.height_px} px)"
            )
        else:
            self.size_label.setText("")

    def _on_scale_changed(self, value: float):
        if not self._height_manual:
            self._setting_height = True
            self.height_scale_input.setValue(round(1.0 / max(value, 1.0), 3))
            self._setting_height = False

        self._update_real_label()

    def _on_height_changed(self, _value: float):
        if not self._setting_height:
            self._height_manual = True

        self._update_real_label()

    def _update_real_label(self):
        size = get_by_label(self.size_combo.currentText())

        if size is None:
            self.real_label.setText("")
            return

        factor = self.scale_input.value()

        text = tr("Reale Fl\u00e4che: {w:.1f} x {h:.1f} km, H\u00f6hen x{f:.3f}").format(
            w=size.width_m * factor / 1000.0,
            h=size.height_m * factor / 1000.0,
            f=self.height_scale_input.value(),
        )

        if factor > 1.0001:
            text += tr(" - nur Copernicus als H\u00f6henquelle")

        self.real_label.setText(text)

    def values(self) -> dict:
        """Gibt die eingegebenen Werte zurueck, passend zu
        MapController.set_rotated_selection(**dialog.values())."""

        size = get_by_label(self.size_combo.currentText())

        return {
            "center_lat": self.center_lat_input.value(),
            "center_lon": self.center_lon_input.value(),
            "width_m": size.width_m,
            "height_m": size.height_m,
            "rotation_deg": self.rotation_input.value(),
            "margin_m": self.margin_input.value(),
            "scale_factor": self.scale_input.value(),
            "height_scale": self.height_scale_input.value(),
        }