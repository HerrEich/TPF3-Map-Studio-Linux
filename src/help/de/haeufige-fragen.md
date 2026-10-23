# Häufige Fragen und Fehler

## Download und Daten

**Der OSM-Download bricht ab oder meldet „Server überlastet“.** Die öffentlichen Overpass-Server sind manchmal voll. Das Studio wechselt den Server und wartet. Starte den Download später noch einmal, geladene Kacheln bleiben gespeichert. Siehe [OSM-Daten laden](help:osm-daten).

**„Es konnten nicht alle Kacheln geladen werden.“** Starte den Download der Höhendaten erneut, er lädt nur das Fehlende nach.

**Die Quelle DGM1, swissALTI3D, AHN, BEV oder Luxemburg ist ausgegraut.** Diese Quellen sind nur wählbar, wenn der Kartenmittelpunkt im jeweiligen Land liegt. Siehe [Höhenquellen](help:hoehenquellen).

**Die Meldung „Unable to allocate … MiB for an array“ (zu wenig Arbeitsspeicher).** Verkleinere das Rechteck oder schließe andere Programme. Neuere Versionen laden Copernicus-Kacheln sparsam, aktualisiere also auf die neueste Version.

**Der Download dauert sehr lange.** Das gilt vor allem für DGM1 (Begrenzung der Anzahl pro Minute) und für sehr große Rechtecke. Du kannst den Download abbrechen, die Kacheln bleiben erhalten.

**Wie viel Speicherplatz belegen die Höhendaten?** *Hilfe → Cache verwalten…* zeigt es und räumt auf.

## Vorschau und Ergebnis

**Der Fluss hat gerade Streifen.** Bei Copernicus fehlt die Feinheit. Nutze *Wasser nur dort, wo OpenStreetMap Wasser hat* und eine genaue Quelle, wenn es sie für dein Gebiet gibt.

**Im Spiel sind Pfützen oder trockene Löcher.** Die Wasserhöhe im Spiel weicht von der im Studio ab. Trage genau den Wert aus dem Studio-Text ein.

**Weiße oder graue Flächen auf den Höhen.** Das Spiel färbt nach der Höhe. Nutze *Höhen stauchen* und *Werte auf Wasserhöhe 0 beziehen*, siehe [Wasser und Gelände](help:wasser-und-gelaende).

**Der Editor nimmt die Höhen nicht an oder das Gelände ragt über 3177 m (Alpen).** Siehe [Höhenfenster und Alpen](help:hoehenfenster).

**Die Heightmap erscheint nicht in der Liste des Spiels.** Dialog schließen und neu öffnen, außerdem prüfen, ob die Datei im Ordner `heightmaps` liegt. Siehe [Export und Import](help:export-und-import).

**Die Datei wird nicht angenommen.** Sie muss ein 16-Bit-Graustufenbild sein und eine Größe von Meter ÷ 4 + 1 Pixel haben. Verwende keine Umlaute oder Sonderzeichen im Dateinamen.

## Programm

**Wo ist die Logdatei?** *Hilfe → Log-Ordner öffnen*.

**Ich möchte einen Fehler melden.** *Hilfe → Fehlerbericht erstellen…* speichert Log sowie Versions- und Systemangaben als ZIP. Namen und Pfade werden entfernt. Schick die ZIP-Datei bei der Meldung auf GitHub mit.

**Wie wechsle ich die Sprache?** Menü *Sprache / Language*, die Änderung gilt nach einem Neustart.

**Die Hilfe ist nur auf Deutsch.** Die Kapitel dieser Hilfe gibt es zunächst nur auf Deutsch. Der Rest des Programms ist zweisprachig.
