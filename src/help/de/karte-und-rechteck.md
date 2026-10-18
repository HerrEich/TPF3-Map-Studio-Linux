# Karte und Rechteck

## Kartenquelle wählen

Im Panel auf der Karte wechselst du die **Kartenquelle**:

- **Straßenkarte** (OpenStreetMap) für die Orientierung.
- **Karte + Relief** zeigt zusätzlich ein Schattenrelief, damit du Täler, Hänge und Bergkämme siehst. Für die Wahl des Ausschnitts am besten geeignet.
- Die **Eisenbahnkarte** (OpenRailwayMap) legt Gleise, Bahnhöfe und Signale darüber.
- Das **Maß-Gitter** hilft beim Abschätzen von Abständen und Größen.

## Marker und Auswahl

Mit dem **Marker**-Werkzeug setzt du per Klick einen Marker. Er liefert den Mittelpunkt für das Rechteck-Tool. Im Dock *Projekt* kannst du Marker umbenennen, löschen oder die Karte darauf zentrieren (Rechtsklick, Doppelklick zentriert).

## Das Rechteck

*Werkzeuge → Rechteck-Tool* legt den Kartenausschnitt an. Im Dialog stellst du ein:

- **Mittelpunkt** (Breite und Länge),
- **Kartengröße** im Format des Spiels. Der Dialog zeigt dir Kilometer und Pixel,
- **Drehwinkel**, damit das Rechteck zu deinem Fluss oder deiner Strecke passt,
- **Sicherheitsrand** für Downloads (Standard 500 m). Das ist ein zusätzlicher Rand um das Rechteck.

Das Rechteck lässt sich auf der Karte verschieben (blauer Punkt) und drehen (oranger Punkt). Öffnest du das Tool erneut, füllt es sich mit den Werten der aktuellen Auswahl.

### Größe und Pixel

TPF rechnet mit **4 Metern pro Pixel**. Die Heightmap hat Meter ÷ 4 + 1 Pixel pro Seite. Ein Beispiel: **Größenwahnsinnig 1:5** ist 10,752 × 53,76 km, das sind 2689 × 13441 Pixel.

> Wähle im Studio dieselbe **Kartengröße und dasselbe Format** wie später im Spiel. Nur dann passt das Seitenverhältnis, das Spiel streckt jedes Bild auf die Kartengröße.

## Messen

Das **Koordinaten-Messwerkzeug** zeigt beim ersten Klick Breite und Länge, beim zweiten zusätzlich die Entfernung (als Linie auf der Karte und in der Statusleiste).

## Ebenen

Im **Layer-Dock** schaltest du Ebenen mit dem Haken ein und aus. Das Schloss sperrt eine Ebene gegen Auswahl und Bearbeitung, der Balken stellt die Deckkraft ein, die Pfeile ändern die Reihenfolge. Nach *OSM laden* erscheinen die Bahnhöfe automatisch auf der Karte, die übrigen Ebenen schaltest du selbst ein.

## Projekte

*Datei → Speichern* schreibt Rechteck (mit Drehung), geladene Ebenen und den Heightmap-Status in eine `.tpf2ms`-Datei. *Datei → Projekt-Dashboard* zeigt alle Projekte eines Ordners auf einen Blick.
