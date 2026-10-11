"""
Basisordner des Studios im Benutzerverzeichnis (Cache, Einstellungen, Logs,
Overpass-Vorlagen).

Frueher hiess er .tpf2_map_studio. Beim ersten Start wird er in
.tpf3_map_studio umbenannt, damit Cache und Einstellungen erhalten bleiben
(Umbenennen auf demselben Laufwerk geht sofort, auch bei vielen GB Cache).
Klappt das nicht (zum Beispiel weil eine Datei gerade offen ist), arbeitet
das Studio mit dem alten Ordner weiter, es geht nichts verloren.
"""

from __future__ import annotations

from pathlib import Path

NEW_DIR_NAME = ".tpf3_map_studio"
LEGACY_DIR_NAME = ".tpf2_map_studio"


def resolve_app_dir(home: Path) -> Path:

    new = home / NEW_DIR_NAME
    legacy = home / LEGACY_DIR_NAME

    if new.exists():
        return new

    if legacy.is_dir():

        try:
            legacy.rename(new)
        except OSError:
            return legacy

    return new


APP_DIR = resolve_app_dir(Path.home())
