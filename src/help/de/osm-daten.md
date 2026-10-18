# OSM-Daten laden

Flüsse, Seen, Wälder, Wiesen, Orte, Industrien und Bahnhöfe kommen aus **OpenStreetMap**. Ohne diese Daten funktionieren im Heightmap-Dialog die Optionen *Wasser nur dort, wo OpenStreetMap Wasser hat* und *Trassen und Siedlungen einebnen* nicht, und auch Biome, Städte und Industrien lassen sich nicht erzeugen.

## Laden

1. Setze das Rechteck (siehe [Karte und Rechteck](help:karte-und-rechteck)).
2. *Werkzeuge → OSM laden*. Die Statusleiste zeigt den Fortschritt.
3. Warte, bis der Download fertig ist. **Danach** öffnest du den Heightmap-Dialog. Das geladene Rechteck bleibt erhalten.

## Was geladen wird

*Werkzeuge → Overpass-Abfrage…* stellt per Haken ein, was geladen wird: Gleistypen, Straßentypen, Gebäude, Parks und Gärten, Flächennutzung, Vegetation, Gewässer, Orte, Siedlung/Heide/Moor/Fels (für die Biome) und Industrie-Objekte. Bahnhöfe und Haltepunkte werden immer mitgeladen. Nach einer Änderung musst du OSM neu laden.

## Große Gebiete

Die Overpass-Server von OpenStreetMap sind öffentlich und manchmal überlastet. Das Studio teilt große Gebiete in Kacheln von etwa 11 km:

- Bereits geladene Kacheln bleiben **gespeichert** (rund 30 Tage). Ein erneuter Start lädt nur das Fehlende.
- Bei Überlastung **wechselt** das Studio den Server und **legt Pausen ein**, statt den Server zu bedrängen.
- Sind am Ende einzelne Kacheln nicht ladbar, nennt das Studio, wie viele von wie vielen fehlen. Starte den Download dann später einfach noch einmal.

**Tipps:** Lade große Karten in Abschnitten. Nachts und morgens sind die Server meist weniger ausgelastet.

## Vorab-Prüfung

*Werkzeuge → Vorab-Prüfung…* prüft die geladenen Daten mit einer Ampel: Sind Knoten und Wege plausibel, gibt es 0 Treffer trotz aktivierter Kategorie, wurden Orte gefunden?
