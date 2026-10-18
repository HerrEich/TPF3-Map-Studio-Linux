# Höhenfenster und Alpen

Der Karteneditor von TPF3 nimmt beim Import nur Höhen von **−100 bis 3177 m** an (im Spiel getestet). Liegt dein Gelände darüber oder darunter, zum Beispiel in den Alpen, zeigt der Dialog unten einen Hinweis. Setze dann den Haken **Höhenfenster begrenzen**.

Das Fenster gilt in den Werten, die du im Editor einträgst: Mit dem Haken *Werte auf Wasserhöhe 0 beziehen* ist es relativ zur Wasserhöhe. Voreingestellt ist der Bereich des Geländes innerhalb der Editor-Grenzen. Mit den Feldern **Fenster von … bis** wird es enger, der **Schieberegler** verschiebt es (gerechnet wird beim Loslassen).

## Drei Modi für alles außerhalb

- **Oben kappen**: Alles über dem Fenster wird flach auf die Obergrenze gesetzt, die Gipfel werden planiert. Das Fenster liegt zunächst an der tiefsten Stelle.
- **Unten abschneiden**: Alles unter dem Fenster wird flach auf die Untergrenze gesetzt. Das Fenster liegt zunächst an der höchsten Stelle.
- **Stauchen**: Das ganze Gelände wird ins Fenster gedrückt, über und unter der Wasserhöhe getrennt. Die Wasserhöhe bleibt erhalten, ein Gelände, das schon passt, wird nicht gestreckt.

Die Vorschau färbt betroffene Stellen ein: **rot** = tiefer gesetzt, **hellblau** = höher gesetzt. Darunter steht zum Beispiel „4,2 % der Fläche werden planiert“, gerechnet auf der ganzen Karte. Vorschau, Zahlen unten und exportierte Datei benutzen dasselbe Raster. Liegt die Wasserhöhe außerhalb des Fensters, warnt der Dialog.
