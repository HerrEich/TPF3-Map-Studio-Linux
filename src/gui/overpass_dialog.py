from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QCheckBox,
    QLabel,
    QComboBox,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QDialogButtonBox,
)

from src.osm.overpass_query_builder import (
    OverpassQueryConfig,
    build_query,
    load_templates,
    save_template,
    delete_template,
)
from src.i18n import tr


CATEGORY_LABELS = (
    ("railways", tr("Gleistypen")),
    ("include_tram", tr("  davon Straßenbahn (Tram) einschließen")),
    ("highways", tr("Straßentypen")),
    ("buildings", tr("Gebäude")),
    ("parks", tr("Parks / Gärten")),
    ("landuse", tr("Flächennutzung")),
    ("vegetation", tr("Vegetation (Wald, Baumreihen)")),
    ("water", tr("Gewässer")),
    ("places", tr("Orte (Städte, Dörfer)")),
    ("biome_areas", tr("Siedlung, Heide, Moor, Fels (für Biome)")),
    ("industry", tr("Industrie-Objekte (Sägewerk, Ziegelei, ...)")),
    ("nature_details", tr("Natur-Details (Hecken, Mauern)")),
)


CATEGORY_HINTS = {
    "railways": tr("Bahnhofsplan (Station Plan), Einebnung des Geländes unter Gleisen, Studio-Ansicht"),
    "include_tram": tr("Nur die Auswahl, ob Straßenbahngleise mitgeladen werden"),
    "highways": tr("Einebnung des Geländes unter Straßen, Studio-Ansicht und eigene Ebenen"),
    "buildings": tr("Einebnung unter Gebäuden, Bahnhofsgebäude im Bahnhofsplan, Studio-Ansicht"),
    "parks": tr("Biome-Maske (Gras/Park), Studio-Ansicht"),
    "landuse": tr("Biome-Maske (Acker, Wiese, Wein ...), Bauernhöfe bei den Industrien, Studio-Ansicht"),
    "vegetation": tr("Biome-Maske (Wald), Forstwirtschaft bei den Industrien, Studio-Ansicht"),
    "water": tr("Studio-Ansicht und eigene Ebenen, nicht direkt im TPF3-Editor"),
    "places": tr("Ortsdatei (Städte und Dörfer) für den TPF3-Editor"),
    "biome_areas": tr("Biome-Maske (Siedlung, Heide, Moor, Fels), Steinbrüche bei den Industrien"),
    "industry": tr("Industrien (Sägewerk, Ziegelei, ...) für den TPF3-Editor"),
    "nature_details": tr("Studio-Ansicht und eigene Ebenen (Natur-Details), nicht direkt im TPF3-Editor"),
}

CATEGORIES_INFO = tr(
    "Nur Höhenkarte, Biome-Maske, Orte, Industrien und Bahnhofsplan gehen "
    "in den TPF3-Editor. Alle anderen Daten dienen der Ansicht im Studio, "
    "eigenen Ebenen und Ableitungen. Fahre mit der Maus über eine Kategorie, "
    "um zu sehen, wofür sie gebraucht wird."
)


