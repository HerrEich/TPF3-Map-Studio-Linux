# TPF3 Map Studio v0.4.0

Sehr große Gebiete (80 × 80 km), eine Beschreibung zum Teilen deiner Karten und viele kleinere Verbesserungen. / Very large areas (80 × 80 km), a description for sharing your maps, and many smaller improvements.

## Deutsch

**Neu**
- **Große Gebiete stauchen (zum Beispiel 80 × 80 km):** Im Rechteck-Tool gibt es einen Stauchfaktor und einen Höhenfaktor. Ein sehr großes echtes Gebiet wird damit auf eine normale Spielkarte geschrumpft. Beim Höhenexport wird die reale Fläche berücksichtigt, Gleise, Straßen und Bahnhöfe werden mitskaliert. Im Spiel getestet mit dem Mittelrhein bei Koblenz, Faktor 2.
- **Sicherungen beim Stauchen:** Mit Stauchung ist nur Copernicus möglich, DGM1 und swissALTI3D sind gesperrt. Eine orange Dauerwarnung und eine Rückfrage schützen davor, es versehentlich auf einer normalen Karte zu benutzen. Der Overpass-Dialog weist bei gestauchten Karten darauf hin, dass Gebäude, Parks, Landnutzung und Vegetation abgeschaltet werden können.
- **Große OSM-Downloads in Kacheln:** Große Gebiete werden in Kacheln von etwa 20 km mit etwa 200 m Überlappung geladen. Die Anzeige zeigt „Kachel n von m“, Doppelte werden entfernt. Die Wartezeit für Overpass beträgt jetzt 200 Sekunden.
- **Abbrechen-Knopf** für OSM-Downloads. Er wirkt auch, wenn der Server hängt.
- **Bahnhofsplan zum Nachbauen** (vorher „Bahnhöfe aus OSM“): neuer Name und bessere Erklärung. Das Spiel kann keine Bahnhöfe importieren, die Liste (bahnhoefe.json und bahnhoefe.csv, Koordinaten in Metern ab Kartenmitte) dient als Plan zum Nachbauen echter Bahnhöfe.
- **Beschreibung zum Teilen** für veröffentlichte Karten, auf Deutsch oder Englisch (im Deutschen mit Dezimalkomma), als Markdown, Steam-BBCode oder Klartext: Kartengröße und -format, Höhenbereich, ob die Werte echte Höhen oder relativ zur Wasserhöhe sind, Höhenquelle mit Datenstand (swissALTI3D, und DGM1, wenn die Kacheldaten ihn enthalten), Stand der OSM-Daten, Biome, Quellenangaben mit Lizenz-Links und Änderungen an den Höhendaten. Der Hinweis auf `experimentalMapFeatures` erscheint nur bei den Größen, die ihn brauchen.
- **Copernicus-Vermerk korrigiert:** Der bisherige Wortlaut passte nicht zur Lizenz. F1-Anleitung, README und `THIRD_PARTY_NOTICES` (Deutsch und Englisch) sind angeglichen.
- **OSM-Datenstand:** wird beim Laden festgehalten (die älteste Kachel zählt) und in der Projektdatei gespeichert.
- **Städte:** Stadtteile (suburb, quarter, neighbourhood) im Städte-Dialog. Die Warenforderung ist wählbar (Beispiel, weglassen, leer oder neu: Zufallsmodus mit zwei Waren je Stadt und einem Seed-Feld für reproduzierbare Ergebnisse).
- **Biome:** Der Dialog scrollt. Die Baumgrenze hat einen weichen Übergang (Band in Metern, Standard 40 m) statt einer harten Linie. Exportierte Dateinamen werden ohne Umlaute und Sonderzeichen geschrieben.
- **JSON-Import** funktioniert wieder (Layer werden geleert, Fehler werden gemeldet), und im Dashboard gibt es den Knopf **Projekt-Datei öffnen…**.
- Der Cache-Ordner heißt jetzt `.tpf3_map_studio`. Der alte Ordner `.tpf2_map_studio` wird beim ersten Start automatisch umbenannt, die Caches bleiben erhalten.

**Installation:** `TPF3-Map-Studio-v0.4.0-win64.zip` herunterladen, die **ganze** ZIP entpacken, `TPF3-Map-Studio.exe` starten. Windows warnt beim ersten Start eventuell („Weitere Informationen“ -> „Trotzdem ausführen“), bei PyInstaller-Programmen sind Virenscanner-Fehlalarme bekannt.

**SHA-256:** `ad32f983d49598e76c6b996e2e72409968be376fc9edd10fdafb37cb730b8a14`

**Hinweis:** inoffizielles Werkzeug, keine Verbindung zu Urban Games.

## English

**What's new**
- **Compress large areas (for example 80 × 80 km):** the rectangle tool has a compression factor and a height factor. A very large real-world area is shrunk onto a normal game map. The height export takes the real area into account, and tracks, roads and stations are scaled along. Tested in the game with the Middle Rhine near Koblenz at factor 2.
- **Safeguards for compression:** with compression only Copernicus can be used, DGM1 and swissALTI3D are blocked. A persistent orange warning and a confirmation dialog protect against using it by accident on a normal map. For compressed maps the Overpass dialog points out that buildings, parks, land use and vegetation can be switched off.
- **Large OSM downloads in tiles:** big areas are loaded in tiles of about 20 km with about 200 m overlap. The status shows "tile n of m", duplicates are removed. The Overpass wait time is now 200 seconds.
- **Cancel button** for OSM downloads. It also works when the server hangs.
- **Station plan for rebuilding** (formerly "Stations from OSM"): new name and a clearer explanation. The game cannot import stations; the list (bahnhoefe.json and bahnhoefe.csv, coordinates in metres from the map centre) is a plan for rebuilding real stations by hand.
- **Description for sharing** for published maps, in German or English (with decimal comma in German), as Markdown, Steam BBCode or plain text: map size and format, elevation range, whether the values are real heights or relative to the water level, elevation source with data date (swissALTI3D, and DGM1 where the tile data contains it), date of the OSM data, biomes, attributions with licence links and changes to the elevation data. The `experimentalMapFeatures` hint appears only for the sizes that need it.
- **Corrected Copernicus notice:** the previous wording did not match the licence. The F1 guide, README and `THIRD_PARTY_NOTICES` (German and English) now agree.
- **OSM data date:** saved when loading (the oldest tile counts) and stored in the project file.
- **Towns:** district-level places (suburb, quarter, neighbourhood) in the towns dialog. The cargo demand is selectable (example, omit, empty, or new: random mode with two goods per town and a seed field for reproducible results).
- **Biomes:** the dialog scrolls. The tree line has a soft transition (band in metres, default 40 m) instead of a hard line. Exported file names are written without umlauts and special characters.
- **JSON import** works again (layers are cleared, errors are reported), and the dashboard has an **Open project file…** button.
- The cache folder is now called `.tpf3_map_studio`. The old `.tpf2_map_studio` folder is renamed automatically on the first start, so the caches are kept.

**Install:** download `TPF3-Map-Studio-v0.4.0-win64.zip`, extract the **whole** ZIP, run `TPF3-Map-Studio.exe`. Windows may warn on first start ("More info" -> "Run anyway"); antivirus false positives are known for PyInstaller programs.

**SHA-256:** `ad32f983d49598e76c6b996e2e72409968be376fc9edd10fdafb37cb730b8a14`

**Note:** unofficial tool, not affiliated with Urban Games.
