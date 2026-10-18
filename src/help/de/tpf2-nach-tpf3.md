# TPF2-Karte nach TPF3 übernehmen

Du hast eine Karte für Transport Fever 2 gebaut und möchtest sie in Transport Fever 3 weiterspielen? Das Map Studio nimmt die **Heightmap deiner TPF2-Karte** und macht daraus Dateien, die der TPF3-Karteneditor annimmt: eine Heightmap mit sauberen Ufern und auf Wunsch eine Biome-Maske.

Es gibt zwei Wege. Such dir den aus, der zu deiner Karte passt:

| | Weg A: Fiktive Karte | Weg B: Karte nach echten Daten |
|---|---|---|
| Passt für | selbst erfundene Landschaften | Karten nach einem echten Vorbild |
| Was du brauchst | nur die Heightmap-PNG | Heightmap-PNG + OpenStreetMap-Daten |
| Wasser | alles Wasser liegt auf einer Höhe | Flüsse und Seen kommen aus OpenStreetMap, Flüsse mit Gefälle sind möglich |
| Biome | aus der Höhe berechnet | aus OpenStreetMap (Wald, Felder …) |

**Voraussetzung für beide Wege:** TPF3 Map Studio ab Version 0.6.0. Die Quelle „Eigene TPF2-Heightmap“ heißt im Heightmap-Dialog genauso.

---

## Vorher: Die Heightmap-PNG

- Gebraucht wird die **16-Bit-Graustufen-PNG**, mit der die Karte im TPF2-Karteneditor erstellt wurde.
- Die PNG enthält **keine Meterangaben**, nur Grauwerte von Schwarz bis Weiß. Welche Höhe in Metern Schwarz (Mindesthöhe) und Weiß (Maximalhöhe) bedeuten, hast du beim TPF2-Import selbst angegeben. **Schreib dir diese Werte auf**, du brauchst sie gleich. TPF3 nimmt Höhen zwischen **−100 und 3177 m**.
- TPF rechnet mit 4 Metern pro Pixel. Ein Beispiel: 2689 × 13441 Pixel sind 10,75 × 53,76 km, das ist die Kartengröße „Größenwahnsinnig 1:5“. Das Studio zeigt dir nach dem Laden, zu welcher Kartengröße deine Datei passt.
- Hat deine PNG nur 8 Bit, streckt das Studio sie auf 16 Bit. Dabei können sichtbare Höhenstufen entstehen.

---

## Weg A: Fiktive Karte

Alles Wasser liegt in TPF auf einer Ebene. Bei erfundenen Karten ist das ohnehin so gebaut, deshalb reicht hier die Heightmap allein.

1. Im Studio: Menü **„TPF2-Karte übernehmen…“** öffnen.
2. **„Heightmap wählen…“** und die PNG auswählen. Das Studio zeigt Größe und passende Kartengröße an.
3. **Mindesthöhe** und **Maximalhöhe** eintragen (die Werte vom TPF2-Import).
4. **Wasserhöhe** einstellen. Schau in der Vorschau auf **„Wasser (blau)“**: Seen und Flüsse sollen gefüllt sein, aber kein Land soll absaufen. Eine Wasserhöhe gleich der Mindesthöhe bedeutet **kein Wasser**.
5. **„Ufer bereinigen“** angehakt lassen (empfohlen). Das entfernt kleine Pfützen und füllt sie glatt auf, hebt flaches Land knapp über das Wasser und vertieft flaches Wasser. So entstehen klare Ufer und keine Löcher im Spiel. Die Vorschlagswerte sind **„Land mindestens über Wasser“** 1,5 m, **„Wasser mindestens tief“** 2,0 m. Gelände weiter weg vom Wasser bleibt unverändert.
6. Unter **„Biome nach Höhe“** legst du fest, welches Biom unten, in der Mitte und oben liegt und wo die Grenzen sind. Auch für **„Unter Wasser“** gibt es ein Biom. Fels und Schnee färbt das Spiel selbst nach Höhe und Steilheit. Die Voreinstellung ist ein Vorschlag, schau dir das Ergebnis in der Vorschau **„Biome“** an.
7. **„Heightmap speichern…“**. Wähle einen **anderen Dateinamen** als die TPF2-Datei (die Originaldatei wird nie überschrieben). Das Studio ersetzt Umlaute und Sonderzeichen im Namen, weil sie im Spiel Probleme machen können.
8. Optional: **„Biome-Maske speichern…“**.

**Im Spiel (TPF3-Karteneditor):**

