"""Beim Zusammenführen darf nichts verschwinden.

Sieben Stufen legen Funde zusammen. Jede davon kann zu viel zusammenlegen —
dann fehlt ein Festival in der Liste, und niemand vermisst es, weil ja etwas
Ähnliches dasteht. Die Gegenprobe ist einfach: Jede Quelladresse, die
hineingeht, muss hinterher bei genau einem Festival stehen.
"""

import pytest
from quellen import datensatz
from zusammenfuehren import band_registry, zusammenfuehren


def fund(quelle, name, nr=0, *, von="", bis="", stadt="", land="DE", lineup=()):
    return datensatz(quelle, f"https://{quelle}.example/{nr}", name,
                     date_from=von, date_to=bis, city=stadt, country=land,
                     lineup=list(lineup))


def zusammen(funde):
    return zusammenfuehren(list(funde), band_registry(list(funde))[0])


def adressen(festivals):
    heraus = []
    for f in festivals:
        heraus += list(f["sources"].values())
    return heraus


def test_jede_adresse_kommt_genau_einmal_an():
    funde = [
        fund("festivalticker", "Wacken Open Air", 1, von="30.07.2026", stadt="Wacken"),
        fund("festivalsunited", "Wacken Open Air", 2, von="30.07.2026", stadt="Wacken"),
        fund("festivalalarm", "Sommerfest", 3, von="01.06.2026", stadt="Kiel"),
        fund("wannafest", "Winterfest", 4, stadt="Kiel"),
    ]
    ergebnis = zusammen(funde)
    gefunden = adressen(ergebnis)
    assert sorted(gefunden) == sorted(f["source_url"] for f in funde)
    assert len(gefunden) == len(set(gefunden)), "eine Adresse steht doppelt"


@pytest.mark.parametrize("luecke", [
    {"name": "x"},                                   # sehr kurzer Name
    {"stadt": ""},                                   # ohne Ort
    {"von": ""},                                     # ohne Termin
    {"stadt": "", "von": ""},                        # weder noch
    {"land": ""},                                    # ohne Land
])
def test_auch_lueckenhafte_funde_gehen_nicht_verloren(luecke):
    grund = {"name": "Testival", "von": "01.06.2026", "stadt": "Kiel", "land": "DE"}
    einer = {**grund, **luecke}
    funde = [fund("festivalticker", einer.pop("name"), 1, **einer),
             fund("festapp", "Anderes Fest", 2, von="05.08.2026", stadt="Bonn")]
    ergebnis = zusammen(funde)
    assert sorted(adressen(ergebnis)) == sorted(f["source_url"] for f in funde)


def test_zwei_gleiche_funde_derselben_quelle_bleiben_eine_adresse():
    # Dieselbe Seite zweimal gelesen darf nicht zwei Festivals ergeben
    a = fund("festivalticker", "Testival", 1, von="01.06.2026", stadt="Kiel")
    ergebnis = zusammen([a, dict(a)])
    assert len(ergebnis) == 1
    assert len(ergebnis[0]["sources"]) == 1


def test_ohne_funde_kein_ergebnis():
    assert zusammen([]) == []


def test_lineups_gehen_beim_verschmelzen_nicht_verloren():
    a = fund("festivalticker", "Testival", 1, von="01.06.2026", stadt="Kiel",
             lineup=["Powerwolf", "Heaven Shall Burn"])
    b = fund("festivalsunited", "Testival", 2, von="01.06.2026", stadt="Kiel",
             lineup=["Powerwolf", "Amon Amarth"])
    [ergebnis] = zusammen([a, b])
    assert set(ergebnis["lineup"]) == {"Powerwolf", "Heaven Shall Burn", "Amon Amarth"}
    assert ergebnis["lineup_count"] == len(ergebnis["lineup"])