class OverpassQueryDialog(QDialog):
    """
    Overpass-Abfrage-Baukasten: statt die Overpass-QL-Abfrage von Hand zu
    tippen (Fehlerquelle: verlorene Klammern), werden hier einzelne
    Kategorien per Checkbox an-/ausgeschaltet und die Abfrage automatisch
    zusammengebaut - inklusive Vorschau und wiederverwendbaren Vorlagen.
    """

    def __init__(self, parent, controller):
        super().__init__(parent)

        self.controller = controller

        self.setWindowTitle(tr("Overpass-Abfrage"))
        self.setMinimumSize(560, 700)

        layout = QVBoxLayout(self)

        # -------------------------------------------------
        # Vorlagen
        # -------------------------------------------------

        templates_group = QGroupBox(tr("Vorlage"))
        templates_layout = QHBoxLayout(templates_group)

        self.template_combo = QComboBox()
        self.template_combo.addItem(tr("(keine)"))
        templates_layout.addWidget(self.template_combo)

        load_button = QPushButton(tr("Laden"))
        load_button.clicked.connect(self._load_selected_template)
        templates_layout.addWidget(load_button)

        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText(tr("Name für neue Vorlage"))
        templates_layout.addWidget(self.template_name_input)

        save_button = QPushButton(tr("Als Vorlage speichern"))
        save_button.clicked.connect(self._save_as_template)
        templates_layout.addWidget(save_button)

        delete_button = QPushButton(tr("Löschen"))
        delete_button.clicked.connect(self._delete_selected_template)
        templates_layout.addWidget(delete_button)

        layout.addWidget(templates_group)

        # -------------------------------------------------
        # Kategorien
        # -------------------------------------------------

        categories_group = QGroupBox(tr("Kategorien"))
        categories_layout = QVBoxLayout(categories_group)

        self.checkboxes: dict[str, QCheckBox] = {}

        for key, label in CATEGORY_LABELS:

            checkbox = QCheckBox(label)
            checkbox.setToolTip(CATEGORY_HINTS.get(key, ""))

            self.checkboxes[key] = checkbox

            categories_layout.addWidget(checkbox)

        self.checkboxes["railways"].toggled.connect(
            self._update_tram_enabled
        )

        info = QLabel(CATEGORIES_INFO)
        info.setWordWrap(True)
        categories_layout.addWidget(info)

        layout.addWidget(categories_group)

        self.scale_hint = QLabel()
        self.scale_hint.setWordWrap(True)
        self.scale_hint.setVisible(False)
        layout.addWidget(self.scale_hint)

        self.scale_off_button = QPushButton(
            tr("Geb\u00e4ude, Parks, Fl\u00e4chennutzung und Vegetation abschalten")
        )
        self.scale_off_button.setVisible(False)
        self.scale_off_button.clicked.connect(self._switch_off_heavy_categories)
        layout.addWidget(self.scale_off_button)

        # -------------------------------------------------
        # Vorschau
        # -------------------------------------------------

        layout.addWidget(QLabel(tr("Vorschau der resultierenden Abfrage:")))

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(
            "font-family: Consolas, monospace;"
        )
        layout.addWidget(self.preview)

        for checkbox in self.checkboxes.values():
            checkbox.toggled.connect(self._update_preview)

        # -------------------------------------------------
        # Buttons
        # -------------------------------------------------

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._apply_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._apply_config(self.controller.overpass_config)
        self._refresh_template_list()
        self._apply_scale_hint()
        self._update_preview()

    # ---------------------------------------------------------
    # Konfiguration <-> Checkboxen
    # ---------------------------------------------------------

    def _apply_config(self, config: OverpassQueryConfig):

        for key, checkbox in self.checkboxes.items():
            checkbox.setChecked(getattr(config, key))

        self._update_tram_enabled()

    def _current_config(self) -> OverpassQueryConfig:

        values = {
            key: checkbox.isChecked()
            for key, checkbox in self.checkboxes.items()
        }

        return OverpassQueryConfig(**values)

    def _update_tram_enabled(self):

        # Der Tram-Unterpunkt ergibt nur Sinn, solange Gleise ueberhaupt
        # abgefragt werden.
        self.checkboxes["include_tram"].setEnabled(
            self.checkboxes["railways"].isChecked()
        )

    # ---------------------------------------------------------
    # Vorschau
    # ---------------------------------------------------------

    def _current_selection(self):

        selection = getattr(self.controller, "selection", None)

        if callable(selection):
            selection = selection()

        if selection is None:
            project = getattr(self.controller, "project", None)
            selection = getattr(project, "selection", None)

        return selection

    def _apply_scale_hint(self):

        selection = self._current_selection()

        if selection is None or not getattr(selection, "is_scaled", False):
            return

        area_km2 = (
            (selection.real_width_m or 0.0)
            * (selection.real_height_m or 0.0)
            / 1_000_000.0
        )

        self.scale_hint.setText(
            tr(
                "Gestauchte Karte: Faktor {f:.1f}, reale Fl\u00e4che {a:.0f} km\u00b2. "
                "Geb\u00e4ude, Parks, Fl\u00e4chennutzung und Vegetation erzeugen hier "
                "sehr gro\u00dfe Datenmengen; f\u00fcr Gel\u00e4nde, Orte, Gleise und "
                "Stra\u00dfen gen\u00fcgen die \u00fcbrigen Kategorien."
            ).format(f=selection.scale_factor, a=area_km2)
        )
        self.scale_hint.setVisible(True)
        self.scale_off_button.setVisible(True)

    def _switch_off_heavy_categories(self):

        for key in ("buildings", "parks", "landuse", "vegetation"):
            if key in self.checkboxes:
                self.checkboxes[key].setChecked(False)

    def _update_preview(self):

        # Fuer die Vorschau reicht ein Platzhalter-Bbox - der tatsaechliche
        # Kartenausschnitt wird erst beim echten Download eingesetzt.
        from src.map.objects.selection import Selection

        placeholder = Selection(
            min_lat=0.0, min_lon=0.0, max_lat=0.0, max_lon=0.0
        )

        query = build_query(placeholder, self._current_config())

        self.preview.setPlainText(query.strip())

    # ---------------------------------------------------------
    # Vorlagen
    # ---------------------------------------------------------

    def _refresh_template_list(self):

        self.template_combo.clear()
        self.template_combo.addItem(tr("(keine)"))

        for name in sorted(load_templates()):
            self.template_combo.addItem(name)

    def _load_selected_template(self):

        name = self.template_combo.currentText()

        if name == tr("(keine)"):
            return

        templates = load_templates()

        config = templates.get(name)

        if config is None:
            return

        self._apply_config(config)
        self._update_preview()

    def _save_as_template(self):

        name = self.template_name_input.text().strip()

        if not name:

            QMessageBox.warning(
                self,
                tr("Kein Name"),
                tr("Bitte einen Namen für die Vorlage eingeben."),
            )

            return

        save_template(name, self._current_config())

        self.template_name_input.clear()

        self._refresh_template_list()

        index = self.template_combo.findText(name)

        if index >= 0:
            self.template_combo.setCurrentIndex(index)

    def _delete_selected_template(self):

        name = self.template_combo.currentText()

        if name == tr("(keine)"):
            return

        delete_template(name)

        self._refresh_template_list()

    # ---------------------------------------------------------
    # Übernehmen
    # ---------------------------------------------------------

    def _apply_and_close(self):

        self.controller.set_overpass_config(
            self._current_config()
        )

        self.accept()