- **Heightmap:** Karteneditor → Heightmap importieren → die gespeicherte Datei wählen und dieselben Werte eintragen: **Mindesthöhe, Maximalhöhe, Wasserhöhe** (wie im Studio). Sieht das Studio die Datei im Spiel nicht, kopiere sie in den TPF3-Heightmap-Ordner (`…\Steam\userdata\<deine Steam-ID>\3493540\local\heightmaps`).
- **Biome:** Karteneditor → Heightmap importieren → Reiter **Biome** → bei **„Biome“** die gespeicherte Maske wählen, **Berge und Flüsse leer lassen** → **Anwenden**.

> **Wichtig:** Trägst du im Spiel eine andere Wasserhöhe ein als im Studio, entstehen Pfützen und Löcher. Die Bereinigung gilt genau für die Wasserhöhe, die du im Studio eingestellt hast. Hast du im Studio *kein Wasser* eingestellt, warnt dich das Studio vor dem Speichern.

---

## Weg B: Karte nach echten Daten (mit OpenStreetMap)

Hier bleibt dein Gelände aus der TPF2-Heightmap, aber Flüsse, Seen, Wälder, Städte und Industrien kommen aus echten OpenStreetMap-Daten.

1. **Rechteck setzen.** Lege im Studio auf der Karte ein Rechteck an, das genau **zur Größe deiner PNG passt** (zum Beispiel „Größenwahnsinnig 1:5“, hochkant). **Mittelpunkt und Drehung** müssen mit deiner ursprünglichen TPF2-Karte übereinstimmen: Die PNG weiß nicht, wo auf der Erde sie liegt. Das Studio legt sie genau auf dein Rechteck.
2. **OSM-Daten laden.** Bei großen Gebieten dauert das, die Server von OpenStreetMap sind öffentlich und manchmal überlastet. Bereits geladene Kacheln bleiben gespeichert, ein erneuter Start lädt nur das Fehlende.
3. **Heightmap-Dialog** öffnen. Als **Höhenquelle** wählst du **„Eigene TPF2-Heightmap (PNG)“**, wählst die Datei und trägst Mindesthöhe (Schwarz) und Maximalhöhe (Weiß) ein. Passt die Größe nicht zum Rechteck, nennt dir das Studio beide Größen.
4. **Wasserhöhe** mit **„Wasserhöhe aus den OSM-Gewässern vorschlagen“** bestimmen lassen.
5. Haken setzen:
   - **„Wasser nur dort, wo OpenStreetMap Wasser hat“**: Flüsse und Seen werden eingetieft, sonst nichts.
   - **„Gefälle ausgleichen“**: Flüsse mit Gefälle in der Heightmap liegen in TPF trotzdem auf einer Wasserebene. Das gleicht es entlang der Flüsse aus.
6. Die 2D-Vorschau lässt sich zoomen: **Mausrad** zoomt, mit gedrückter Maustaste **ziehen** verschiebt, **Doppelklick** zeigt wieder die ganze Karte. Prüfe, ob Flüsse in den Tälern liegen.
7. **„Exportieren…“** speichert die Heightmap. Danach brauchst du je nach Wunsch **„Biome-Maske aus OSM…“**, **„Städte aus OSM…“** und **„Industrien aus OSM…“**. Der Import im Spiel läuft wie in Weg A.

**Gut zu wissen:**
- Beim Speichern eines Projekts merkt sich das Studio die gewählte PNG nicht. Nach dem Öffnen wählst du sie neu.
- Liegen die OSM-Flüsse quer zu den Tälern, ist das Rechteck verschoben oder gedreht. Setze Mittelpunkt und Drehung wie bei der Originalkarte.

---

## Häufige Fragen

**Im Spiel sind Pfützen oder trockene Löcher.** Die Wasserhöhe im Spiel weicht von der im Studio ab, oder im Studio war „Ufer bereinigen“ aus.

**Zu viel oder zu wenig Wasser.** Stelle die Wasserhöhe in der Vorschau neu ein. Zu viel blaue Fläche: niedrigerer Wert. Flüsse bleiben trocken: höherer Wert.

**Die Meldung „Die PNG passt nicht zum Rechteck“.** Das Rechteck hat eine andere Größe als die PNG. Gleiche es an (Pixel = Meter / 4 + 1) oder wähle die passende Kartengröße.

**Das Bild liegt quer zur Kartengröße.** Deine PNG ist gegenüber der TPF3-Kartengröße um 90° gedreht.

**Die Datei wird im Spiel nicht angenommen.** Die Datei muss ein Graustufenbild mit 16 Bit sein und eine bekannte TPF3-Kartengröße haben (Meter / 4 + 1 Pixel). Das Studio warnt, wenn die Größe unbekannt ist.

**Dateinamen.** Verwende keine Umlaute oder Sonderzeichen in Dateinamen für das Spiel.

---

*Stand: Weg A ist im Spiel getestet. Die Biome-Voreinstellung ist ein Vorschlag und wurde bisher nur mit einer Testkarte geprüft. Rückmeldungen mit echten Karten sind willkommen.*
