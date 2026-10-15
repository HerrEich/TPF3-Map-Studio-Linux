# TPF3 Map Studio v0.5.0

Zuverlässigere OSM-Downloads für große Gebiete, Höhendaten aus den Niederlanden und neue Hilfen für Kartenrezepte und Fehlersuche. / More reliable OSM downloads for large areas, elevation data from the Netherlands, and new helpers for map recipes and troubleshooting.

## Deutsch

**Neu**
- **Zuverlässigere OSM-Downloads:** Die Kacheln sind jetzt etwa 11 km groß statt 20 km. Kleinere Anfragen laufen bei großen oder dichten Gebieten seltener in eine Zeitüberschreitung. Fehlgeschlagene Kacheln werden bis zu viermal wiederholt (Wartezeiten 10, 30, 60 und 90 Sekunden). Meldungen des Servers wie „runtime error“ oder „timed out“ werden erkannt, die Fehlermeldung ist genauer, und das Log zeigt den HTTP-Statuscode.
- **OSM-Kachel-Cache auf der Festplatte** und paralleler Kachel-Download. Wegen der neuen Kachelgröße werden bereits gespeicherte OSM-Kacheln beim ersten Mal neu geladen.
- **Höhenquelle AHN Niederlande** (PDOK, 2 m) mit Abruf, Cache, Dialog, Freigabetext, Anleitung und Lizenzhinweisen.
- **Overpass-Baukasten:** neue Kategorie **Natur-Details** (Hecken, Mauern), standardmäßig ausgeschaltet.
- **Biome-Maske:** eigene Kategorie Weinberg. Weinberg und Obstbau werden auch als Relation geladen.
- **Kartenrezept** exportieren und importieren. Das Projektformat 3 speichert und lädt die Export-Einstellungen.
- **Copernicus-Download** mit Fortschrittsanzeige und Abbrechen-Knopf.
- **Cache-Verwaltung** im Hilfe-Menü: Größe anzeigen und Höhendaten-Caches leeren. Der Cache-Dialog erklärt die OSM-Kacheln.
- **Fehlerbericht erstellen** und Log-Ordner öffnen (Hilfe-Menü).
- **Update-Hinweis:** manuelle Prüfung und optional eine Prüfung beim Start.
- Externe Links in der Karte (Leaflet, OSM) öffnen im Standardbrowser. Lange JS-Aufrufe werden im Log gekürzt.

**Installation:** `TPF3-Map-Studio-v0.5.0-win64.zip` herunterladen, die **ganze** ZIP entpacken, `TPF3-Map-Studio.exe` starten. Windows warnt beim ersten Start eventuell („Weitere Informationen“ -> „Trotzdem ausführen“), bei PyInstaller-Programmen sind Virenscanner-Fehlalarme bekannt.

**SHA-256:** `3b6fa3fd7138ca6ce492c8c73e2960ad62a54d2b3b38be3eacdeb295912c8b7b`

**Hinweis:** inoffizielles Werkzeug, keine Verbindung zu Urban Games.

## English

**What's new**
- **More reliable OSM downloads:** tiles are now about 11 km instead of 20 km. Smaller requests time out less often for large or dense areas. Failed tiles are retried up to four times (waits of 10, 30, 60 and 90 seconds). Server messages such as "runtime error" or "timed out" are recognised, the error message is more precise, and the log shows the HTTP status code.
- **OSM tile cache on disk** and parallel tile download. Because of the new tile size, OSM tiles saved earlier are downloaded again once.
- **Elevation source AHN Netherlands** (PDOK, 2 m) with download, cache, dialog, release text, guide and licence notices.
- **Overpass builder:** new category **Natural details** (hedges, walls), off by default.
- **Biome mask:** separate vineyard category. Vineyards and orchards are also loaded as relations.
- **Map recipe** export and import. Project format 3 saves and loads the export settings.
- **Copernicus download** with progress display and a cancel button.
- **Cache management** in the Help menu: show size and clear elevation caches. The cache dialog explains the OSM tiles.
- **Create error report** and open the log folder (Help menu).
- **Update notice:** manual check and an optional check at start-up.
- External links in the map (Leaflet, OSM) open in the default browser. Long JS calls are shortened in the log.

**Install:** download `TPF3-Map-Studio-v0.5.0-win64.zip`, extract the **whole** ZIP, run `TPF3-Map-Studio.exe`. Windows may warn on first start ("More info" -> "Run anyway"); antivirus false positives are known for PyInstaller programs.

**SHA-256:** `3b6fa3fd7138ca6ce492c8c73e2960ad62a54d2b3b38be3eacdeb295912c8b7b`

**Note:** unofficial tool, not affiliated with Urban Games.
