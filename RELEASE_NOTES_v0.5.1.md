# TPF3 Map Studio v0.5.1

Eigene DGM1-Kacheln als ASC-Dateien direkt im Studio nutzen, Stauchfaktor mit allen Höhenquellen, schlankere Overpass-Abfragen, ein festes Kachelraster für große OSM-Auswahlen, robusterer Overpass-Download und eine Korrektur für DGM1 in Ostbayern. / Use your own DGM1 tiles as ASC files directly in the Studio, compression factor with all height sources, leaner Overpass queries, a fixed tile grid for large OSM selections, a more robust Overpass download and a fix for DGM1 in eastern Bavaria.

## Deutsch

**Neu**
- **ASC-Dateien direkt im Studio umwandeln:** Bei der Quelle „DGM1 aus eigenen GeoTIFF-Kacheln“ erkennt der Heightmap-Dialog ASC-Dateien im gewählten Ordner und fragt, ob sie zu GeoTIFF zusammengefasst werden sollen. Damit lassen sich z. B. ASC-Daten aus Trient ohne Umweg über ein Zusatzprogramm verwenden.
- **Skript `tools\asc_zu_geotiff.py`** mit Anleitung: wandelt ASC-Kacheln außerhalb des Studios zu GeoTIFF um, für Eigene Kacheln.
- **Stauchfaktor mit allen Höhenquellen:** Bei gestauchten Karten sind jetzt auch DGM1 Deutschland, swissALTI3D, AHN Niederlande und eigene Kacheln wählbar, nicht mehr nur Copernicus. Je größer der Faktor, desto mehr Kacheln werden geladen.
- **Stauchfaktor unter 1 (ab 0,5):** Das reale Gebiet ist kleiner als die Spielkarte, die Höhen werden entsprechend angehoben. Das Rechteck-Tool zeigt dafür einen eigenen Hinweis.

**Verbessert**
- **Overpass:** Beim Aktivieren weiterer Merkmale werden nur die zusätzlich aktivierten Kategorien nachgeladen, nicht mehr alles von vorn.
- **OSM:** Große Auswahlen werden in einem festen Kachelraster geladen. Der Overpass-Dialog zeigt dazu Hinweise.
- **Overpass-Download:** Statusanzeige mit Wartezeiten, Berücksichtigung der Wartehinweise des Servers bei Überlastung (Retry-After), mehr schon gespeicherte Kacheln werden wiederverwendet. Nach etwa zehn vergeblichen Runden bei Serverproblemen bricht der Download mit einer klaren Meldung ab. Danke an **Volker** für die Vorlage (macOS-Fork)!

**Behoben**
- **DGM1 Deutschland in Bayern östlich von 12° Ost:** Der Dienst hoehendaten.de liefert Bayern durchgehend in UTM-Zone 32, das Studio fragte dort Zone 33 an und brach mit HTTP 400 ab. Jetzt wird bei einer Ablehnung automatisch die andere Zone versucht. Die Fehlermeldung zeigt außerdem den Text des Dienstes. Danke an Buzz für die Meldung.

**Installation:** `TPF3-Map-Studio-v0.5.1-win64.zip` herunterladen, die **ganze** ZIP entpacken, `TPF3-Map-Studio.exe` starten. Windows warnt beim ersten Start eventuell („Weitere Informationen“ -> „Trotzdem ausführen“), bei PyInstaller-Programmen sind Virenscanner-Fehlalarme bekannt.

**SHA-256:** `(wird nach dem Build eingetragen)`

**Hinweis:** inoffizielles Werkzeug, keine Verbindung zu Urban Games.

## English

**What's new**
- **Convert ASC files directly in the Studio:** with the source "DGM1 from own GeoTIFF tiles", the heightmap dialog detects ASC files in the chosen folder and asks whether to merge them into GeoTIFF. This makes ASC data, for example from Trento, usable without an extra program.
- **Script `tools\asc_zu_geotiff.py`** with a guide: converts ASC tiles to GeoTIFF outside the Studio, for own tiles.
- **Compression factor with all height sources:** compressed maps can now also use DGM1 Germany, swissALTI3D, AHN Netherlands and own tiles, not only Copernicus. The larger the factor, the more tiles are downloaded.
- **Compression factor below 1 (down to 0.5):** the real area is smaller than the game map, heights are raised accordingly. The rectangle tool shows its own note for this.

**Improved**
- **Overpass:** when you enable further features, only the additionally enabled categories are loaded, not everything again.
- **OSM:** large selections are loaded in a fixed tile grid. The Overpass dialog shows notes about it.
- **Overpass download:** status display with waiting times, honours the server's wait hints when overloaded (Retry-After), reuses more already cached tiles. After about ten failed rounds on server problems the download stops with a clear message. Thanks to **Volker** for the template (macOS fork)!

**Fixed**
- **DGM1 Germany in Bavaria east of 12° E:** the hoehendaten.de service delivers Bavaria consistently in UTM zone 32, but the Studio asked for zone 33 there and stopped with HTTP 400. If the service rejects a request, the other zone is now tried automatically. The error message also shows the service's text. Thanks to Buzz for reporting.

**Install:** download `TPF3-Map-Studio-v0.5.1-win64.zip`, extract the **whole** ZIP, run `TPF3-Map-Studio.exe`. Windows may warn on first start ("More info" -> "Run anyway"); antivirus false positives are known for PyInstaller programs.

**SHA-256:** `(will be added after the build)`

**Note:** unofficial tool, not affiliated with Urban Games.
