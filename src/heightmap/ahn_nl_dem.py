"""
AHN (Actueel Hoogtebestand Nederland) als weitere Hoehenquelle neben Copernicus, DGM1 und
swissALTI3D.

Das AHN ist das Hoehenmodell der Niederlande (Rijkswaterstaat und die Wasserverbaende). Die
Kacheln kommen vom WCS-Dienst von PDOK (service.pdok.nl). Je 1-km-Kachel wird das Gelaendemodell
(Coverage "dtm_05m", ohne Gebaeude und Bewuchs) mit fester Groesse von 500 x 500 Pixeln
angefordert, das ergibt genau 2 m je Pixel und passt damit auf das 1-km-Raster des Mosaiks
(dgm1_dem.Dgm1Mosaic). Eine Kachel ist rund 0,8 MB gross.

Die Niederlande liegen bis auf einen schmalen Streifen im Osten in der UTM-Zone 31
(EPSG:25831), PDOK liefert das ganze Land in dieser Zone. Deshalb wird fuer alle Karten
in den Niederlanden die Zone 31 benutzt.

Nutzungsbedingungen: das AHN steht unter CC0 1.0 (frei nutzbar); die Quellenangabe in
ATTRIBUTION ist keine Pflicht, wird aber mitgefuehrt.
"""

from __future__ import annotations

import io
import json
import re
import time
from pathlib import Path

import numpy as np
import requests

from src.heightmap.dgm1_dem import (
    MARGIN_M,
    TILE_M,
    VALID_MAX_M,
    VALID_MIN_M,
    Dgm1Cancelled,
    Dgm1Error,
    Dgm1FetchJob,
    FetchSummary,
    _required_tiles,
    _write_atomic,
    slot_is_cached,
)
from src.heightmap.utm import latlon_to_utm
from src.http_identity import USER_AGENT
from src.i18n import tr

WCS_URL = "https://service.pdok.nl/rws/ahn/wcs/v1_0"
COVERAGE = "dtm_05m"

# UTM-Zone 31 (EPSG:25831) fuer das ganze Land
NL_ZONE = 31
NL_EPSG = 25831

# 500 x 500 Pixel je 1-km-Kachel = 2 m je Pixel
TILE_PX = 500

# Grobe Umgrenzung der Niederlande (Breite min/max, Laenge min/max), um die Auswahl
# bei passenden Karten anzubieten
NL_BOUNDS = (50.7, 53.7, 3.2, 7.3)

ATTRIBUTION = "© Rijkswaterstaat / AHN (Actueel Hoogtebestand Nederland), CC0 1.0"

ORIGIN = "AHN"

# Pause zwischen zwei Downloads: der Dienst soll nicht uebermaessig belastet werden.
MIN_REQUEST_INTERVAL_S = 0.3

_TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


# ---------------------------------------------------------------------------
# Welche Kacheln braucht der Kartenausschnitt?
# ---------------------------------------------------------------------------


def required_ahn_tiles(
    selection,
    margin_m: float = MARGIN_M,
    step_m: float = 100.0,
) -> list[tuple[int, int, int]]:
    """Liste der 1-km-Kacheln (31, Ost-km, Nord-km), die das Kartenband beruehren."""

    return _required_tiles(
        selection,
        margin_m,
        step_m,
        latlon_to_utm,
        lambda _lon: NL_ZONE,
    )


def cache_file_name(ie: int, inn: int) -> str:
    """Dateiname im Zwischenspeicher, passend zu dgm1_dem.cached_files_for_slot."""

    return f"{NL_ZONE}_{ie}_{inn}__ahn"


def tile_params(ie: int, inn: int) -> dict:
    """WCS-Parameter fuer eine 1-km-Kachel (Bounding-Box genau auf dem Kilometerraster)."""

    e0, n0 = ie * TILE_M, inn * TILE_M

    return {
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGE": COVERAGE,
        "CRS": f"EPSG:{NL_EPSG}",
        "BBOX": f"{e0},{n0},{e0 + TILE_M},{n0 + TILE_M}",
        "WIDTH": TILE_PX,
        "HEIGHT": TILE_PX,
        "FORMAT": "GEOTIFF",
    }


# ---------------------------------------------------------------------------
# Abruf
# ---------------------------------------------------------------------------


def make_session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "image/tiff, */*"})
    return session


