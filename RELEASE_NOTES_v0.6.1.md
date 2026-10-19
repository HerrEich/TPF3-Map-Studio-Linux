# TPF3 Map Studio v0.6.1

Große Karten (z. B. „Gigantomanie“ 1:3) werden deutlich schneller berechnet, die Oberfläche friert dabei nicht mehr ein, und lange Berechnungen zeigen Fortschritt, Restzeit und einen Abbrechen-Knopf. / Large maps (e.g. "Gigantomanie" 1:3) are calculated much faster, the window no longer freezes, and long calculations show progress, remaining time and a Cancel button.

## Deutsch

Verbessert
- Große Karten rechnen im Hintergrund: Höhenraster berechnen, Gelände glätten und die weiteren Gelände-Schritte laufen bei großen Karten in einem Fortschrittsfenster mit Balken, Restzeit und Abbrechen. Das Fenster bleibt bedienbar, Windows meldet kein „Keine Rückmeldung“ mehr. Das gilt ab etwa 4 Millionen Pixeln, kleine Karten rechnen wie bisher ohne Fenster.
- Mehrere Prozessorkerne: Einlesen der Höhendaten und Glätten nutzen mehrere Kerne. Das gilt für Copernicus, TPF2-Heightmap (PNG), DGM1, swissALTI3D, AHN, BEV Österreich, die Ordner-Quelle und die Ergänzung durch Copernicus. Parallel und einzeln gerechnet kommen exakt dieselben Werte heraus.
- Jede Höhenkachel wird pro Streifen nur noch einmal geladen (früher bis zu neunmal). Das war der Hauptgrund, warum große Karten sehr lange brauchten.
- Wasserhöhen-Vorschlag und PNG-Export: Der Vorschlag rechnet bei riesigen Rastern aus einer Stichprobe, das Schreiben großer PNG-Dateien blockiert das Fenster nicht mehr.
- OSM-Download: Die Overpass-Server `overpass-api.de` und `lz4.overpass-api.de` lehnten die Anfragen des Studios ab (HTTP 406), der Download musste auf langsamere Server ausweichen. Behoben. Bei Fehlern steht außerdem der Anfang der Server-Antwort im Log.

Installation: `TPF3-Map-Studio-v0.6.1-win64.zip` herunterladen, die ganze ZIP entpacken, `TPF3-Map-Studio.exe` starten. Windows warnt beim ersten Start eventuell („Weitere Informationen“ -> „Trotzdem ausführen“), bei PyInstaller-Programmen sind Virenscanner-Fehlalarme bekannt.

SHA-256: `56dc9486d6ce5cae224b1868f9c29b4d05632f5f6c9b4cedd69bc3063d4b5a8b`

Hinweis: inoffizielles Werkzeug, keine Verbindung zu Urban Games.

## English

Improved
- Large maps calculate in the background: calculating the height grid, smoothing the terrain and the other terrain steps now run in a progress window with a bar, remaining time and Cancel on large maps. The window stays usable, and Windows no longer reports "Not responding". This applies from about 4 million pixels; small maps calculate as before without a window.
- Multiple processor cores: reading the height data and smoothing use several cores. This applies to Copernicus, TPF2 heightmap (PNG), DGM1, swissALTI3D, AHN, BEV Austria, the folder source and the Copernicus gap filling. Calculated in parallel or one at a time, the values are exactly the same.
- Each height tile is loaded only once per strip (previously up to nine times). This was the main reason why large maps took so long.
- Water level suggestion and PNG export: on huge grids the suggestion is calculated from a sample, and writing large PNG files no longer blocks the window.
- OSM download: the Overpass servers `overpass-api.de` and `lz4.overpass-api.de` rejected the Studio's requests (HTTP 406), so the download had to fall back to slower servers. Fixed. On errors, the start of the server's reply is now also shown in the log.

Install: download `TPF3-Map-Studio-v0.6.1-win64.zip`, extract the whole ZIP, run `TPF3-Map-Studio.exe`. Windows may warn on first start ("More info" -> "Run anyway"); antivirus false positives are known for PyInstaller programs.

SHA-256: `56dc9486d6ce5cae224b1868f9c29b4d05632f5f6c9b4cedd69bc3063d4b5a8b`

Note: unofficial tool, not affiliated with Urban Games.
