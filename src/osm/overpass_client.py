import threading

import requests

from src.http_identity import USER_AGENT
from src.map.objects.selection import Selection
from src.osm.osm_parser import OSMParser
from src.osm.objects.osm_data import OSMData
from src.osm.overpass_query_builder import OverpassQueryConfig, build_query
from src.i18n import tr


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

        self.timeout = 60
        self.parser = OSMParser()

        # Zuletzt erfolgreicher Server wird beim naechsten Download
        # zuerst gefragt - overpass-api.de ist oft ueberlastet und
        # bricht erst nach einigen Sekunden mit 504 ab, das muss nicht
        # bei jedem Download erneut abgewartet werden.
        self._preferred_server = None

        # Wird vom GUI-Thread gesetzt (cancel()), der Download-Thread
        # prueft ihn zwischen den Schritten.
        self._cancel = threading.Event()

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