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

    # ------------------------------------------------------------------
    # Index je Kachel: welche Merkmalsgruppen liegen schon im Cache?
    #
    # Eine Kachel kann mehrere Eintraege haben (zum Beispiel "alles ausser
    # Gebaeude" und spaeter "nur Gebaeude"). Der Index merkt sich je Kachel
    # Gruppenmenge -> Schluessel, damit beim Aktivieren eines weiteren
    # Merkmals nur das Fehlende neu geladen werden muss.

    def _index_path(self, signature: str) -> Path:

        text = f"osm-tile-index-v{CACHE_FORMAT}\n{signature}"
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return self.directory / f"idx_{digest[:40]}.json"

    def _read_index(self, signature: str) -> list:

        try:
            raw = json.loads(
                self._index_path(signature).read_text(encoding="utf-8")
            )
            entries = raw.get("entries", [])
        except (OSError, ValueError, AttributeError):
            return []

        return [
            entry for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("cats"), list)
            and isinstance(entry.get("key"), str)
        ]

    def _load(self, path: Path):
        """Wie get(), aber ueber den Dateipfad (fuer den Index)."""

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
            return None

    def register(self, signature: str, categories, query: str) -> bool:
        """
        Merkt, dass `query` (schon im Cache) fuer die Kachel `signature`
        genau die Merkmalsgruppen `categories` enthaelt. Schlaegt nie fehl.
        """

        cats = sorted(categories)

        if not cats:
            return False

        path = self._index_path(signature)
        tmp = path.with_name(
            f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )

        entries = [
            entry for entry in self._read_index(signature)
            if sorted(entry["cats"]) != cats
        ]
        entries.append({"cats": cats, "key": self.key(query)})

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps({"entries": entries}, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(tmp, path)
            return True

        except (OSError, TypeError, ValueError):

            try:
                tmp.unlink()
            except OSError:
                pass

            return False

    def find_cover(self, signature: str, wanted) -> list:
        """
        Gespeicherte Antworten dieser Kachel, deren Merkmalsgruppen alle zu
        `wanted` gehoeren (abgeschaltete Gruppen duerfen nicht wieder
        auftauchen). Gierig nach groesster Gruppenmenge gewaehlt.
        Ergebnis: Liste von (Gruppenmenge, Antwort).
        """

        wanted = set(wanted)
        usable = []

        for entry in self._read_index(signature):
            cats = set(entry["cats"])

            if cats and cats <= wanted:
                usable.append((cats, entry["key"]))

        usable.sort(key=lambda item: -len(item[0]))

        covered = set()
        chosen = []

        for cats, key in usable:

            if cats <= covered:
                continue

            data = self._load(self.directory / f"{key}.json.gz")

            if data is None:
                continue

            chosen.append((cats, data))
            covered |= cats

        return chosen

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
