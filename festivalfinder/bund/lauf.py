"""Aus vielen Funden ein Bestand.

Zuerst wird die Reihenfolge festgelegt. Die Seiten kommen aus vier Fäden
zurück, also jedes Mal anders, und die Stufen sind nicht vollständig
reihenfolgeunabhängig: Verschmilzt A mit B, findet C danach vielleicht keinen
Partner mehr. Bei acht Quellen fiel das nicht auf, bei zwölf unterschieden sich
zwei Läufe über denselben Funden um bis zu 29 Festivals — ohne dass sich an den
Quellen etwas geändert hätte.
"""

from datetime import date

from ..kern.festival import Festival
from ..kern.fund import Fund
from ..kern.orte import land_code, punkt_passt_zum_land
from ..kern.text import Kuerzel
from ..quellen import RANG
from . import bandnamen
from .stufen import NACH_STUFE1, stufe1_exakt


def zusammenfuehren(funde: list[Fund], namen: dict[str, str],
                    kuerzel: Kuerzel) -> list[Festival]:
    """Alle Funde zu Festivals bündeln, chronologisch sortiert."""
    funde = sorted(funde, key=lambda f: (RANG.get(f.quelle, 99), f.url, f.name))

    bestand = stufe1_exakt(funde, namen, kuerzel.band_key, RANG)
    for stufe in NACH_STUFE1:
        stufe(bestand)

    festivals = list(bestand.values())
    for f in festivals:
        f.land = land_code(f.land)
        # Noch einmal, jetzt gegen das zusammengetragene Land: Beim
        # Verschmelzen kann die Koordinate der einen Quelle auf das Land der
        # anderen treffen. So stand Lollapalooza Berlin in Chicago, obwohl jede
        # Quelle für sich stimmig war.
        if not punkt_passt_zum_land(f.lat, f.lon, f.land):
            f.lat = f.lon = None

    festivals.sort(key=_reihenfolge)
    _kennungen_eindeutig(festivals)
    return festivals


def _kennungen_eindeutig(festivals: list[Festival]) -> None:
    """Jedem Festival seine eigene Kennung.

    Bo-Mit-Rock im März und im September, Edgefest in Kanada und in
    Neuseeland: Name, Jahr und Ort sind gleich, Preisgeschichte und Neuzugänge
    gehören trotzdem getrennt. Der früheste Eintrag behält die bisherige
    Kennung — so wird kein schon bekanntes Fest über Nacht „neu" —, die übrigen
    bekommen ihr Land oder, im selben Land, ihren Termin dazu.
    """
    gruppen: dict[str, list[Festival]] = {}
    for f in festivals:
        gruppen.setdefault(f.kennung, []).append(f)
    vergeben = set(gruppen)
    for gruppe in gruppen.values():
        if len(gruppe) < 2:
            continue
        erster, *rest = sorted(gruppe, key=lambda f: (f.von or date.max, f.land, f.name))
        for f in rest:
            zusatz = (f.land if f.land != erster.land
                      else f.von.isoformat() if f.von else f.land) or "2"
            f.zusatz = zusatz
            n = 2
            while f.kennung in vergeben:
                f.zusatz, n = f"{zusatz}-{n}", n + 1
            vergeben.add(f.kennung)


def _reihenfolge(f: Festival):
    """Chronologisch, bei gleichem Termin alphabetisch.

    Das Jahr kann vom Termin abweichen: Verschmilzt ein terminloser Eintrag mit
    einem datierten, bringt er sein leeres Jahr mit. Dann zählt der Termin.
    """
    jahr = f.jahr or (str(f.von.year) if f.von else "") or "9999"
    monat = f"{f.von.month:02d}" if f.von else "99"
    tag = f"{f.von.day:02d}" if f.von else "99"
    return (jahr, monat, tag, f.name.casefold())


def vorbereiten(funde: list[Fund]) -> tuple[dict[str, str], dict, list[str], Kuerzel]:
    """Bandnamen ordnen, bevor zusammengeführt wird.

    Gibt die verbindlichen Schreibweisen zurück, die Statistik dazu, die
    abgeschalteten Kürzel und die Kürzeltabelle dieses Laufs.
    """
    kuerzel = Kuerzel()
    doppelt = bandnamen.kollisionen(funde, kuerzel)
    namen, statistik = bandnamen.verzeichnis(funde, kuerzel)
    return namen, statistik, doppelt, kuerzel
