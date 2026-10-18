# Export und Import im Spiel

## Im Studio

1. **Unten im Dialog den Text lesen** und abschreiben oder fotografieren:
   *Im TPF3-Import eintragen: Mindesthöhe …, Maximalhöhe …, Wasserhöhe …* und *Kartengröße und -format im Spiel: …*. Diese Zahlen gelten immer für genau die aktuellen Einstellungen und ändern sich mit jeder Option.
2. Der Haken **Werte auf Wasserhöhe 0 beziehen** schaltet auf die Variante um, die das TPF3-Wiki für Biome und Materialien empfiehlt. Die Mindesthöhe kann dabei negativ werden. Mit echten Höhen liegt alles entsprechend höher im Spiel, weiße Flächen auf den Höhen können zunehmen.
3. **Exportieren…** Der Dialog schlägt den `heightmaps`-Ordner von TPF3 vor. Gib der Datei einen **eindeutigen Namen** ohne Umlaute und Sonderzeichen.

## Im Spiel (TPF3-Karteneditor)

1. Karteneditor öffnen. Bei den Einstellungen unter **Welt** dieselbe **Kartengröße** und dasselbe **Kartenformat** wählen wie im Studio-Text. Fehlt eine Größe (zum Beispiel Gigantomanisch), steht laut Wiki in der `settings.lua` der Schalter `experimentalMapFeatures`.
2. Den Dialog **Heightmap importieren** öffnen, Reiter **Heightmap**.
3. Die exportierte Datei in der Liste anklicken. Steht sie nicht drin: Dialog schließen, neu öffnen und prüfen, ob die Datei im Ordner `heightmaps` liegt (`…\Steam\userdata\<deine Steam-ID>\3493540\local\heightmaps`).
4. **Mindesthöhe, Maximalhöhe** und **Wasserhöhe** genau wie im Studio-Text eintragen, **Assets behalten: Nein**.
5. Die Vorschau rechts ansehen: Stimmt die Form? Steht nur der Fluss unter Wasser (blau)?
6. **Import** klicken.

> Trägst du im Spiel eine andere Wasserhöhe ein als im Studio, entstehen Pfützen und Löcher.

## Bäume, Städte, Industrien

Die Biome-Maske, Städte und Industrien kommen als eigene Dateien, siehe [Biome, Städte und Industrien](help:biome-staedte-industrien).
