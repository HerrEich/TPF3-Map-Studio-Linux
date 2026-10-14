"""Welche Adressen darf das Kartenfenster selbst anzeigen?

Die Karte laeuft in einem eingebetteten Browser (QtWebEngine) ohne Zurueck-Taste.
Klickt jemand auf einen Link der Karte (Leaflet, OpenStreetMap-Copyright), darf die
fremde Seite nicht die Karte ersetzen: Solche Links gehoeren in den Standardbrowser.
Die Entscheidung ist reine Textarbeit und deshalb ohne Qt testbar.
"""

from urllib.parse import urlsplit

# Rechner, von denen die Karte ihre eigenen Seiten laedt (LocalServer).
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# Schemata ohne Netzwerkseite (leere Seite, Daten, interne Fehlerseite).
INTERNAL_SCHEMES = frozenset(
    {"about", "data", "blob", "qrc", "devtools", "chrome-error", "chrome-devtools"}
)

# Nur diese Schemata werden bei einem Klick im Standardbrowser geoeffnet.
BROWSER_SCHEMES = frozenset({"http", "https", "mailto"})


def _scheme_and_host(url):
    try:
        parts = urlsplit(str(url).strip())
        return parts.scheme.lower(), (parts.hostname or "").lower()
    except ValueError:
        return "", ""


def is_internal_url(url) -> bool:
    """True, wenn das Kartenfenster die Adresse selbst laden darf."""

    scheme, host = _scheme_and_host(url)

    if scheme in INTERNAL_SCHEMES:
        return True

    if scheme in ("http", "https"):
        return host in LOCAL_HOSTS

    return False


def opens_in_browser(url) -> bool:
    """True, wenn ein Klick auf diese (externe) Adresse den Standardbrowser oeffnen soll."""

    scheme, _host = _scheme_and_host(url)

    return scheme in BROWSER_SCHEMES and not is_internal_url(url)
