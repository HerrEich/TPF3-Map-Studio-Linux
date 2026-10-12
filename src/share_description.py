"""
Beschreibungstext zum Teilen einer Karte (Klartext, Markdown, Steam-BBCode).

Reine Textfunktion ohne GUI. Der Dialog liefert die Werte, die nur dort
bekannt sind (Hoehenbereich, Wasserhoehe, Stauchung, Bearbeitungsschritte).
"""

from __future__ import annotations

from src.heightmap.heightmap_exporter import (
    SOURCE_COPERNICUS,
    SOURCE_DGM1_DE,
    SOURCE_DGM1_FOLDER,
    SOURCE_SWISSALTI3D,
    pixel_size_for_selection,
)
from src.heightmap.swissalti3d_dem import ATTRIBUTION as SWISS_ATTRIBUTION
from src.gui.map_size_presets import find_by_pixels
from src.i18n import get_language, translate_to

# Sprache des Textes ("de" oder "en"). None = Sprache des Programms. Wird nur
# waehrend build_share_description() gesetzt.
_lang = None


def _language() -> str:
    return _lang or get_language()


def tr(text):
    return translate_to(text, _language())


class _DeNum(float):
    # Dezimalkomma im deutschen Text, Formatangaben wie {:.1f} oder {:g} bleiben gueltig
    def __format__(self, spec):
        return float.__format__(self, spec).replace(".", ",")


def _n(value):
    return _DeNum(value) if _language() == "de" else float(value)

FORMATS = ("text", "markdown", "bbcode")

STUDIO_URL = "https://github.com/sharpi13822/TPF3-Map-Studio"

# Lizenz-Links je Quelle (am 12.10.2026 gegen die offiziellen Texte geprueft;
# govdata.de selbst war nicht abrufbar, die Adresse steht im Lizenztext).
LICENSE_URLS: dict[str, str] = {
    "osm": "https://www.openstreetmap.org/copyright",
    "copernicus": (
        "https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/"
        "Data/DEM/resources/license/License-COPDEM-30.pdf"
    ),
    "dgm1": "http://www.govdata.de/dl-de/by-2-0",
    "cc_by_4": "https://creativecommons.org/licenses/by/4.0/",
    "swissalti3d": (
        "https://www.swisstopo.admin.ch/en/"
        "terms-of-use-free-geodata-and-geoservices"
    ),
}

FALLBACK_MIN_FRACTION = 0.0005

WIKI_MAPSIZES_URL = (
    "https://wiki.transportfever3.com/doku.php?id=gamemanual:mapsizes"
    "#enable_experimental_map_features"
)

# Groessenstufen, die laut TPF3-Wiki erst mit experimentalMapFeatures = true
# im Spiel verfuegbar sind (im Wiki mit * markiert: Tiny, Huge, Megalomaniac,
# Gigantomaniac).
EXPERIMENTAL_SIZE_KEYS = frozenset(
    {"winzig", "riesig", "grössenwahnsinnig", "gigantomanisch"}
)


def _size_key(size_name: str) -> str:
    return size_name.replace("ß", "ss").casefold()


def _is_experimental(size) -> bool:
    return _size_key(size.size_name) in EXPERIMENTAL_SIZE_KEYS


def _size_name(size_name: str) -> str:
    names = {
        "winzig": tr("Winzig"),
        "klein": tr("Klein"),
        "mittel": tr("Mittel"),
        "gross": tr("Gross"),
        "sehr gross": tr("Sehr gross"),
        "riesig": tr("Riesig"),
        "grössenwahnsinnig": tr("Grössenwahnsinnig"),
        "gigantomanisch": tr("Gigantomanisch"),
    }
    return names.get(_size_key(size_name), size_name)


def _size_label(size) -> str:
    return f"{_size_name(size.size_name)} {size.ratio}"


# Vermerk und Haftungssatz laut Copernicus-Lizenz (Art. 6 b und c), im
# englischen Wortlaut der Lizenz. Die Daten werden immer veraendert
# (zugeschnitten, neu abgetastet), deshalb gilt der Vermerk fuer veraenderte Daten.
COPERNICUS_NOTICE = (
    "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and "
    "© Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS "
    "by the European Union and ESA; all rights reserved"
)
COPERNICUS_DISCLAIMER = (
    "The organisations in charge of the Copernicus programme by law or by "
    "delegation do not incur any liability for any use of the Copernicus "
    "WorldDEM-30"
)


def _link(text: str, url: str | None, fmt: str) -> str:
    if not url:
        return text
    if fmt == "markdown":
        return f"[{text}]({url})"
    if fmt == "bbcode":
        return f"[url={url}]{text}[/url]"
    return f"{text} ({url})"


