# Erste Schritte

Das TPF3 Map Studio macht aus einem Ausschnitt der echten Welt Dateien für den Karteneditor von Transport Fever 3: eine **Heightmap** (16-Bit-PNG), auf Wunsch eine **Biome-Maske**, **Städte**, **Industrien** und einen **Bahnhofsplan** zum Nachbauen.

## Der Ablauf in sechs Schritten

1. **Rechteck setzen.** Lege auf der Karte den Ausschnitt fest, der später deine Spielkarte wird. → [Karte und Rechteck](help:karte-und-rechteck)
2. **OSM-Daten laden.** Flüsse, Seen, Wälder, Orte und Industrien kommen aus OpenStreetMap. → [OSM-Daten laden](help:osm-daten)
3. **Höhendaten laden.** Im Heightmap-Dialog eine Höhenquelle wählen und herunterladen. → [Heightmap erstellen](help:heightmap)
4. **Wasser und Gelände einstellen.** Wasserhöhe, Ufer, Glättung. → [Wasser und Gelände](help:wasser-und-gelaende)
5. **Exportieren.** Die Heightmap als PNG speichern, die Zahlen für den Import ablesen.
6. **Im Spiel importieren.** → [Export und Import im Spiel](help:export-und-import)

## Wo fange ich an?

| Du willst … | Dann lies … |
|---|---|
| eine Karte nach einem echten Vorbild bauen | die Schritte oben, dann [Höhenquellen](help:hoehenquellen) |
| eine Karte in Österreich bauen | [Österreich (BEV)](help:oesterreich-bev) |
| eine Karte in Luxemburg bauen | [Luxemburg (MNT 2024)](help:luxemburg-mnt) |
| eine alte TPF2-Karte nach TPF3 mitnehmen | [TPF2-Karte nach TPF3](help:tpf2-nach-tpf3) |
| Bäume, Städte und Industrien aus OSM | [Biome, Städte und Industrien](help:biome-staedte-industrien) |
| etwas funktioniert nicht | [Häufige Fragen und Fehler](help:haeufige-fragen) |

## Tipps für den Anfang

- **Erst klein testen.** Ein kleines Rechteck lädt in Minuten, ein großes braucht deutlich länger. So siehst du schnell, ob alles passt.
- **Projekt speichern.** *Datei → Speichern* sichert Rechteck, Drehung und geladene Ebenen als `.tpf2ms`-Datei.
- **Eindeutige Dateinamen.** Gib jeder exportierten Heightmap einen eigenen Namen, zum Beispiel `rhein_osmwasser.png`, ohne Umlaute und Sonderzeichen.
- **Zahlen aufschreiben.** Die Werte unten im Heightmap-Dialog (Mindesthöhe, Maximalhöhe, Wasserhöhe) brauchst du beim Import im Spiel.
