"""Festplatten-Cache fuer OSM-Kachelabfragen (Overpass).

Eine Datei je Abfrage: gzip-komprimiertes JSON, Dateiname = SHA-256 des
fertigen Abfragetexts (enthaelt Bounding-Box und Filter). Der Server fliesst
nicht in den Schluessel ein, die Daten sind auf jedem Overpass-Server gleich.
Aendert sich ein Filter, entsteht automatisch ein neuer Schluessel.

Geschrieben wird atomar (erst .tmp, dann umbenennen): ein Abbruch hinterlaesst
keine halben Dateien. Eintraege gelten MAX_AGE_S Sekunden, danach wird neu
geladen. Eine kaputte Datei wird verworfen und beim naechsten Mal neu geladen.
"""

import gzip
import hashlib
import json
import os
import threading
import time
import zlib
from pathlib import Path

CACHE_FORMAT = 1
MAX_AGE_S = 30 * 24 * 3600


def default_cache_dir() -> Path:
    """Unterordner osm_cache im Basisordner des Studios (wie dem_cache usw.)."""

    try:
        from src.app_paths import APP_DIR

        return Path(APP_DIR) / "osm_cache"
    except Exception:  # noqa: BLE001
        return Path.home() / ".tpf3_map_studio" / "osm_cache"


class TileCache:

    def __init__(self, directory=None, max_age_s=MAX_AGE_S, clock=time.time):

        self._directory = Path(directory) if directory is not None else None
        self.max_age_s = max_age_s
        self._clock = clock

    @property
    def directory(self) -> Path:

        if self._directory is None:
            self._directory = default_cache_dir()

        return self._directory

    @staticmethod
    def key(query: str) -> str:

        text = f"osm-tile-v{CACHE_FORMAT}\n{query}"

        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def path_for(self, query: str) -> Path:

        return self.directory / f"{self.key(query)}.json.gz"

    def get(self, query: str):
        """Gespeicherte Antwort oder None (fehlt, abgelaufen, kaputt)."""

        path = self.path_for(query)

        try:
            age = self._clock() - path.stat().st_mtime
        except OSError:
            return None

        if age > self.max_age_s:
            return None

        try:
            with gzip.open(path, "rb") as handle:
                data = json.loads(handle.read().decode("utf-8"))

            if not isinstance(data, dict) or "elements" not in data:
                raise ValueError("kein Overpass-Ergebnis")

            return data

        except (OSError, ValueError, EOFError, zlib.error):

            try:
                path.unlink()
            except OSError:
                pass

            return None

    def put(self, query: str, data) -> bool:
        """Speichert eine Antwort atomar. Gibt False zurueck, schlaegt aber nie fehl."""

        path = self.path_for(query)
        tmp = path.with_name(
            f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            payload = json.dumps(
                data, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")

            with gzip.open(tmp, "wb", compresslevel=6) as handle:
                handle.write(payload)

            os.replace(tmp, path)

            return True

        except (OSError, TypeError, ValueError):

            try:
                tmp.unlink()
            except OSError:
                pass

            return False
