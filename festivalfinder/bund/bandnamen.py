"""Bandnamen vereinheitlichen, bevor Festivals zusammenfinden.

Zwei Aufgaben, die zusammengehören: Zu jedem Bandschlüssel eine verbindliche
Schreibweise finden — und die Kürzel abschalten, die in diesem Bestand eine
andere Band meinen.
"""

from ..kern.fund import Fund
from ..kern.text import Kuerzel, canonical_band, clean, festival_key, fold


def kollisionen(funde: list[Fund], kuerzel: Kuerzel) -> list[str]:
    """Kürzel abschalten, die eine andere Band meinen.

    Steht ein Kürzel selbst im Programm, gibt es zwei Möglichkeiten. Bei „TBS"
    führen alle betroffenen Festivals zugleich The Butcher Sisters auf —
    dieselbe Band, zweimal geschrieben, das Kürzel gehört also aufgelöst. „LP"
    dagegen teilt sich mit Linkin Park kein einziges Lineup: Das ist die
    Sängerin LP, und ein Alias würde acht Einträge umbenennen.

    Entscheidend ist deshalb nicht das bloße Vorkommen, sondern ob Kürzel und
    ausgeschriebener Name je gemeinsam auf einem Plakat stehen. Geprüft wird je
    Festival, nicht je Quellseite: Die beiden Schreibweisen stehen oft auf den
    Seiten verschiedener Quellen und treffen sich erst hier. Für die Suche auf
    der Webseite bleiben alle Kürzel nutzbar — dort erscheinen dann beide.
    """
    programme: dict[tuple[str, str], set[str]] = {}
    for f in funde:
        schluessel = (festival_key(f.name), f.jahr)
        programme.setdefault(schluessel, set()).update(fold(b) for b in f.lineup)

    kollidiert = []
    for kurz, voll in list(kuerzel.nach_kuerzel.items()):
        voll_gefaltet = fold(voll)
        allein = zusammen = False
        for namen in programme.values():
            if kurz not in namen:
                continue
            if voll_gefaltet in namen:
                zusammen = True
                break
            allein = True
        if allein and not zusammen:
            kuerzel.abschalten(kurz)
            kollidiert.append(kurz)
    return sorted(kollidiert)


def verzeichnis(funde: list[Fund], kuerzel: Kuerzel) -> tuple[dict[str, str], dict]:
    """Je Bandschlüssel eine verbindliche Schreibweise, plus Statistik."""
    varianten: dict[str, list[str]] = {}
    for f in funde:
        for b in f.lineup:
            varianten.setdefault(kuerzel.band_key(b), []).append(clean(b))

    # Ein hinterlegter Alias schlägt die Mehrheitsregel: sonst gewänne bei
    # gleicher Häufigkeit die Abkürzung statt des ausgeschriebenen Namens.
    namen = {k: kuerzel.nach_schluessel.get(k) or canonical_band(v)
             for k, v in varianten.items() if k}
    verschieden = {k: sorted(set(v)) for k, v in varianten.items() if k}
    statistik = {
        "roh_schreibweisen": sum(len(v) for v in verschieden.values()),
        "gruppen": len(namen),
        "vereinheitlicht": sum(len(v) - 1 for v in verschieden.values() if len(v) > 1),
        "beispiele": [(namen[k], v) for k, v in verschieden.items() if len(v) > 1][:400],
    }
    return namen, statistik
