import math
import threading

import requests

from src.http_identity import USER_AGENT
from src.map.objects.selection import Selection
from src.osm.osm_parser import OSMParser
from src.osm.objects.osm_data import OSMData
from src.osm.overpass_query_builder import OverpassQueryConfig, build_query
from src.i18n import tr


# Ab dieser Kantenlaenge (reale Meter) wird in Kacheln geladen.
TILE_THRESHOLD_M = 25_000.0
# Zielkante einer Kachel und Ueberlappung (reale Meter).
TILE_SIZE_M = 20_000.0
TILE_OVERLAP_M = 200.0
TILE_RETRIES = 2

_R_EARTH = 6371008.8


def plan_tiles(selection):
    """
    Zerlegt eine grosse Auswahl in Kachel-Selections im (gedrehten)
    Raster der Auswahl. Kleine oder nicht vermessene Auswahlen kommen
    unveraendert als Liste mit einem Eintrag zurueck.
    """

    width = getattr(selection, "real_width_m", None)
    height = getattr(selection, "real_height_m", None)

    if not width or not height or max(width, height) <= TILE_THRESHOLD_M:
        return [selection]

    nx = max(1, math.ceil(width / TILE_SIZE_M))
    ny = max(1, math.ceil(height / TILE_SIZE_M))

    step_x = width / nx
    step_y = height / ny

    center_lat, center_lon = selection.center
    theta = math.radians(selection.rotation_deg)
    up = (math.sin(theta), math.cos(theta))
    right = (math.sin(theta + math.pi / 2), math.cos(theta + math.pi / 2))
    cos0 = math.cos(math.radians(center_lat))

    tiles = []

    for j in range(ny):
        for i in range(nx):

            x = -width / 2 + (i + 0.5) * step_x
            y = height / 2 - (j + 0.5) * step_y

            e = right[0] * x + up[0] * y
            n = right[1] * x + up[1] * y

            lat = center_lat + math.degrees(n / _R_EARTH)
            lon = center_lon + math.degrees(e / (_R_EARTH * cos0))

            tiles.append(
                type(selection).from_center(
                    lat,
                    lon,
                    step_x + 2 * TILE_OVERLAP_M,
                    step_y + 2 * TILE_OVERLAP_M,
                    rotation_deg=selection.rotation_deg,
                    scale_factor=1.0,
                )
            )

    return tiles


class OverpassCancelled(Exception):
    """Der Benutzer hat den OSM-Download abgebrochen."""


