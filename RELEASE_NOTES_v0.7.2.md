# TPF3 Map Studio v0.7.2

Behebt das Einfrieren beim Einschalten der Flüsse-Ebene und bringt neue Hilfen für Höhenkarten, Wasser, Biome und Natur-Details. / Fixes the freeze when switching on the rivers layer and adds new helpers for height maps, water, biomes and nature details.

## Deutsch

Behoben
- Bei sehr großen Gebieten fror die Karte ein, sobald die Ebene „Flüsse“ eingeschaltet wurde. Jede Ebene hat jetzt ein eigenes Limit, und bei Flüssen und Straßen werden die wichtigsten Objekte zuerst gezeigt (zum Beispiel Flüsse und Kanäle vor Bächen und Gräben). Export und Berechnung nutzen weiterhin alle Daten. Danke an Seppestoni für den Fehlerbericht.

Neu
- Flussbreite: Im Heightmap-Dialog lässt sich die Breite der gezeichneten Flüsse und Kanäle von 1 bis 12 Pixel einstellen (Standard 3 Pixel, 1 Pixel = 4 m im Spiel). Breiteres Wasser ist für Schiffe besser befahrbar.
- Maßstabs-Hinweis im Rechteck-Dialog: zeigt, wie breit Flüsse im Spiel sind, dass Bäche und Gräben nicht als Wasser gezeichnet werden und wie sich 1000 m echte Höhe im Spiel auswirken.
- Wasser-Check im Heightmap-Dialog: zeigt, wie stark das Gelände am Wasser abgesenkt wird, und weist darauf hin, wenn über die Hälfte der Wasserflächen zu hoch liegt.
- Steigungs-Overlay in der Vorschau: gelb ab 4 %, orange ab 10 %, rot ab 24 % (ungefähr Gebirge im Spiel), mit Flächenanteilen. Die Steigung ist auf die Spielwerte umgerechnet (Stauchfaktor und Höhenskalierung).
- Berg-, See- und Sumpf-Masken: schlägt aus der Höhenkarte drei PNG-Masken für den Biome-Tab vor. Die Berge treffen die Testmasken ordentlich, Seen und Sümpfe nur grob. Es ist ein Ausgangspunkt zum Nachmalen. Danke an alaric_stormblade für die Testkarten.
- Natur-Details-Plan: schreibt Weinberge, Obstwiesen, Mauern und Hecken aus OSM als .csv und .json (Lage in Metern ab Kartenmitte, bei Weinbergen Reihenrichtung und geschätzte Reihenzahl, kleine Flächen unter einer Mindestgröße werden weggelassen). Als Vorlage zum Nachbauen, zum Beispiel mit dem Zaunbaukasten. Mauern und Hecken gibt es nur, wenn beim OSM-Laden „Natur-Details“ angehakt war.

Installation: `TPF3-Map-Studio-v0.7.2-win64.zip` herunterladen, die ganze ZIP entpacken, `TPF3-Map-Studio.exe` starten. Windows warnt beim ersten Start eventuell („Weitere Informationen“ -> „Trotzdem ausführen“), bei PyInstaller-Programmen sind Virenscanner-Fehlalarme bekannt.

SHA-256: `12cbd37c089f3970bbf6b2a5225216253b670b40ec9b170bc3c809c2e14670e6`

Hinweis: inoffizielles Werkzeug, keine Verbindung zu Urban Games.

„Kaffeekasse – Freiwillig & von Herzen! ❤️“ https://paypal.me/PEttelt?locale.x=de_DE&country.x=DE

## English

Fixed
- With very large areas the map froze as soon as the "Rivers" layer was switched on. Each layer now has its own limit, and for rivers and roads the most important objects are shown first (for example rivers and canals before streams and ditches). Export and calculations still use all data. Thanks to Seppestoni for the bug report.

New
- River width: in the heightmap dialog the width of drawn rivers and canals can be set from 1 to 12 pixels (default 3 pixels, 1 pixel = 4 m in the game). Wider water is easier for ships.
- Scale hint in the rectangle dialog: shows how wide rivers are in the game, that streams and ditches are not drawn as water, and what 1000 m of real height becomes in the game.
- Water check in the heightmap dialog: shows how much the terrain is lowered at water and warns when more than half of the water areas lie too high.
- Slope overlay in the preview: yellow from 4 %, orange from 10 %, red from 24 % (roughly mountains in the game), with area shares. The slope is converted to game values (compression factor and height scale).
- Mountain, lake and swamp masks: suggests three PNG masks for the biome tab from the height map. Mountains match the test masks reasonably well, lakes and swamps only roughly. It is a starting point to paint over. Thanks to alaric_stormblade for the test maps.
- Nature details plan: writes vineyards, orchards, walls and hedges from OSM as .csv and .json (position in metres from the map centre; for vineyards the row direction and estimated row count; small areas below a minimum size are left out). A template for rebuilding, for example with the fence builder. Walls and hedges only exist if "Natur-Details" was ticked when loading OSM.

Install: download `TPF3-Map-Studio-v0.7.2-win64.zip`, extract the whole ZIP, run `TPF3-Map-Studio.exe`. Windows may warn on first start ("More info" -> "Run anyway"); antivirus false positives are known for PyInstaller programs.

SHA-256: `12cbd37c089f3970bbf6b2a5225216253b670b40ec9b170bc3c809c2e14670e6`

Note: unofficial tool, not affiliated with Urban Games.

“Coffee fund – Voluntary & from the heart! ❤️” https://paypal.me/PEttelt?locale.x=de_DE&country.x=DE