def collect_rows(
    selection,
    info,
    *,
    range_min_m: float,
    range_max_m: float,
    water_level_m: float,
    relative_values: bool = False,
    compress_percent: float = 100.0,
    edits=(),
    osm_used: bool = True,
    biomes: str | None = None,
) -> list[tuple[str, str, str | None]]:
    """Zeilen (Bezeichnung, Wert, Link oder None), unabhaengig vom Format."""

    source = info.source if info is not None else SOURCE_COPERNICUS
    fallback = info.fallback_fraction if info is not None else 0.0
    attributions = list(info.attributions) if info is not None else []

    rows: list[tuple[str, str, str | None]] = []

    w_px, h_px = pixel_size_for_selection(selection)

    rows.append((
        tr("Kartengröße"),
        tr("{w:.1f} x {h:.1f} km ({wp} x {hp} Pixel)").format(
            w=_n(selection.width_m / 1000.0),
            h=_n(selection.height_m / 1000.0),
            wp=w_px,
            hp=h_px,
        ),
        None,
    ))

    matches = find_by_pixels(w_px, h_px)

    if matches:
        rows.append((
            tr("Kartenformat im Spiel"),
            tr(" oder ").join(_size_label(m) for m in matches),
            None,
        ))

    if selection.is_scaled:
        rows.append((
            tr("Reales Gebiet"),
            tr(
                "{w:.1f} x {h:.1f} km (Stauchfaktor {f:g}, Höhenfaktor {hs:.3f})"
            ).format(
                w=_n(selection.real_width_m / 1000.0),
                h=_n(selection.real_height_m / 1000.0),
                f=_n(selection.scale_factor),
                hs=_n(selection.height_scale),
            ),
            None,
        ))

    offset = water_level_m if relative_values else 0.0

    rows.append((
        tr("Höhenbereich im Import"),
        tr("{low:.0f} bis {high:.0f} m, Wasserhöhe {water:.0f} m").format(
            low=range_min_m - offset,
            high=range_max_m - offset,
            water=water_level_m - offset,
        )
        + (" " + tr("(auf Wasserhöhe 0 bezogen)") if relative_values else ""),
        None,
    ))

    if compress_percent < 100.0:
        rows.append((
            tr("Höhen über Wasser gestaucht auf"),
            f"{compress_percent:.0f} %",
            None,
        ))

    if biomes:
        rows.append((tr("Biome"), biomes, None))

    # Hoehenquelle
    if source == SOURCE_SWISSALTI3D:
        source_name = tr("swissALTI3D Schweiz (2 m)")
    elif source in (SOURCE_DGM1_DE, SOURCE_DGM1_FOLDER):
        source_name = tr("DGM1 Deutschland (1 m)")
    else:
        source_name = "Copernicus DEM GLO-30 (30 m)"

    if source != SOURCE_COPERNICUS and fallback > FALLBACK_MIN_FRACTION:
        source_name += ", " + tr(
            "{percent:.1f} % der Fläche aus Copernicus ergänzt"
        ).format(percent=_n(fallback * 100.0))

    rows.append((tr("Höhenquelle"), source_name, None))

    actualities = list(getattr(info, "actualities", None) or [])

    if actualities and source != SOURCE_COPERNICUS:
        stand = (
            actualities[0]
            if len(actualities) == 1
            else f"{actualities[0]} – {actualities[-1]}"
        )
        rows.append((tr("Datenstand der Höhendaten"), stand, None))

    # Quellenangaben und Lizenzen
    uses_copernicus = source == SOURCE_COPERNICUS or fallback > FALLBACK_MIN_FRACTION

    if source == SOURCE_SWISSALTI3D:
        rows.append((tr("Quellenangabe"), SWISS_ATTRIBUTION, None))
        rows.append((
            tr("Lizenz"),
            tr("OGD swisstopo (Quellenangabe ist Pflicht)"),
            LICENSE_URLS.get("swissalti3d"),
        ))
    elif source in (SOURCE_DGM1_DE, SOURCE_DGM1_FOLDER):
        text = (
            " | ".join(attributions)
            if attributions
            else tr("DGM1 der Landesvermessung (Quellenvermerk des Landes beachten)")
        )
        rows.append((tr("Quellenangabe"), text + " – " + tr("Daten verändert"), None))
        rows.append((
            tr("Lizenz (je nach Bundesland)"),
            tr("Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0)"),
            LICENSE_URLS.get("dgm1"),
        ))
        rows.append((
            tr("Lizenz (je nach Bundesland)"),
            tr("Creative Commons Namensnennung 4.0 International (CC BY 4.0)"),
            LICENSE_URLS.get("cc_by_4"),
        ))

    if uses_copernicus:
        rows.append((tr("Quellenangabe"), COPERNICUS_NOTICE, LICENSE_URLS.get("copernicus")))
        rows.append((tr("Haftungsausschluss"), COPERNICUS_DISCLAIMER, None))

    if osm_used:
        rows.append((
            tr("Karten- und Gewässerdaten"),
            tr("© OpenStreetMap-Mitwirkende (ODbL)"),
            LICENSE_URLS.get("osm"),
        ))

    base = tr("zugeschnitten und auf 4 m je Pixel neu abgetastet")
    rows.append((
        tr("Änderungen an den Höhendaten"),
        "; ".join([base, *[e for e in edits if e]]),
        None,
    ))

    if matches and all(_is_experimental(m) for m in matches):
        rows.append((
            tr("Hinweis"),
            tr(
                "Die Größenstufe {size} ist im Spiel nur mit "
                "experimentalMapFeatures = true in der settings.lua "
                "verfügbar. Für experimentelle Größen sind laut TPF3-Wiki "
                "mindestens 16 GB RAM nötig."
            ).format(size=_size_name(matches[0].size_name)),
            None,
        ))
        rows.append((tr("TPF3-Wiki"), WIKI_MAPSIZES_URL, WIKI_MAPSIZES_URL))

    rows.append((tr("Erzeugt mit"), "TPF3 Map Studio", STUDIO_URL))

    return rows


