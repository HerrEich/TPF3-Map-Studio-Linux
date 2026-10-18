# TPF3 Map Studio v0.6.0

Neue Höhenquelle Österreich (BEV, 1 m), TPF2-Karten nach TPF3 übernehmen, ein Hilfe-Fenster mit Anleitungen, Zoom in der Heightmap-Vorschau und Korrekturen bei OSM-Download und Speicherverbrauch. / New height source Austria (BEV, 1 m), carry TPF2 maps over to TPF3, a help window with guides, zoom in the heightmap preview, and fixes for the OSM download and memory use.

## Deutsch

**Neu**
- **Höhenquelle „BEV Österreich“ (1 m):** Das Studio holt aus den großen BEV-Dateien nur die Teile, die dein Rechteck braucht (rund 100 MB für 10 × 54 km statt mehrerer GB). Mit Quellenangabe (CC BY 4.0). Bei Graz im Studio und im Spiel mit „Größenwahnsinnig 1:5“ getestet. Danke für die Anregung!
- **TPF2-Karten nach TPF3 übernehmen:** Menü *Werkzeuge → TPF2-Karte übernehmen…* macht aus der Heightmap-PNG einer TPF2-Karte eine TPF3-Heightmap mit sauberen Ufern und auf Wunsch eine Biome-Maske (Weg A, fiktive Karten). Für Karten nach echten Daten gibt es die Höhenquelle „Eigene TPF2-Heightmap (PNG)“ mit OSM-Gewässern (Weg B).
- **Hilfe → Anleitungen…:** Inhaltsverzeichnis mit Suche und Kapiteln zu Karte und Rechteck, OSM, Heightmap, Höhenquellen, Österreich, Export und Import im Spiel, Biome/Städte/Industrien, TPF2 nach TPF3, häufige Fragen, Quellen und Lizenzen. (Vorerst nur auf Deutsch.)
- **Zoom in der Heightmap-Vorschau:** Mausrad zoomt, Ziehen verschiebt, Doppelklick zeigt wieder die ganze Karte.

**Verbessert**
- **OSM-Download:** Bei überlasteten Servern wechselt das Studio den Server und legt Pausen ein.
- **Copernicus:** Die Kacheln werden sparsam geladen. Bei großen Karten mit großem Stauchfaktor gibt es keinen Speicherfehler mehr („Unable to allocate … MiB“). Danke an Bohneneintopf für die Meldung!

**Installation:** `TPF3-Map-Studio-v0.6.0-win64.zip` herunterladen, die **ganze** ZIP entpacken, `TPF3-Map-Studio.exe` starten. Windows warnt beim ersten Start eventuell („Weitere Informationen“ -> „Trotzdem ausführen“), bei PyInstaller-Programmen sind Virenscanner-Fehlalarme bekannt.

**SHA-256:** `b03df38af4f1861bba60a0b35dc7937cf883e5db592ad33bbf9a229ad540bc17`

**Hinweis:** inoffizielles Werkzeug, keine Verbindung zu Urban Games.

## English

**What's new**
- **Height source "BEV Austria" (1 m):** the Studio fetches only the parts of the large BEV files that your rectangle needs (about 100 MB for 10 × 54 km instead of several GB). With source attribution (CC BY 4.0). Tested near Graz in the Studio and in the game with "Größenwahnsinnig 1:5". Thanks for the suggestion!
- **Carry TPF2 maps over to TPF3:** menu *Tools → Import TPF2 map…* turns the heightmap PNG of a TPF2 map into a TPF3 heightmap with clean shores and, if you like, a biome mask (way A, fictional maps). For maps based on real data there is the height source "Own TPF2 heightmap (PNG)" with OSM water (way B).
- **Help → Guides…:** table of contents with search and chapters on map and rectangle, OSM, heightmap, height sources, Austria, export and import in the game, biomes/towns/industries, TPF2 to TPF3, frequent questions, sources and licences. (German only for now.)
- **Zoom in the heightmap preview:** mouse wheel zooms, dragging pans, double-click shows the whole map again.

**Improved**
- **OSM download:** when servers are overloaded, the Studio switches server and pauses.
- **Copernicus:** tiles are loaded sparingly. Large maps with a large compression factor no longer fail with a memory error ("Unable to allocate … MiB"). Thanks to Bohneneintopf for reporting!

**Install:** download `TPF3-Map-Studio-v0.6.0-win64.zip`, extract the **whole** ZIP, run `TPF3-Map-Studio.exe`. Windows may warn on first start ("More info" -> "Run anyway"); antivirus false positives are known for PyInstaller programs.

**SHA-256:** `b03df38af4f1861bba60a0b35dc7937cf883e5db592ad33bbf9a229ad540bc17`

**Note:** unofficial tool, not affiliated with Urban Games.
