"""Fehlerbericht: Log und Systemangaben als ZIP, ohne Namen und Pfade.

Ohne Qt, einzeln testbar. Der Bericht enthaelt kein Projekt und keine
OSM-Daten, nur die Logdateien (anonymisiert) und eine kurze info.txt.
"""

from __future__ import annotations

import getpass
import platform
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

MAX_LOG_BYTES = 3 * 1024 * 1024

HOME_PLACEHOLDER = "%USERPROFILE%"
USER_PLACEHOLDER = "<user>"
ID_PLACEHOLDER = "<id>"
MAIL_PLACEHOLDER = "<email>"

_WIN_USER = re.compile(
    r"([A-Za-z]:[\\/]+Users[\\/]+)([^\\/\s'\"<>|:*?]+)", re.IGNORECASE
)
_STEAM_ID = re.compile(r"(userdata[\\/]+)\d+", re.IGNORECASE)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _home_variants(home) -> list[str]:
    raw = str(home).rstrip("\\/")

    # "/" oder "C:" nicht ersetzen
    if len(raw) < 4:
        return []

    forms = {
        raw,
        raw.replace("\\", "/"),
        raw.replace("/", "\\"),
        raw.replace("\\", "\\\\"),
    }

    return sorted(forms, key=len, reverse=True)


def anonymize(text: str, home=None, username=None) -> str:
    """Entfernt Benutzerordner, Benutzername, Steam-ID und E-Mail-Adressen."""

    if home is None:
        home = Path.home()

    if username is None:
        try:
            username = getpass.getuser()
        except Exception:
            username = ""

    for form in _home_variants(home):
        text = re.sub(
            re.escape(form),
            lambda match: HOME_PLACEHOLDER,
            text,
            flags=re.IGNORECASE,
        )

    text = _WIN_USER.sub(lambda m: m.group(1) + USER_PLACEHOLDER, text)
    text = _STEAM_ID.sub(lambda m: m.group(1) + ID_PLACEHOLDER, text)
    text = _EMAIL.sub(lambda m: MAIL_PLACEHOLDER, text)

    if username and len(username) >= 3:
        text = re.sub(
            r"\b" + re.escape(username) + r"\b",
            lambda match: USER_PLACEHOLDER,
            text,
        )

    return text


def collect_log_files(log_file) -> list[Path]:
    """Die aktuelle Logdatei und ihre rotierten Sicherungen (.1, .2, ...)."""

    base = Path(log_file)

    candidates = [base] + [
        base.with_name(base.name + "." + str(number)) for number in range(1, 6)
    ]

    return [path for path in candidates if path.is_file()]


def _read_log(path: Path) -> str:
    with open(path, "rb") as f:
        data = f.read()

    cut = False

    if len(data) > MAX_LOG_BYTES:
        data = data[-MAX_LOG_BYTES:]
        cut = True

    text = data.decode("utf-8", errors="replace")

    if cut:
        newline = text.find("\n")

        if newline != -1:
            text = text[newline + 1:]

        text = "[... older lines left out ...]\n" + text

    return text


def build_info(
    version,
    language,
    pyside_version="",
    extras=None,
    now=None,
) -> str:

    now = now or datetime.now()

    rows = [
        ("created", now.isoformat(timespec="seconds")),
        ("studio_version", version),
        ("language", language),
        ("frozen", bool(getattr(sys, "frozen", False))),
        ("python", sys.version.split()[0]),
        ("pyside6", pyside_version or "?"),
        ("system", platform.platform()),
        ("machine", platform.machine()),
    ]

    for key, value in (extras or {}).items():
        rows.append((str(key), value))

    body = "\n".join("%s: %s" % (key, value) for key, value in rows)

    return "TPF3 Map Studio bug report\n" + body + "\n"


def default_report_name(now=None) -> str:
    now = now or datetime.now()
    return "tpf3-map-studio-fehlerbericht-%s.zip" % now.strftime("%Y%m%d-%H%M%S")


def create_report(
    zip_path,
    log_file,
    version,
    language,
    pyside_version="",
    extras=None,
    now=None,
    home=None,
    username=None,
) -> list[str]:
    """Schreibt den Bericht und gibt die Namen der Dateien im ZIP zurueck."""

    zip_path = Path(zip_path)

    logs = collect_log_files(log_file)

    info = build_info(version, language, pyside_version, extras, now)

    if not logs:
        info += "logs: none found\n"

    names = ["info.txt"]

    try:

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:

            archive.writestr("info.txt", anonymize(info, home, username))

            for path in logs:
                name = "logs/" + path.name
                archive.writestr(name, anonymize(_read_log(path), home, username))
                names.append(name)

    except Exception:

        try:
            zip_path.unlink()
        except OSError:
            pass

        raise

    return names