def edit_notes(
    *,
    smooth_sigma=None,
    flatten_sigma=None,
    slope=None,
    enforce=None,
    blend_transition=None,
    clip_mode=None,
) -> list[str]:
    # Beschreibt die eingeschalteten Bearbeitungsschritte (None = aus).
    # slope = (Staerke %, Glaettung m), enforce = (Ufer m, Mitte m, Boeschung m)
    notes = []

    if smooth_sigma is not None:
        notes.append(
            tr("Gelände geglättet ({sigma:.0f} m)").format(sigma=smooth_sigma)
        )

    if flatten_sigma is not None:
        notes.append(
            tr("Trassen und Siedlungen eingeebnet ({sigma:.0f} m)").format(
                sigma=flatten_sigma
            )
        )

    if slope is not None:
        strength, smoothing = slope
        notes.append(
            tr(
                "Gefälle ausgeglichen (Stärke {strength:.0f} %, Glättung "
                "{smoothing:.0f} m), die absoluten Höhen ü. NN stimmen nicht mehr"
            ).format(strength=strength, smoothing=smoothing)
        )

    if enforce is not None:
        edge, depth, transition = enforce
        notes.append(
            tr(
                "Wasser nur dort, wo OpenStreetMap Wasser hat (Flussbett "
                "{edge:g} bis {depth:g} m tief, Böschung {transition:.0f} m)"
            ).format(edge=_n(edge), depth=_n(depth), transition=transition)
        )

    if blend_transition is not None:
        notes.append(
            tr(
                "Terrain um Gewässer sanft ans Wasserniveau angepasst "
                "(Übergang {transition:.0f} m)"
            ).format(transition=blend_transition)
        )

    if clip_mode:
        notes.append(tr("Höhenfenster begrenzt ({mode})").format(mode=clip_mode))

    return notes


def render_rows(rows, fmt: str = "markdown") -> str:
    if fmt not in FORMATS:
        raise ValueError(f"Unbekanntes Format: {fmt}")

    title = tr("Karteninformationen")
    lines = []

    if fmt == "markdown":
        lines.append(f"## {title}")
        lines.append("")
    elif fmt == "bbcode":
        lines.append(f"[h2]{title}[/h2]")
        lines.append("[list]")
    else:
        lines.append(title)

    for label, value, url in rows:
        shown = _link(value, url, fmt)
        if fmt == "markdown":
            lines.append(f"- **{label}:** {shown}")
        elif fmt == "bbcode":
            lines.append(f"[*][b]{label}:[/b] {shown}")
        else:
            lines.append(f"- {label}: {shown}")

    if fmt == "bbcode":
        lines.append("[/list]")

    return "\n".join(lines) + "\n"


def build_share_description(
    selection, info, *, fmt: str = "markdown", language: str | None = None, **kwargs
) -> str:
    # language: "de" oder "en", None = Sprache des Programms.
    # edit_params: Einstellungen fuer edit_notes(), die erst hier in die
    # gewaehlte Sprache uebersetzt werden.
    global _lang

    previous = _lang
    _lang = language

    try:
        edit_params = kwargs.pop("edit_params", None)

        if edit_params:
            kwargs["edits"] = [
                *(kwargs.get("edits") or ()),
                *edit_notes(**edit_params),
            ]

        return render_rows(collect_rows(selection, info, **kwargs), fmt)
    finally:
        _lang = previous
