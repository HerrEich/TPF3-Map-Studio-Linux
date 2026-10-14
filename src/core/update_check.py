"""Update-Hinweis: fragt GitHub nach dem neuesten Release (ohne Qt, einzeln testbar)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from src.i18n import tr

REPO = "sharpi13822/TPF3-Map-Studio"
API_URL = "https://api.github.com/repos/%s/releases/latest" % REPO
RELEASES_URL = "https://github.com/%s/releases/latest" % REPO
ALLOWED_URL_PREFIX = "https://github.com/%s/" % REPO

MAX_RESPONSE_BYTES = 1_000_000
DEFAULT_TIMEOUT_S = 8.0

_VERSION = re.compile(r"^[vV]?(\d{1,4})\.(\d{1,4})(?:\.(\d{1,4}))?$")


class UpdateCheckError(Exception):
    """Pruefung fehlgeschlagen; der Text ist fuer Nutzer gedacht."""


@dataclass
class UpdateInfo:
    version: str
    tag: str
    url: str
    name: str


def default_settings_path() -> Path:
    # Erst hier importiert: app_paths kann beim Import den Ordner umbenennen.
    from src.app_paths import APP_DIR

    return APP_DIR / "update_check.json"


# ------------------------------------------------------------- Versionen

def parse_version(text):
    if not isinstance(text, str):
        return None

    match = _VERSION.match(text.strip())

    if not match:
        return None

    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def is_newer(latest, current) -> bool:
    a = parse_version(latest)
    b = parse_version(current)
    return a is not None and b is not None and a > b


def decide_action(current, latest, skipped, manual) -> str:
    """'update' = Dialog zeigen, 'current' = nichts Neues, 'skipped' = uebersprungen."""

    if not is_newer(latest, current):
        return "current"

    if not manual and parse_version(skipped) == parse_version(latest):
        return "skipped"

    return "update"


# --------------------------------------------------------------- Abfrage

def _http_message(code) -> str:
    if code == 404:
        return tr("Es wurde noch keine Version ver\u00f6ffentlicht.")

    if code in (403, 429):
        return tr(
            "GitHub hat die Anfrage abgelehnt (Rate-Limit). "
            "Bitte sp\u00e4ter erneut versuchen."
        )

    return tr("GitHub hat mit Fehler {code} geantwortet.").format(code=code)


def _unexpected() -> UpdateCheckError:
    return UpdateCheckError(tr("Unerwartete Antwort von GitHub."))


def fetch_latest(user_agent, urlopen=None, timeout=DEFAULT_TIMEOUT_S) -> UpdateInfo:
    opener = urlopen or urllib.request.urlopen

    request = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/vnd.github+json",
        },
    )

    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)

    except urllib.error.HTTPError as exc:
        raise UpdateCheckError(_http_message(exc.code))

    except OSError as exc:
        raise UpdateCheckError(
            tr("GitHub ist nicht erreichbar ({error}).").format(error=exc)
        )

    if len(raw) > MAX_RESPONSE_BYTES:
        raise _unexpected()

    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise _unexpected()

    if not isinstance(data, dict) or not isinstance(data.get("tag_name"), str):
        raise _unexpected()

    tag = data["tag_name"].strip()
    parsed = parse_version(tag)

    if parsed is None:
        raise UpdateCheckError(
            tr("Die Versionsnummer der neuesten Version ist nicht lesbar: {tag}")
            .format(tag=tag[:40])
        )

    url = data.get("html_url")

    if not isinstance(url, str) or not url.startswith(ALLOWED_URL_PREFIX):
        url = RELEASES_URL

    name = data.get("name")
    name = " ".join(name.split())[:80] if isinstance(name, str) else ""

    return UpdateInfo(
        version="%d.%d.%d" % parsed,
        tag=tag,
        url=url,
        name=name,
    )


# ---------------------------------------------------------- Einstellungen

def default_settings() -> dict:
    # Die automatische Pruefung beim Start ist standardmaessig AUS.
    return {"auto_check": False, "skipped_version": ""}


def sanitize_settings(raw) -> dict:
    result = default_settings()

    if not isinstance(raw, dict):
        return result

    if isinstance(raw.get("auto_check"), bool):
        result["auto_check"] = raw["auto_check"]

    parsed = parse_version(raw.get("skipped_version"))

    if parsed is not None:
        result["skipped_version"] = "%d.%d.%d" % parsed

    return result


def load_settings(path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sanitize_settings(json.load(f))
    except (OSError, ValueError):
        return default_settings()


def save_settings(path, settings):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_name(path.name + ".tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sanitize_settings(settings), f, indent=2)
        f.write("\n")

    os.replace(tmp, path)