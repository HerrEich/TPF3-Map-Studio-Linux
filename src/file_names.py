"""
Dateinamen fuer Ordner, die das Spiel selbst einliest (zum Beispiel biomes).
Umlaute und Sonderzeichen im Namen koennen dort Probleme machen, darum
schreibt das Studio dort nur einfache ASCII-Namen.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_UMLAUTS = {
    "\u00e4": "ae", "\u00f6": "oe", "\u00fc": "ue",
    "\u00c4": "Ae", "\u00d6": "Oe", "\u00dc": "Ue",
    "\u00df": "ss",
}


def ascii_safe_name(name: str) -> str:
    """Ersetzt Umlaute (ae, oe, ue, ss), entfernt Akzente, andere Zeichen -> _."""

    for old, new in _UMLAUTS.items():
        name = name.replace(old, new)

    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)

    return name or "datei"


def ascii_safe_path(path) -> tuple[str, bool]:
    """
    Liefert (Pfad mit ASCII-Dateiname, wurde_geaendert). Nur der Dateiname
    wird angepasst, der Ordner bleibt wie er ist.
    """

    original = Path(path)
    safe = ascii_safe_name(original.name)

    if safe == original.name:
        return str(original), False

    return str(original.with_name(safe)), True
