"""
Dialog "TPF2-Karte übernehmen" (Szenario A, v0.6.0): eine TPF2-Heightmap
laden, Höhenskala und Wasserhöhe per Vorschau festlegen, Ufer bereinigen
und Heightmap plus Biome-Maske für den TPF3-Karteneditor speichern.

Gedacht für fiktive TPF2-Karten (Wasser auf einer Ebene). Karten nach
echten Höhendaten mit Flussgefälle brauchen die Gewässer aus OSM.
Die Biom-Voreinstellung ist ein Vorschlag und im Spiel noch nicht geprüft.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.file_names import ascii_safe_path
from src.heightmap.biome_mask import BIOME_NAMES, index_to_preview_rgb
from src.heightmap.tpf2_heightmap_import import (
    Tpf2HeightmapError,
    load_tpf2_heightmap,
)
from src.heightmap.tpf2_import_pipeline import (
    TPF3_MAX_M,
    TPF3_MIN_M,
    ImportSettings,
    ImportSettingsError,
    default_output_name,
    run_import,
    validate_settings,
    water_preview_rgb,
)
from src.heightmap.tpf2_water_cleanup import save_heightmap
from src.heightmap.tpf2_biome_from_height import biome_gray, save_biome_mask
from src.heightmap.tpf3_paths import find_tpf3_heightmaps_folder
from src.i18n import tr

# Vorschau rechts: groesster Rahmen, in den das Bild eingepasst wird
_PREVIEW_MAX_W = 460
_PREVIEW_MAX_H = 740
_PREVIEW_STEP = 4
_HA_TO_PX = 10000.0 / 16.0     # 1 ha = 625 Pixel bei 4 m/Pixel


class Tpf2ImportDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._hm = None
        self._result = None

        self.setWindowTitle(tr("TPF2-Karte übernehmen"))

        outer = QVBoxLayout(self)

        # links Einstellungen (scrollbar), rechts die Vorschau
        body = QHBoxLayout()
        outer.addLayout(body, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        scroll.setWidget(content)
        scroll.setMinimumWidth(520)
        body.addWidget(scroll, 3)

        layout = QVBoxLayout(content)

        preview_panel = QVBoxLayout()
        body.addLayout(preview_panel, 2)

        self.setMinimumWidth(900)
        self.resize(1120, 860)

        info = QLabel(
            tr("Übernimmt die Heightmap einer TPF2-Karte nach TPF3: Höhen "
               "und Wasserhöhe festlegen, Ufer bereinigen und eine "
               "Biome-Maske aus der Höhe erzeugen. Gedacht für fiktive "
               "Karten, bei denen alles Wasser auf einer Höhe liegt. Fels "
               "und Schnee färbt das Spiel selbst.")
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # --- Datei ------------------------------------------------
        file_row = QHBoxLayout()
        layout.addLayout(file_row)

        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText(tr("Noch keine Heightmap gewählt."))
        file_row.addWidget(self.file_edit, 1)

        file_button = QPushButton(tr("Heightmap wählen..."))
        file_button.clicked.connect(self._choose_file)
        file_row.addWidget(file_button)

        self.file_info = QLabel("")
        self.file_info.setWordWrap(True)
        layout.addWidget(self.file_info)

        # --- Höhen --------------------------------------------------
        form = QFormLayout()
        layout.addLayout(form)

        self.low_input = self._meter_box(0.0)
        form.addRow(tr("Mindesthöhe:"), self.low_input)

        self.high_input = self._meter_box(250.0)
        form.addRow(tr("Maximalhöhe:"), self.high_input)

        self.water_input = self._meter_box(0.0)
        self.water_input.setSingleStep(0.5)
        self.water_input.setDecimals(1)
        self.water_input.setToolTip(
            tr("Die PNG enthält keine Meter. Stelle die Wasserhöhe so ein, "
               "dass in der Vorschau Seen und Flüsse gefüllt sind, aber "
               "kein Land absäuft. Gleiche Höhe wie Mindesthöhe = kein Wasser.")
        )
        form.addRow(tr("Wasserhöhe:"), self.water_input)

        # --- Ufer ---------------------------------------------------
        self.cleanup_checkbox = QCheckBox(tr("Ufer bereinigen"))
        self.cleanup_checkbox.setChecked(True)
        self.cleanup_checkbox.setToolTip(
            tr("Entfernt kleine Pfützen, hebt flaches Land knapp über dem "
               "Wasser an und vertieft flaches Wasser, damit klare Ufer "
               "entstehen. Gelände weiter weg vom Wasser bleibt unverändert.")
        )
        form.addRow(self.cleanup_checkbox)

        self.margin_input = self._small_box(1.5, 0.0, 20.0, " m")
        form.addRow(tr("Land mindestens über Wasser:"), self.margin_input)

        self.depth_input = self._small_box(2.0, 0.0, 50.0, " m")
        form.addRow(tr("Wasser mindestens tief:"), self.depth_input)

        self.puddle_input = self._small_box(0.8, 0.0, 100.0, " ha")
        self.puddle_input.setDecimals(1)
        form.addRow(tr("Pfützen entfernen bis:"), self.puddle_input)

        # --- Biome --------------------------------------------------
        biome_title = QLabel(tr("Biome nach Höhe (Anteil der Landhöhe):"))
        layout.addWidget(biome_title)

        biome_form = QFormLayout()
        layout.addLayout(biome_form)

        self.low_biome = self._biome_box(0)
        biome_form.addRow(tr("Unten:"), self.low_biome)

        self.limit1_input = self._small_box(30.0, 1.0, 98.0, " %")
        self.limit1_input.setDecimals(0)
        biome_form.addRow(tr("Grenze unten/Mitte:"), self.limit1_input)

        self.mid_biome = self._biome_box(1)
        biome_form.addRow(tr("Mitte:"), self.mid_biome)

        self.limit2_input = self._small_box(70.0, 2.0, 99.0, " %")
        self.limit2_input.setDecimals(0)
        biome_form.addRow(tr("Grenze Mitte/oben:"), self.limit2_input)

        self.high_biome = self._biome_box(2)
        biome_form.addRow(tr("Oben:"), self.high_biome)

        self.water_biome = self._biome_box(0)
        biome_form.addRow(tr("Unter Wasser:"), self.water_biome)

        # --- Vorschau -----------------------------------------------
        mode_row = QHBoxLayout()
        preview_panel.addLayout(mode_row)
        mode_row.addWidget(QLabel(tr("Vorschau:")))
        self.mode_box = QComboBox()
        self.mode_box.addItem(tr("Wasser (blau)"), "water")
        self.mode_box.addItem(tr("Biome"), "biome")
        self.mode_box.currentIndexChanged.connect(self._show_preview)
        mode_row.addWidget(self.mode_box, 1)

        self.preview_label = QLabel(tr("Noch keine Vorschau."))
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(_PREVIEW_MAX_W // 2, _PREVIEW_MAX_H // 2)
        preview_panel.addWidget(self.preview_label, 1)
        layout.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        row = QHBoxLayout()
        outer.addLayout(row)

        self.preview_button = QPushButton(tr("Vorschau"))
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self._make_preview)
        row.addWidget(self.preview_button)

        self.save_height_button = QPushButton(tr("Heightmap speichern..."))
        self.save_height_button.setEnabled(False)
        self.save_height_button.clicked.connect(self._save_heightmap)
        row.addWidget(self.save_height_button)

        self.save_biome_button = QPushButton(tr("Biome-Maske speichern..."))
        self.save_biome_button.setEnabled(False)
        self.save_biome_button.clicked.connect(self._save_biome)
        row.addWidget(self.save_biome_button)

        close_button = QPushButton(tr("Schließen"))
        close_button.clicked.connect(self.reject)
        row.addWidget(close_button)

    # ---------------------------------------------------------
    # Bausteine

    @staticmethod
    def _meter_box(value: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(TPF3_MIN_M, TPF3_MAX_M)
        box.setDecimals(0)
        box.setSuffix(" m")
        box.setValue(value)
        return box

    @staticmethod
    def _small_box(value: float, low: float, high: float, suffix: str) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(low, high)
        box.setDecimals(1)
        box.setSuffix(suffix)
        box.setValue(value)
        return box

    @staticmethod
    def _biome_box(default: int) -> QComboBox:
        box = QComboBox()
        for number, name in enumerate(BIOME_NAMES):
            box.addItem(name, number)
        box.setCurrentIndex(default)
        return box

    # ---------------------------------------------------------
    # Datei

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("TPF2-Heightmap wählen"),
            str(Path.home()),
            tr("PNG (*.png)"),
        )
        if not path:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            hm = load_tpf2_heightmap(path)
        except Tpf2HeightmapError as error:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(
                self,
                tr("TPF2-Karte übernehmen"),
                self._load_error_text(error),
            )
            return
        QApplication.restoreOverrideCursor()

        self._hm = hm
        self._result = None
        self.file_edit.setText(str(hm.path))
        self.file_info.setText(self._file_info_text(hm))
        self.preview_button.setEnabled(True)
        self.save_height_button.setEnabled(False)
        self.save_biome_button.setEnabled(False)
        self.preview_label.setText(tr("Noch keine Vorschau."))
        self.status_label.setText("")

    @staticmethod
    def _load_error_text(error: Tpf2HeightmapError) -> str:
        texts = {
            "missing": tr("Die Datei wurde nicht gefunden."),
            "read": tr("Die Datei konnte nicht als Bild gelesen werden."),
            "mode": tr("Das Bild ist kein Graustufenbild. Erwartet wird eine "
                       "16-Bit-Graustufen-PNG wie aus dem TPF2-Ordner heightmaps."),
            "range": tr("Das Bild enthält Werte außerhalb von 16 Bit."),
            "shape": tr("Das Bild ist zu klein oder hat mehrere Farbkanäle."),
        }
        return texts.get(error.code, tr("Die Heightmap konnte nicht geladen werden."))

    @staticmethod
    def _file_info_text(hm) -> str:
        text = tr("{w} x {h} Pixel = {wkm:.2f} x {hkm:.2f} km.").format(
            w=hm.width_px, h=hm.height_px,
            wkm=hm.width_m / 1000.0, hkm=hm.height_m / 1000.0,
        )
        if hm.map_sizes:
            labels = tr(" oder ").join(m.label for m in hm.map_sizes)
            text += " " + tr("Kartengröße: {labels}.").format(labels=labels)
            if hm.rotated:
                text += " " + tr("Das Bild liegt quer zu dieser Kartengröße.")
        else:
            text += " " + tr("Keine bekannte TPF3-Kartengröße – der "
                             "Karteneditor nimmt die Datei eventuell nicht an.")
        if hm.is_8bit:
            text += " " + tr("Das Bild hat nur 8 Bit und wurde auf 16 Bit "
                             "gestreckt; Höhenstufen können sichtbar sein.")
        return text

    # ---------------------------------------------------------
    # Einstellungen und Vorschau

    def _settings(self) -> ImportSettings | None:
        l1 = self.limit1_input.value() / 100.0
        l2 = self.limit2_input.value() / 100.0
        if l1 >= l2:
            QMessageBox.information(
                self,
                tr("TPF2-Karte übernehmen"),
                tr("Die untere Biom-Grenze muss kleiner als die obere sein."),
            )
            return None
        settings = ImportSettings(
            low_m=self.low_input.value(),
            high_m=self.high_input.value(),
            water_m=self.water_input.value(),
            cleanup=self.cleanup_checkbox.isChecked(),
            margin_m=self.margin_input.value(),
            depth_m=self.depth_input.value(),
            min_area_px=int(round(self.puddle_input.value() * _HA_TO_PX)),
            bands=(
                (l1, int(self.low_biome.currentData())),
                (l2, int(self.mid_biome.currentData())),
                (1.0, int(self.high_biome.currentData())),
            ),
            water_biome=int(self.water_biome.currentData()),
        )
        texts = {
            "limits": tr("Höhen müssen zwischen -20 und 3177 m liegen (Grenzen des TPF3-Imports)."),
            "order": tr("Die Maximalhöhe muss größer als die Mindesthöhe sein."),
            "water": tr("Die Wasserhöhe muss zwischen Mindest- und Maximalhöhe liegen."),
        }
        try:
            validate_settings(settings)
        except ImportSettingsError as error:
            QMessageBox.information(self, tr("TPF2-Karte übernehmen"),
                                    texts.get(error.code, str(error)))
            return None
        return settings

    def _make_preview(self):
        if self._hm is None:
            return
        settings = self._settings()
        if settings is None:
            return

        self.status_label.setText(tr("Berechne ..."))
        self.repaint()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._result = run_import(self._hm.raw, settings)
        except Exception as error:
            QApplication.restoreOverrideCursor()
            self.status_label.setText("")
            QMessageBox.warning(
                self,
                tr("TPF2-Karte übernehmen"),
                tr("Die Berechnung ist fehlgeschlagen:\n{error}").format(error=error),
            )
            return
        QApplication.restoreOverrideCursor()

        self._show_preview()
        self.save_height_button.setEnabled(True)
        self.save_biome_button.setEnabled(True)

    def _show_preview(self, *_):
        result = self._result
        if result is None:
            return

        if self.mode_box.currentData() == "biome":
            index = result.biome_index[::_PREVIEW_STEP, ::_PREVIEW_STEP]
            rgb = np.ascontiguousarray(index_to_preview_rgb(index))
        else:
            rgb = water_preview_rgb(result.raw, result.settings, step=_PREVIEW_STEP)

        image = QImage(
            rgb.data, rgb.shape[1], rgb.shape[0], rgb.shape[1] * 3,
            QImage.Format_RGB888,
        ).copy()
        self.preview_label.setPixmap(
            QPixmap.fromImage(image).scaled(
                _PREVIEW_MAX_W, _PREVIEW_MAX_H,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
        )

        text = tr("Wasser: {share:.2f} % der Karte.").format(share=100 * result.flooded_share)
        if result.cleanup is not None:
            text += " " + tr(
                "Ufer bereinigt: {puddles} Pfützen entfernt, {raised} Pixel "
                "angehoben, {lowered} Pixel vertieft."
            ).format(
                puddles=result.cleanup.puddles_removed,
                raised=result.cleanup.raised_px,
                lowered=result.cleanup.lowered_px,
            )
        counts = np.bincount(result.biome_index.ravel(), minlength=len(BIOME_NAMES))
        total = max(1, int(counts.sum()))
        parts = [
            f"{BIOME_NAMES[i].split(' - ')[0]}: {100 * counts[i] / total:.0f} %"
            for i in range(len(BIOME_NAMES)) if counts[i] > 0
        ]
        self.status_label.setText(text + " " + ", ".join(parts))

    def _current_result(self):
        """Ergebnis passend zu den aktuellen Einstellungen (neu rechnen, wenn geändert)."""
        settings = self._settings()
        if settings is None:
            return None
        if self._result is None or self._result.settings != settings:
            self._make_preview()
        return self._result

    # ---------------------------------------------------------
    # Speichern

    def _ask_path(self, title: str, folder: Path, name: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(
            self, title, str(folder / name), tr("PNG (*.png)")
        )
        if not path:
            return None
        if self._hm is not None and Path(path).resolve() == self._hm.path.resolve():
            QMessageBox.information(
                self, title,
                tr("Bitte einen anderen Dateinamen wählen – die TPF2-Datei "
                   "wird nicht überschrieben."),
            )
            return None
        return path

    def _heightmap_folder(self) -> Path:
        folder = find_tpf3_heightmaps_folder()
        return folder if folder is not None else Path.home()

    def _save_heightmap(self):
        result = self._current_result()
        if result is None or self._hm is None:
            return
        path = self._ask_path(
            tr("Heightmap speichern"), self._heightmap_folder(),
            default_output_name(self._hm.path, "tpf3"),
        )
        if path is None:
            return
        path, renamed = ascii_safe_path(path)
        try:
            save_heightmap(path, result.raw)
        except OSError as error:
            QMessageBox.warning(
                self, tr("Heightmap speichern"),
                tr("Die Datei konnte nicht gespeichert werden:\n{error}").format(error=error),
            )
            return
        s = result.settings
        QMessageBox.information(
            self,
            tr("Heightmap speichern"),
            tr("Gespeichert:\n{path}\n\nIm Spiel: Karteneditor → Heightmap "
               "importieren → diese Datei wählen und eintragen:\n"
               "Mindesthöhe {low:g}, Maximalhöhe {high:g}, Wasserhöhe {water:g}").format(
                path=path, low=s.low_m, high=s.high_m, water=s.water_m)
            + (
                tr("\n\nDer Dateiname wurde ohne Umlaute und Sonderzeichen "
                   "gespeichert, weil sie im Spiel Probleme machen können.")
                if renamed else ""
            ),
        )

    def _save_biome(self):
        result = self._current_result()
        if result is None or self._hm is None:
            return
        heightmaps = self._heightmap_folder()
        biomes = heightmaps.parent / "biomes"
        folder = biomes if biomes.is_dir() else heightmaps
        path = self._ask_path(
            tr("Biome-Maske speichern"), folder,
            default_output_name(self._hm.path, "biome"),
        )
        if path is None:
            return
        path, renamed = ascii_safe_path(path)
        try:
            save_biome_mask(path, biome_gray(result.biome_index))
        except OSError as error:
            QMessageBox.warning(
                self, tr("Biome-Maske speichern"),
                tr("Die Datei konnte nicht gespeichert werden:\n{error}").format(error=error),
            )
            return
        QMessageBox.information(
            self,
            tr("Biome-Maske speichern"),
            tr("Gespeichert:\n{path}\n\nIm Spiel: Karteneditor → Heightmap importieren → Reiter Biome → bei \"Biome\" diese Datei wählen, Berge und Flüsse leer lassen → Anwenden.").format(path=path)
            + (
                tr("\n\nDer Dateiname wurde ohne Umlaute und Sonderzeichen "
                   "gespeichert, weil sie im Spiel Probleme machen können.")
                if renamed else ""
            ),
        )