class OverpassClient:
    """
    Overpass-Client mit Fallback auf mehrere Server.
    """

    SERVERS = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

    def __init__(self):

        # (Verbinden, Antwort abwarten): Overpass schickt bei grossen
        # Gebieten erst nach der Berechnung Daten; die Abfrage selbst
        # erlaubt 180 s ([timeout:180]).
        self.timeout = (15, 200)
        self.parser = OSMParser()

        # Zuletzt erfolgreicher Server wird beim naechsten Download
        # zuerst gefragt - overpass-api.de ist oft ueberlastet und
        # bricht erst nach einigen Sekunden mit 504 ab, das muss nicht
        # bei jedem Download erneut abgewartet werden.
        self._preferred_server = None

        # Wird vom GUI-Thread gesetzt (cancel()), der Download-Thread
        # prueft ihn zwischen den Schritten.
        self._cancel = threading.Event()

        # Optional: on_progress(kachel, gesamt), aus dem Download-Thread.
        self.on_progress = None

    # ---------------------------------------------------------

    def cancel(self):
        """Bricht den laufenden Download ab (aus jedem Thread aufrufbar)."""
        self._cancel.set()

    def reset_cancel(self):
        self._cancel.clear()

    def _check_cancel(self):
        if self._cancel.is_set():
            raise OverpassCancelled()

    def download(
        self,
        selection: Selection,
        config: OverpassQueryConfig | None = None,
    ) -> OSMData:

        try:
            if len(plan_tiles(selection)) > 1:
                return self._download_tiled(selection, config)
            return self._download(selection, config)
        finally:
            self._cancel.clear()

    def _download(
        self,
        selection: Selection,
        config: OverpassQueryConfig | None = None,
    ) -> OSMData:

        self._check_cancel()

        query = build_query(selection, config)

        print("Overpass-Abfrage:")
        print(query)

        last_exception = None

        servers = list(self.SERVERS)

        if self._preferred_server in servers:
            servers.remove(self._preferred_server)
            servers.insert(0, self._preferred_server)

        for server in servers:

            self._check_cancel()

            print()
            print("=" * 60)
            print("Versuche Server:", server)

            try:

                response = self._post(server, query)

                print("HTTP:", response.status_code)

                response.raise_for_status()

                json_data = response.json()

                self._check_cancel()

                print("JSON erfolgreich empfangen.")

                osm = self.parser.parse(json_data)
                osm.data_timestamp = self._timestamp_of(json_data)

                self._preferred_server = server

                print()
                print("Download erfolgreich.")
                print(f"Nodes     : {osm.node_count}")
                print(f"Ways      : {osm.way_count}")
                print(f"Relations : {osm.relation_count}")

                return osm

            except requests.RequestException as exc:

                last_exception = exc

                print(type(exc).__name__)

                if hasattr(exc, "response") and exc.response is not None:

                    print("HTTP:", exc.response.status_code)

                    try:
                        print(exc.response.text)
                    except Exception:
                        pass

                else:
                    print(exc)

        raise RuntimeError(
            tr("Keiner der Overpass-Server war erreichbar.")
        ) from last_exception

    @staticmethod
    def _timestamp_of(data) -> str:
        """Datenstand der Overpass-Datenbank (osm3s.timestamp_osm_base), sonst leer."""

        try:
            return str((data.get("osm3s") or {}).get("timestamp_osm_base") or "")
        except AttributeError:
            return ""

    def _fetch_json(self, query: str) -> dict:
        """Eine Abfrage mit Server-Fallback, liefert das rohe JSON."""

        last_exception = None

        servers = list(self.SERVERS)

        if self._preferred_server in servers:
            servers.remove(self._preferred_server)
            servers.insert(0, self._preferred_server)

        for server in servers:

            self._check_cancel()

            try:

                response = self._post(server, query)

                response.raise_for_status()

                data = response.json()

                self._check_cancel()

                self._preferred_server = server

                return data

            except requests.RequestException as exc:

                last_exception = exc

                print("Server", server, "fehlgeschlagen:", type(exc).__name__)

        raise RuntimeError(
            tr("Keiner der Overpass-Server war erreichbar.")
        ) from last_exception

    def _download_tiled(self, selection, config=None) -> OSMData:
        """Laedt eine grosse Auswahl kachelweise und fuehrt die Daten zusammen."""

        tiles = plan_tiles(selection)
        total = len(tiles)

        print(f"Kachel-Download: {total} Kacheln")

        merged = {}
        stamps = []

        for index, tile in enumerate(tiles, start=1):

            self._check_cancel()

            if self.on_progress is not None:
                self.on_progress(index, total)

            query = build_query(tile, config)

            data = None

            for attempt in range(TILE_RETRIES + 1):

                try:
                    data = self._fetch_json(query)
                    break
                except RuntimeError:
                    if attempt >= TILE_RETRIES:
                        raise
                    print(f"Kachel {index}: neuer Versuch {attempt + 2}")

            stamp = self._timestamp_of(data)

            if stamp:
                stamps.append(stamp)

            for element in data.get("elements", []):
                merged[(element.get("type"), element.get("id"))] = element

        print(f"Zusammengefuehrt: {len(merged)} Elemente")

        osm = self.parser.parse({"elements": list(merged.values())})

        # Aeltester Stand aller Kacheln: die sichere Aussage ("Daten bis hoechstens ...")
        osm.data_timestamp = min(stamps) if stamps else ""

        return osm

    def _post(self, server: str, query: str):
        """
        POST in einem Hilfs-Thread, damit ein Abbruch sofort wirkt, auch
        wenn der Server minutenlang nicht antwortet. Die abgebrochene
        Anfrage laeuft im Hintergrund aus, ihr Ergebnis wird verworfen.
        """

        box = {}

        def work():
            try:
                box["response"] = requests.post(
                    server,
                    data={"data": query},
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                    timeout=self.timeout,
                )
            except Exception as exc:  # noqa: BLE001
                box["error"] = exc

        thread = threading.Thread(
            target=work, name="overpass-post", daemon=True
        )
        thread.start()

        while thread.is_alive():
            thread.join(0.2)
            self._check_cancel()

        if "error" in box:
            raise box["error"]

        return box["response"]