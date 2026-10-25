"""Reine Rechenhilfen fuer die Zug-Fortschrittsanzeige (ohne Qt, testbar)."""


def fraction(done, total):
    """Fortschritt 0.0 bis 1.0; bei total <= 0 immer 0.0."""

    if not total or total <= 0:
        return 0.0
    return max(0.0, min(1.0, done / total))


def ease(current, target, dt, speed=3.0):
    """
    Bewegt current weich auf target zu (exponentiell, unabhaengig von der
    Bildrate). Gibt den neuen Wert zurueck; springt bei sehr kleinem
    Abstand direkt auf target.
    """

    if abs(target - current) < 0.0005:
        return target
    step = 1.0 - pow(2.718281828, -speed * max(dt, 0.0))
    return current + (target - current) * step
