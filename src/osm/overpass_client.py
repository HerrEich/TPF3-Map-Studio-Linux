import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from src.http_identity import USER_AGENT
from src.map.objects.selection import Selection
from src.osm.osm_parser import OSMParser
from src.osm.objects.osm_data import OSMData
from src.osm.overpass_query_builder import (
    OverpassQueryConfig,
    area_filter,
    build_query,
    config_from_categories,
    query_categories,
)
from src.osm.tile_cache import TileCache
from src.i18n import tr


# Ab dieser Kantenlaenge (reale Meter) wird in Kacheln geladen.
TILE_THRESHOLD_M = 25_000.0
# Festes, an der Weltkarte verankertes Kachelraster: Kantenlaenge in Grad
# Breite (ca. 11 km). Die Laengengrad-Schrittweite je Breitenband wird
# daraus abgeleitet. Weil das Raster nicht von Auswahl, Drehung oder
# Stauchfaktor abhaengt, bleiben gleiche Kacheln im Cache wiederverwendbar.
TILE_GRID_DEG = 0.1
TILE_RETRIES = 4
# Wartezeit (s) vor dem 2., 3., ... Versuch einer Kachel, falls der Server
# keinen Retry-After nennt. Overpass ist oft minutenlang ueberlastet.
BACKOFF_S = (10.0, 30.0, 60.0, 90.0)
# Vorruebergehende Fehler: warten und erneut versuchen.
TRANSIENT_STATUS = (429, 500, 502, 503, 504)
# Gleichzeitige Kachel-Anfragen (bei 429/504 faellt es auf 1 zurueck) und
# Obergrenze fuer die Wartezeit nach einem Retry-After-Hinweis.
TILE_WORKERS = 2
MAX_RETRY_AFTER_S = 60.0

_R_EARTH = 6371008.8


def _lon_step(band):
    """Laengengrad-Schrittweite des Breitenbands `band` (feste, gerundete Zahl)."""

    mid = math.radians((band + 0.5) * TILE_GRID_DEG)

    return round(TILE_GRID_DEG / max(math.cos(mid), 0.05), 3)


def _overlaps(poly, box):
    """Schneidet das konvexe Polygon (lon, lat)-Punkte das Rechteck box? (SAT)"""

    x0, y0, x1, y1 = box
    rect = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    axes = [(1.0, 0.0), (0.0, 1.0)]

    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        axes.append((-(by - ay), bx - ax))

    for nx, ny in axes:

        if nx == 0 and ny == 0:
            continue

        p = [nx * x + ny * y for x, y in poly]
        r = [nx * x + ny * y for x, y in rect]

        if max(p) < min(r) or max(r) < min(p):
            return False

    return True


def plan_tiles(selection):
    """
    Zerlegt eine grosse Auswahl in Kacheln eines festen Weltrasters
    (TILE_GRID_DEG Grad Breite, Laengenschritt je Breitenband). Nur Kacheln,
    die das (ggf. gedrehte) Auswahlband beruehren, werden geladen. Da das
    Raster nicht von Mittelpunkt, Drehung oder Stauchfaktor abhaengt, treffen
    geaenderte Einstellungen dieselben Kacheln wieder im Cache.
    Kleine oder nicht vermessene Auswahlen kommen unveraendert als Liste mit
    einem Eintrag zurueck.
    """

    width = getattr(selection, "real_width_m", None)
    height = getattr(selection, "real_height_m", None)

    if not width or not height or max(width, height) <= TILE_THRESHOLD_M:
        return [selection]

    corners = selection.corners_latlon()
    lats = [c[0] for c in corners]
    lons = [c[1] for c in corners]
    poly = [(lon, lat) for lat, lon in corners]

    d = TILE_GRID_DEG
    tiles = []

    for band in range(math.floor(min(lats) / d), math.floor(max(lats) / d) + 1):

        lat0 = round(band * d, 6)
        lat1 = round((band + 1) * d, 6)
        step = _lon_step(band)

        for k in range(math.floor(min(lons) / step), math.floor(max(lons) / step) + 1):

            lon0 = round(k * step, 6)
            lon1 = round((k + 1) * step, 6)

            if _overlaps(poly, (lon0, lat0, lon1, lat1)):
                tiles.append(
                    type(selection)(
                        min_lat=lat0, min_lon=lon0,
                        max_lat=lat1, max_lon=lon1,
                    )
                )

    return tiles


class OverpassRemarkError(requests.RequestException):
    """Overpass antwortet mit HTTP 200, meldet aber im Feld 'remark' einen Abbruch."""


