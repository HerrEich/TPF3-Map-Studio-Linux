# Österreich (BEV)

Für Karten in Österreich gibt es die Höhenquelle **BEV Österreich (1 m)**. Sie nutzt das **ALS-DTM-Höhenraster** des Bundesamts für Eich- und Vermessungswesen (BEV): ein Geländemodell aus Laserscanning, ohne Gebäude und Bewuchs, mit 1 m Auflösung für ganz Österreich (Stand der Daten: 15.09.2025).

## So funktioniert es

Die Daten liegen auf data.bev.gv.at in 55 Dateien zu je 50 × 50 km, jede rund **8 GB** groß. Das Studio lädt diese Dateien **nie ganz**. Es holt nur die Teile, die dein Rechteck braucht:

- Die Dateien sind für den Teilabruf aufgebaut. Das Studio fragt nur die benötigten Kacheln von 2 × 2 km ab (rund 0,6 MB je Kachel, bei der 4-m-Stufe).
- Für TPF reicht 4 m pro Pixel. Das Studio nimmt deshalb die 4-m-Stufe. Bei großem **Stauchfaktor** wählt es automatisch eine gröbere Stufe.
- Die Kacheln werden entpackt und im Zwischenspeicher abgelegt: `%USERPROFILE%\.tpf3_map_studio\bev_at_cache`. Beim zweiten Mal geht nichts mehr über das Netz.

Ein Rechteck von 10 × 54 km braucht etwa 100 MB Download.

## Schritt für Schritt

1. Rechteck in Österreich setzen und OSM-Daten laden (siehe [OSM-Daten laden](help:osm-daten)).
2. Heightmap-Dialog öffnen. Unter **Höhenquelle** den Eintrag **BEV Österreich** wählen. Er ist nur anklickbar, wenn der Kartenmittelpunkt in Österreich liegt.
3. **Höhendaten herunterladen.** Ein Fenster zeigt den Fortschritt und lässt sich jederzeit abbrechen, geladene Kacheln bleiben erhalten.
4. Weiter wie bei jeder Quelle, siehe [Wasser und Gelände](help:wasser-und-gelaende) und [Export und Import](help:export-und-import).

## Lizenz und Quellenangabe

Die Daten stehen unter **CC BY 4.0**. Die Quellenangabe ist Pflicht, das Studio zeigt sie unter der Höhenquelle an und übernimmt sie in *Beschreibung zum Teilen*:

> Datenquelle: BEV – Bundesamt für Eich- und Vermessungswesen, ALS DTM Höhenraster 1 m (CC BY 4.0)

## Gut zu wissen

- Wo dem BEV-Modell Daten fehlen, ergänzt das Studio aus Copernicus.
- Das BEV bietet auch historische Karten an (zum Beispiel um 1900). Das sind keine Höhendaten, das Studio nutzt sie nicht.
- Getestet im Studio bei Graz (kleines Rechteck von 4 × 4 km und ein hohes Rechteck von etwa 7 × 36 km). *Im Spiel noch nicht getestet.*
