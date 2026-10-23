# Höhenquellen im Überblick

Die **Höhenquelle** bestimmt, wie genau dein Gelände wird. Wähle sie oben im Heightmap-Dialog.

| Quelle | Gebiet | Auflösung | Hinweis |
|---|---|---|---|
| Copernicus | weltweit | 30 m | mit Baumkronen, rauscht an Hängen, braucht Glätten |
| DGM1 Deutschland | Deutschland | 1 m | Kacheln über hoehendaten.de |
| DGM1 aus eigenen Kacheln | wo du Kacheln hast | 1 m | GeoTIFF-Ordner im 1-km-Raster |
| swissALTI3D Schweiz | Schweiz, Liechtenstein | 2 m | von swisstopo |
| AHN Niederlande | Niederlande | 2 m | von PDOK |
| BEV Österreich | Österreich | 1 m | nur Teilabruf, siehe [Österreich](help:oesterreich-bev) |
| Luxemburg MNT 2024 | Luxemburg | 0,5 m | nur Teilabruf, siehe [Luxemburg](help:luxemburg-mnt) |
| Eigene TPF2-Heightmap (PNG) | beliebig | wie die PNG | siehe [TPF2 nach TPF3](help:tpf2-nach-tpf3) |

Die Quellen für Deutschland, Schweiz, Niederlande, Österreich und Luxemburg erscheinen **nur, wenn der Kartenmittelpunkt in dem Land liegt**. Wo einer Quelle Daten fehlen, ergänzt das Studio aus Copernicus. Ein größerer Anteil aus Copernicus kann an den Nahtstellen kleine Höhenstufen erzeugen, das Studio warnt dann.

## Copernicus

Weltweit, aber nur etwa 30 m fein und mit Baumkronen. Die Kacheln (im Schnitt etwa 35 MB) kommen vom öffentlichen Copernicus-DEM-Bucket bei AWS. Gelände glätten ist hier sinnvoll.

## DGM1 Deutschland

1-m-Geländemodell der Bundesländer, genauer an Hängen und Böschungen. Die Kacheln kommen über den Webdienst hoehendaten.de, **höchstens etwa 20 Kacheln pro Minute**. Eine große Karte braucht deshalb etwa eine halbe Stunde. Das Fenster zeigt den Fortschritt und lässt sich abbrechen, geladene Kacheln werden beim nächsten Mal übersprungen.

Hast du die Kacheln selbst bei einem Landesportal geladen, wähle **DGM1 aus eigenen GeoTIFF-Kacheln** und den Ordner. Die Kacheln müssen auf dem 1-km-Raster liegen.

*Im Spiel am Rhein getestet (Bingen bis Koblenz, Größenwahnsinnig 1:5).*

## swissALTI3D Schweiz

Geländemodell von swisstopo mit 2 m Auflösung für die Schweiz und Liechtenstein. Die Kacheln kommen von data.geo.admin.ch.

*Im Spiel bei Bern getestet.*

## AHN Niederlande

Geländemodell mit 2 m Auflösung, ohne Gebäude und Bewuchs. Die Kacheln kommen von PDOK. Auf Wasserflächen hat das AHN keine Werte, dort ergänzt das Studio aus Copernicus.

*Bei Amsterdam im Spiel getestet.*

## Empfohlene Voreinstellung

Für DGM1, swissALTI3D, AHN, BEV und Luxemburg (die genauen Modelle) lässt *Empfohlen* das Glätten aus, ebnet mit 10 m ein und nimmt Wasser nach OSM mit 10 m Böschung. Für Copernicus gelten Glätten, Einebnen und Wasser nach OSM mit den Standardwerten.