def _check_remark(data):
    """Wirft OverpassRemarkError, wenn die Antwort unvollstaendig ist (Timeout/Speicher)."""

    try:
        remark = str(data.get("remark") or "")
    except AttributeError:
        return

    low = remark.lower()

    if remark and ("runtime error" in low or "timed out" in low or "out of memory" in low):
        raise OverpassRemarkError(remark)


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

        # Festplatten-Cache je Kachelabfrage (projektuebergreifend).
        # use_cache=False laedt alles neu und aktualisiert den Cache.
        self.tile_cache = TileCache()
        self.use_cache = True
        self.last_cache_hits = 0

        # Parallele Kachel-Anfragen: workers ist die Obergrenze, _allowed der
        # aktuell erlaubte Wert (faellt bei 429/504 auf 1).
        self.workers = TILE_WORKERS
        self._gate = threading.Condition()
        self._allowed = 1
        self._active = 0
        self._tls = threading.local()

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

    # ---------------------------------------------------------
    # Cache je Kachel und Merkmalsgruppe (nur Fehlendes nachladen)

    @staticmethod
    def _signature(tile):
        """Kennung der Kachel im Cache (ihr Gebietsfilter) oder None."""

        try:
            return area_filter(tile)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _merge_results(datas):
        """Fuehrt mehrere Overpass-Antworten zusammen (aeltester Datenstand)."""

        merged = {}
        stamps = []

        for data in datas:

            stamp = OverpassClient._timestamp_of(data)

            if stamp:
                stamps.append(stamp)

            for element in data.get("elements", []):
                merged[(element.get("type"), element.get("id"))] = element

        result = {"elements": list(merged.values())}

        if stamps:
            result["osm3s"] = {"timestamp_osm_base": min(stamps)}

        return result

    def _cached_tile(self, tile, config, query):
        """
        Schaut im Cache nach: (Antwort, None) wenn alles da ist, sonst
        (None, Plan) mit der Abfrage nur der fehlenden Merkmale, sonst
        (None, None) wenn die Kachel komplett geladen werden muss.
        """

        if not self.use_cache:
            return None, None

        cached = self.tile_cache.get(query)

        if cached is not None:
            return cached, None

        signature = self._signature(tile)

        if signature is None:
            return None, None

        wanted = query_categories(config)
        entries = self.tile_cache.find_cover(signature, wanted)

        if not entries:
            return None, None

        covered = set()

        for cats, _data in entries:
            covered |= cats

        missing = set(wanted) - covered
        datas = [data for _cats, data in entries]

        if not missing:
            merged = self._merge_results(datas)
            self.tile_cache.put(query, merged)
            self.tile_cache.register(signature, wanted, query)
            return merged, None

        return None, {
            "signature": signature,
            "wanted": wanted,
            "missing": missing,
            "query": build_query(tile, config_from_categories(missing)),
            "datas": datas,
        }

    def _complete_tile(self, tile, config, query, plan, fresh):
        """
        Nach dem Laden: Teilantwort mit den Cache-Teilen zusammenfuehren und
        im Index vermerken. `fresh` liegt schon unter der geladenen Abfrage
        im Cache. Ergebnis: die vollstaendige Antwort fuer diese Kachel.
        """

        if plan is not None:

            self.tile_cache.register(
                plan["signature"], plan["missing"], plan["query"]
            )

            merged = self._merge_results(plan["datas"] + [fresh])
            self.tile_cache.put(query, merged)
            self.tile_cache.register(plan["signature"], plan["wanted"], query)

            return merged

        signature = self._signature(tile)

        if signature is not None:
            self.tile_cache.register(signature, query_categories(config), query)

        return fresh

    def _download(
        self,
        selection: Selection,
        config: OverpassQueryConfig | None = None,
    ) -> OSMData:

        self._check_cancel()

        query = build_query(selection, config)

        cached, plan = self._cached_tile(selection, config, query)

        if cached is not None:
            print("Overpass-Cache: Daten aus dem Cache")
            self.last_cache_hits = 1
            osm = self.parser.parse(cached)
            osm.data_timestamp = self._timestamp_of(cached)
            return osm

        self.last_cache_hits = 0
        fetch_query = plan["query"] if plan else query

        print("Overpass-Abfrage:")
        print(fetch_query)

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

                response = self._post(server, fetch_query)

                print("HTTP:", response.status_code)

                response.raise_for_status()

                json_data = response.json()

                self._check_cancel()

                print("JSON erfolgreich empfangen.")

                _check_remark(json_data)

                self.tile_cache.put(fetch_query, json_data)
                json_data = self._complete_tile(
                    selection, config, query, plan, json_data
                )

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
        failures = []

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

                _check_remark(data)

                self._check_cancel()

                self._preferred_server = server

                return data

            except requests.RequestException as exc:

                last_exception = exc

                status = getattr(getattr(exc, "response", None), "status_code", None)
                label = type(exc).__name__ + (f" (HTTP {status})" if status else "")
                if isinstance(exc, OverpassRemarkError):
                    label += ": " + str(exc)[:80]
                print("Server", server, "fehlgeschlagen:", label)
                failures.append(server.split("/")[2] + ": " + label)

                self._note_overload(getattr(exc, "response", None))

        raise RuntimeError(
            tr("Keiner der Overpass-Server war erreichbar.")
            + " (" + "; ".join(failures) + ")"
        ) from last_exception

    def _download_tiled(self, selection, config=None) -> OSMData:
        """Laedt eine grosse Auswahl kachelweise und fuehrt die Daten zusammen."""

        tiles = plan_tiles(selection)
        total = len(tiles)

        print(f"Kachel-Download: {total} Kacheln")

        merged = {}
        stamps = []

        queries = [build_query(tile, config) for tile in tiles]
        fetch_queries = list(queries)
        plans = [None] * total
        results = [None] * total
        pending = []
        done = 0
        partial = 0

        self.last_cache_hits = 0

        for index, query in enumerate(queries):

            cached, plan = self._cached_tile(tiles[index], config, query)

            if cached is not None:
                results[index] = cached
                self.last_cache_hits += 1
                done += 1
            else:
                if plan is not None:
                    plans[index] = plan
                    fetch_queries[index] = plan["query"]
                    partial += 1
                pending.append(index)

        print(f"Kachel-Cache: {self.last_cache_hits} von {total} Kacheln aus dem Cache")

        if partial:
            print(
                f"Kachel-Cache: {partial} Kacheln nur teilweise im Cache, "
                "es werden nur die fehlenden Merkmale nachgeladen"
            )

        if self.on_progress is not None and done:
            self.on_progress(done, total)

        if pending:

            self._allowed = max(1, min(int(self.workers), len(pending)))
            self._active = 0

            executor = ThreadPoolExecutor(
                max_workers=self._allowed, thread_name_prefix="overpass-tile"
            )

            futures = {
                executor.submit(self._load_tile, index, fetch_queries[index]): index
                for index in pending
            }

            try:

                for future in as_completed(futures):

                    index = futures[future]
                    results[index] = self._complete_tile(
                        tiles[index], config, queries[index],
                        plans[index], future.result(),
                    )
                    done += 1

                    if self.on_progress is not None:
                        self.on_progress(done, total)

            except BaseException:
                # Fehler oder Abbruch: laufende Anfragen beenden. Fertige
                # Kacheln liegen schon im Cache, der naechste Lauf macht dort weiter.
                self._cancel.set()
                raise

            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        for data in results:

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

    # ---------------------------------------------------------
    # Parallele Kachel-Anfragen

    def _enter(self):
        """Wartet, bis eine Anfrage gleichzeitig laufen darf."""

        with self._gate:

            while self._active >= self._allowed:
                self._gate.wait(0.2)
                self._check_cancel()

            self._active += 1

    def _leave(self):

        with self._gate:
            self._active -= 1
            self._gate.notify_all()

    def _sleep(self, seconds):
        """Wartet, bricht bei Abbruch sofort ab."""

        end = time.monotonic() + seconds

        while True:

            self._check_cancel()

            left = end - time.monotonic()

            if left <= 0:
                return

            time.sleep(min(0.2, left))

    def _note_overload(self, response):
        """
        Bei HTTP 429/504: ab sofort nur noch eine Anfrage gleichzeitig und
        vor dem naechsten Versuch warten (Retry-After, sonst 10 s bzw. 5 s).
        """

        status = getattr(response, "status_code", None)

        # status None = Timeout/Verbindungsfehler: ebenfalls vorruebergehend.
        if status is not None and status not in TRANSIENT_STATUS:
            return

        with self._gate:
            self._allowed = 1
            self._gate.notify_all()

        wait = 10.0 if status == 429 else 5.0

        try:
            header = response.headers.get("Retry-After")
            if header:
                wait = float(header)
        except (AttributeError, TypeError, ValueError):
            pass

        wait = min(max(wait, 0.0), MAX_RETRY_AFTER_S)

        self._tls.wait = max(getattr(self._tls, "wait", 0.0), wait)

    def _load_tile(self, index, query):
        """Eine Kachel laden (mit Wiederholungen) und im Cache ablegen."""

        self._enter()

        try:

            data = None

            for attempt in range(TILE_RETRIES + 1):

                self._tls.wait = 0.0

                try:
                    data = self._fetch_json(query)
                    break
                except RuntimeError:

                    if attempt >= TILE_RETRIES:
                        raise

                    wait = max(
                        getattr(self._tls, "wait", 0.0),
                        BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)],
                    )

                    print(f"Kachel {index + 1}: neuer Versuch {attempt + 2} in {wait:.0f} s")

                    self._sleep(wait)

        finally:
            self._leave()

        self.tile_cache.put(query, data)

        return data

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