"""Beim Zusammenführen darf nichts verschwinden.

Acht Stufen legen Funde zusammen. Jede davon kann zu viel zusammenlegen — dann
fehlt ein Festival in der Liste, und niemand vermisst es, weil ja etwas
Ähnliches dasteht. Die Gegenprobe ist einfach: Jede Quelladresse, die
hineingeht, muss hinterher bei genau einem Festival stehen.
"""

import pytest

from festivalfinder.bund.lauf import vorbereiten, zusammenfuehren
from festivalfinder.kern.fund import fund
from festivalfinder.kern.zeit import aus_deutsch


def f(quelle, name, nr=0, *, von=None, bis=None, stadt="", land="DE", lineup=()):
    return fund(quelle, f"https://{quelle}.example/{nr}", name,
                von=aus_deutsch(von), bis=aus_deutsch(bis),
                stadt=stadt, land=land, lineup=list(lineup))


def bund(funde):
    liste = list(funde)
    namen, _s, _d, kuerzel = vorbereiten(liste)
    return zusammenfuehren(liste, namen, kuerzel)


def adressen(festivals):
    return [u for x in festivals for u in x.quellen.values()]


def test_jede_adresse_kommt_genau_einmal_an():
    funde = [
        f("festivalticker", "Wacken Open Air", 1, von="30.07.2026", stadt="Wacken"),
        f("festivalsunited", "Wacken Open Air", 2, von="30.07.2026", stadt="Wacken"),
        f("festivalalarm", "Sommerfest", 3, von="01.06.2026", stadt="Kiel"),
        f("wannafest", "Winterfest", 4, stadt="Kiel"),
    ]
    gefunden = adressen(bund(funde))
    assert sorted(gefunden) == sorted(x.url for x in funde)
    assert len(gefunden) == len(set(gefunden)), "eine Adresse steht doppelt"


@pytest.mark.parametrize("luecke", [
    {"name": "x"},                                   # sehr kurzer Name
    {"stadt": ""},                                   # ohne Ort
    {"von": None},                                   # ohne Termin
    {"stadt": "", "von": None},                      # weder noch
    {"land": ""},                                    # ohne Land
])
def test_auch_lueckenhafte_funde_gehen_nicht_verloren(luecke):
    grund = {"name": "Testival", "von": "01.06.2026", "stadt": "Kiel", "land": "DE"}
    einer = {**grund, **luecke}
    funde = [f("festivalticker", einer.pop("name"), 1, **einer),
             f("festapp", "Anderes Fest", 2, von="05.08.2026", stadt="Bonn")]
    assert sorted(adressen(bund(funde))) == sorted(x.url for x in funde)


def test_zwei_gleiche_funde_derselben_quelle_bleiben_eine_adresse():
    """Dieselbe Seite zweimal gelesen darf nicht zwei Festivals ergeben."""
    a = f("festivalticker", "Testival", 1, von="01.06.2026", stadt="Kiel")
    ergebnis = bund([a, a])
    assert len(ergebnis) == 1
    assert len(ergebnis[0].quellen) == 1


def test_ohne_funde_kein_ergebnis():
    assert bund([]) == []


def test_lineups_gehen_beim_verschmelzen_nicht_verloren():
    a = f("festivalticker", "Testival", 1, von="01.06.2026", stadt="Kiel",
          lineup=["Powerwolf", "Heaven Shall Burn"])
    b = f("festivalsunited", "Testival", 2, von="01.06.2026", stadt="Kiel",
          lineup=["Powerwolf", "Amon Amarth"])
    [ergebnis] = bund([a, b])
    assert set(ergebnis.lineup) == {"Powerwolf", "Heaven Shall Burn", "Amon Amarth"}


def test_der_bestand_ist_chronologisch():
    funde = [
        f("festivalticker", "Spaeter", 1, von="01.09.2026", stadt="Kiel"),
        f("festivalticker", "Frueher", 2, von="01.06.2026", stadt="Bonn"),
        f("festivalticker", "Ohne Termin", 3, stadt="Mainz"),
    ]
    namen = [x.name for x in bund(funde)]
    assert namen == ["Frueher", "Spaeter", "Ohne Termin"]