def _get(session, params, timeout=120, retries=3, sleep=time.sleep):
    """GET mit wenigen Wiederholungen bei Netzwerk- und Dienstfehlern."""

    last_error = ""

    for attempt in range(retries):

        try:
            response = session.get(WCS_URL, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_error = f"Netzwerkfehler: {exc}"
            sleep(min(20.0, 2.0 ** (attempt + 1)))
            continue

        if response.status_code == 429 or response.status_code >= 500:
            last_error = f"Dienstfehler HTTP {response.status_code}"
            sleep(min(30.0, 5.0 * (attempt + 1)))
            continue

        if response.status_code != 200:
            raise Dgm1Error(
                tr("PDOK antwortet mit HTTP {status}.").format(status=response.status_code)
            )

        return response

    raise Dgm1Error(tr("PDOK nicht erreichbar ({error}).").format(error=last_error or tr("unbekannter Fehler")))


def check_tile(content: bytes, ie: int, inn: int) -> bool:
    """
    Prueft die Antwort des Dienstes. Gibt True zurueck, wenn die Kachel Hoehenwerte enthaelt,
    False, wenn sie nur aus "keine Daten" besteht (ausserhalb der Niederlande, offenes Meer).
    Wirft Dgm1Error bei einer Fehlermeldung des Dienstes oder unlesbaren Daten.
    """

    if content[:4] not in _TIFF_MAGIC:

        text = content[:2000].decode("utf-8", errors="replace")

        if "ServiceException" in text:
            match = re.search(r"<ServiceException[^>]*>(.*?)</ServiceException>", text, re.S)
            detail = (match.group(1) if match else text).strip()[:200]
            raise Dgm1Error(
                tr("PDOK meldet einen Fehler fuer Kachel {ie}-{inn}: {detail}").format(ie=ie, inn=inn, detail=detail)
            )

        raise Dgm1Error(tr("Kachel {ie}-{inn}: Antwort von PDOK ist kein GeoTIFF.").format(ie=ie, inn=inn))

    from PIL import Image

    try:
        with Image.open(io.BytesIO(content)) as im:
            arr = np.array(im, dtype=np.float32)
    except Exception as exc:  # noqa: BLE001
        raise Dgm1Error(
            tr("Kachel {ie}-{inn}: Antwort von PDOK nicht lesbar ({exc}).").format(ie=ie, inn=inn, exc=exc)
        ) from exc

    if arr.ndim != 2:
        raise Dgm1Error(tr("Kachel {ie}-{inn}: Antwort von PDOK ist kein Hoehenraster.").format(ie=ie, inn=inn))

    valid = np.isfinite(arr) & (arr >= VALID_MIN_M) & (arr <= VALID_MAX_M)

    return bool(valid.any())


def store_tile(cache_dir: Path, ie: int, inn: int, content: bytes) -> None:
    """Legt eine geladene Kachel samt Quellenvermerk im Zwischenspeicher ab."""

    name = cache_file_name(ie, inn)

    meta = {
        "Origin": ORIGIN,
        "Attribution": ATTRIBUTION,
        "TileIndex": f"{ie}-{inn}",
        "Source": f"PDOK WCS {COVERAGE}",
    }

    _write_atomic(cache_dir / f"{name}.tif", content)
    _write_atomic(cache_dir / f"{name}.json", json.dumps(meta, ensure_ascii=False).encode("utf-8"))


def fetch_tiles_for_selection(
    selection,
    cache_dir: Path,
    progress=None,
    cancelled=None,
    min_interval_s: float = MIN_REQUEST_INTERVAL_S,
    session=None,
    sleep=time.sleep,
) -> FetchSummary:
    """
    Holt alle fehlenden AHN-Kacheln fuer den Ausschnitt. progress(done, total, text)
    wird laufend aufgerufen, cancelled() fragt den Abbruchwunsch ab (Dgm1Cancelled).
    Kacheln ohne Hoehenwerte (ausserhalb der Niederlande) werden als "keine Daten" vermerkt
    und nicht erneut angefragt.
    """

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    slots = required_ahn_tiles(selection)

    summary = FetchSummary(total=len(slots))

    todo = []

    for zone, ie, inn in slots:
        if slot_is_cached(cache_dir, zone, ie, inn):
            if (cache_dir / f"{zone}_{ie}_{inn}.none").exists():
                summary.no_data += 1
            else:
                summary.already_cached += 1
        else:
            todo.append((zone, ie, inn))

    done = len(slots) - len(todo)

    def report(text):
        if progress is not None:
            progress(done, len(slots), text)

    def check_cancel():
        if cancelled is not None and cancelled():
            raise Dgm1Cancelled("Abgebrochen.")

    if not todo:
        report("Fertig")
        return summary

    session = session or make_session()

    last_request = None

    for zone, ie, inn in todo:

        check_cancel()

        report(tr("Kachel {value} von {count}").format(value=done + 1, count=len(slots)))

        if last_request is not None:
            wait = min_interval_s - (time.monotonic() - last_request)
            if wait > 0:
                sleep(wait)

        last_request = time.monotonic()

        response = _get(session, tile_params(ie, inn), sleep=sleep)

        if check_tile(response.content, ie, inn):
            store_tile(cache_dir, ie, inn, response.content)
            summary.fetched += 1
        else:
            _write_atomic(cache_dir / f"{zone}_{ie}_{inn}.none", "keine Daten bei PDOK".encode("utf-8"))
            summary.no_data += 1

        done += 1

    report("Fertig")

    return summary


class AhnFetchJob(Dgm1FetchJob):
    """Fuehrt fetch_tiles_for_selection in einem Hintergrund-Thread aus (gleiche Schnittstelle
    wie Dgm1FetchJob, damit das Fortschrittsfenster alle Quellen nutzen kann)."""

    def _run(self) -> None:
        try:
            self.summary = fetch_tiles_for_selection(
                self.selection,
                self.cache_dir,
                progress=self._on_progress,
                cancelled=self._cancel_flag.is_set,
            )
        except Dgm1Cancelled:
            self.cancelled = True
            self.error = "Abgebrochen."
        except Exception as exc:  # noqa: BLE001 - jede Fehlerart soll in der Oberflaeche landen
            self.error = str(exc)
        finally:
            self.finished = True
