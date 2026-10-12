# TPF3 Map Studio v0.4.0

Sehr große Gebiete (80 × 80 km), eine Beschreibung zum Teilen deiner Karten und viele kleinere Verbesserungen. / Very large areas (80 × 80 km), a description for sharing your maps, and many smaller improvements.

## Deutsch

**Neu**
- **Große Gebiete stauchen (zum Beispiel 80 × 80 km):** Ein sehr großes echtes Gebiet lässt sich mit einem Faktor auf eine normale Spielkarte schrumpfen. Die Höhen werden mitskaliert. Das gilt für Heightmap, Städte, Bahnhöfe und Netze. Im Spiel getestet mit dem Mittelrhein bei Koblenz, Faktor 2.
- **Sicherungen beim Stauchen:** Mit Stauchung ist nur Copernicus möglich, DGM1 und swissALTI3D sind gesperrt. Ab Faktor 2 warnen eine orange Anzeige und eine Rückfrage davor, es versehentlich auf einer normalen Karte zu benutzen.
- **Große OSM-Downloads in Kacheln:** Große Gebiete werden in Kacheln von etwa 20 km mit etwa 200 m Überlappung geladen. Die Anzeige zeigt „Kachel n von m“, Doppelte werden entfernt.
- **Overpass-Dialog:** warnt bei großen Gebieten und hat einen Knopf, der Gebäude, Parks, Landnutzung und Vegetation abschaltet.
- **Abbrechen-Knopf** für OSM-Downloads. Er wirkt auch, wenn der Server hängt.
- **Beschreibung zum Teilen** für veröffentlichte Karten, auf Deutsch oder Englisch (im Deutschen mit Dezimalkomma), als Markdown, Steam-BBCode oder Klartext: Kartengröße und -format, Höhenbereich, ob die Werte echte Höhen oder relativ zur Wasserhöhe sind, Höhenquelle mit Datenstand (swissALTI3D, und DGM1, wenn die Kacheldaten ihn enthalten), Stand der OSM-Daten, Biome, Quellenangaben mit Lizenz-Links und Änderungen an den Höhendaten. Der Hinweis auf `experimentalMapFeatures` erscheint nur bei den Größen, die ihn brauchen.
- **Copernicus-Vermerk korrigiert:** Der bisherige Wortlaut passte nicht zur Lizenz. F1-Anleitung, README und `THIRD_PARTY_NOTICES` (Deutsch und Englisch) sind angeglichen.
- **OSM-Datenstand:** wird beim Laden festgehalten (die älteste Kachel zählt) und in der Projektdatei gespeichert.
- **Städte:** Stadtteile (suburb, quarter, neighbourhood) im Export. Die Warenforderung ist wählbar (Beispiel, weglassen, leer), mit Zufallsmodus und Seed-Feld.
- **Biome:** Der Dialog scrollt, die Baumgrenze hat einen weichen Übergang statt einer harten Linie, und exportierte Dateinamen werden ohne Umlaute und Sonderzeichen geschrieben.
- **JSON-Import** funktioniert wieder, und im Dashboard gibt es den Knopf **Projekt-Datei öffnen…**.
- Der Cache-Ordner heißt jetzt `.tpf3_map_studio`. Der alte `.tpf2_map_studio` wird beim ersten Start automatisch umbenannt.

**Installation:** `TPF3-Map-Studio-v0.4.0-win64.zip` herunterladen, die **ganze** ZIP entpacken, `TPF3-Map-Studio.exe` starten. Windows warnt beim ersten Start eventuell („Weitere Informationen“ -> „Trotzdem ausführen“), bei PyInstaller-Programmen sind Virenscanner-Fehlalarme bekannt.

**SHA-256:** `…`

**Hinweis:** inoffizielles Werkzeug, keine Verbindung zu Urban Games.

## English

**What's new**
- **Compress large areas (for example 80 × 80 km):** shrink a very large real-world area onto a normal game map with a scale factor. Heights are scaled along with it. It applies to the heightmap, towns, stations and networks. Tested in the game with the Middle Rhine near Koblenz at factor 2.
- **Safeguards for compression:** with compression only Copernicus can be used, DGM1 and swissALTI3D are blocked. From factor 2 on, an orange warning and a confirmation dialog help against using it by accident on a normal map.
- **Large OSM downloads in tiles:** big areas are loaded in tiles of about 20 km with about 200 m overlap. The status shows "tile n of m", duplicates are removed.
- **Overpass dialog:** warns for large areas and has a button that switches off buildings, parks, land use and vegetation.
- **Cancel button** for OSM downloads. It also works when the server hangs.
- **Description for sharing** for published maps, in German or English (with decimal comma in German), as Markdown, Steam BBCode or plain text: map size and format, elevation range, whether the values are real heights or relative to the water level, elevation source with data date (swissALTI3D, and DGM1 where the tile data contains it), date of the OSM data, biomes, attributions with licence links and changes to the elevation data. The `experimentalMapFeatures` hint appears only for the sizes that need it.
- **Corrected Copernicus notice:** the previous wording did not match the licence. The F1 guide, README and `THIRD_PARTY_NOTICES` (German and English) now agree.
- **OSM data date:** saved when loading (the oldest tile counts) and stored in the project file.
- **Towns:** district-level places (suburb, quarter, neighbourhood) in the export. The cargo demand is selectable (example, omit, empty), with a random mode and a seed field.
- **Biomes:** the dialog scrolls, the tree line has a soft transition instead of a hard line, and exported file names are written without umlauts and special characters.
- **JSON import** works again, and the dashboard has an **Open project file…** button.
- The cache folder is now called `.tpf3_map_studio`. The old `.tpf2_map_studio` is renamed automatically on the first start.

**Install:** download `TPF3-Map-Studio-v0.4.0-win64.zip`, extract the **whole** ZIP, run `TPF3-Map-Studio.exe`. Windows may warn on first start ("More info" -> "Run anyway"); antivirus false positives are known for PyInstaller programs.

**SHA-256:** `…`

**Note:** unofficial tool, not affiliated with Urban Games.
