# Luxemburg (MNT 2024)

Für Karten in Luxemburg gibt es die Höhenquelle **Luxemburg MNT 2024 (0,5 m)**. Sie nutzt das **Geländemodell (MNT) der Lidar-Befliegung 2024** der Administration du cadastre et de la topographie (ACT): ein Modell aus Laserscanning, ohne Gebäude und Bewuchs, mit 0,5 m Auflösung für das ganze Land.

## So funktioniert es

Das ganze Land liegt auf data.public.lu in **einer einzigen Datei von rund 40 GB** (Koordinatensystem LUREF, EPSG:2169). Das Studio lädt sie **nie ganz**. Es holt nur die Teile, die dein Rechteck braucht:

- Die Datei ist für den Teilabruf aufgebaut. Das Studio fragt nur die benötigten Kacheln ab.
- Für TPF reicht 4 m pro Pixel. Das Studio nimmt deshalb die 4-m-Übersichtsstufe (rund 0,3 MB je Quadratkilometer). Bei großem **Stauchfaktor** wählt es automatisch eine gröbere Stufe.
- Die Kacheln werden entpackt und im Zwischenspeicher abgelegt: `%USERPROFILE%\.tpf3_map_studio\lux_mnt_cache`. Beim zweiten Mal geht nichts mehr über das Netz.
- Die Umrechnung zwischen GPS-Koordinaten und LUREF macht das Studio selbst (Genauigkeit rund 1 m, bei 4 m pro Pixel ohne Folgen).

Ganz Luxemburg (rund 2.600 km²) wären etwa 800 MB Download.

## Schritt für Schritt

1. Rechteck in Luxemburg setzen und OSM-Daten laden (siehe [OSM-Daten laden](help:osm-daten)).
2. Heightmap-Dialog öffnen. Unter **Höhenquelle** den Eintrag **Luxemburg MNT 2024** wählen. Er ist nur anklickbar, wenn der Kartenmittelpunkt in Luxemburg liegt.
3. **Höhendaten herunterladen.** Ein Fenster zeigt den Fortschritt und lässt sich jederzeit abbrechen, geladene Kacheln bleiben erhalten.
4. Weiter wie bei jeder Quelle, siehe [Wasser und Gelände](help:wasser-und-gelaende) und [Export und Import](help:export-und-import).

## Lizenz und Quellenangabe

Die Daten stehen unter **CC0 1.0** (frei nutzbar). Das Studio führt die Quellenangabe trotzdem mit, zeigt sie unter der Höhenquelle an und übernimmt sie in *Beschreibung zum Teilen*:

> Datenquelle: Administration du cadastre et de la topographie (ACT), Luxembourg – Lidar 2024, MNT (data.public.lu, CC0 1.0)

## Gut zu wissen

- Wo dem Modell Daten fehlen (zum Beispiel jenseits der Landesgrenze), ergänzt das Studio aus Copernicus.
- Auf Wasserflächen hat ein Laser-Geländemodell oft keine oder unruhige Werte. Dafür gibt es die Wasser-Einstellungen im Heightmap-Dialog.
- Es gibt auch ein Oberflächenmodell (MNS, mit Gebäuden und Bäumen). Das Studio nutzt nur das Geländemodell.
- Neu in Version 0.7.0. Der Test mit einem echten Rechteck steht noch aus.
