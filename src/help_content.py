"""Inhalt der Hilfe (Inhaltsverzeichnis + Markdown-Kapitel). Kein Qt noetig."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

HELP_DIR = Path(__file__).resolve().parent / "help"
DEFAULT_LANGUAGE = "de"

_LINK = re.compile(r"\]\(help:([a-z0-9-]+)\)")


@dataclass
class HelpPage:
    id: str
    title: str
    file: str
    children: list["HelpPage"] = field(default_factory=list)


def _language_dir(language: str, base: Path) -> Path:
    folder = base / language
    return folder if (folder / "index.json").is_file() else base / DEFAULT_LANGUAGE


def _parse(entry: dict) -> HelpPage:
    return HelpPage(
        id=entry["id"],
        title=entry["title"],
        file=entry["file"],
        children=[_parse(child) for child in entry.get("children", [])],
    )


def load_index(language: str = DEFAULT_LANGUAGE, base: Path | None = None) -> list[HelpPage]:
    folder = _language_dir(language, base or HELP_DIR)
    data = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    return [_parse(entry) for entry in data["pages"]]


def flatten(pages: list[HelpPage]) -> list[HelpPage]:
    result: list[HelpPage] = []
    for page in pages:
        result.append(page)
        result.extend(flatten(page.children))
    return result


def find_page(pages: list[HelpPage], page_id: str) -> HelpPage | None:
    for page in flatten(pages):
        if page.id == page_id:
            return page
    return None


def read_page(page: HelpPage, language: str = DEFAULT_LANGUAGE, base: Path | None = None) -> str:
    folder = _language_dir(language, base or HELP_DIR)
    return (folder / page.file).read_text(encoding="utf-8")


def linked_ids(text: str) -> list[str]:
    return _LINK.findall(text)


def search(pages: list[HelpPage], query: str, language: str = DEFAULT_LANGUAGE,
           base: Path | None = None) -> list[HelpPage]:
    """Kapitel, deren Titel oder Text alle Suchwoerter enthalten (ohne Gross/Klein)."""
    words = [w for w in query.lower().split() if w]
    if not words:
        return flatten(pages)
    hits = []
    for page in flatten(pages):
        haystack = (page.title + "\n" + read_page(page, language, base)).lower()
        if all(word in haystack for word in words):
            hits.append(page)
    return hits
