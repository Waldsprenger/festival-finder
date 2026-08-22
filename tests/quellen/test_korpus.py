"""Die Leser an echten Seiten, nicht an handgeschriebenen Schnipseln.

Die übrigen Tests halten fest, was gemeint ist. Diese hier halten fest, was die
Quellen tatsächlich schicken — dort saßen die letzten Fehler: eine Bandliste,
die Menüpunkte mitzählte, ein Preis mit zwei Punkten, eine Spielstätte namens
„Tickets Ticket".

In `tests/seiten/` liegen je Quelle zwei eingefrorene Seiten (gepackt, zusammen
0,5 MB). Sie ändern sich nicht mehr; ändert sich das Ergebnis, war es der Code.
"""

import gzip
import json
import re
from pathlib import Path

import pytest

from festivalfinder.kern.geld import betrag
from festivalfinder.kern.orte import ist_land
from festivalfinder.kern.text import KNOPFBESCHRIFTUNG, valid_band
from festivalfinder.quellen import alle

from ..conftest import SEITEN, StillerAbrufer

VERZEICHNIS = json.loads((SEITEN / "verzeichnis.json").read_text(encoding="utf-8"))
LESER = {q.name: q for q in alle()}

#: Zeichen, die man nicht sieht und die trotzdem jeden Vergleich verderben
UNSICHTBAR = re.compile("[\xa0​-‏  ﻿\x00-\x08\x0b-\x1f]")


def lesen(datei: str):
    eintrag = VERZEICHNIS[datei]
    quelle = LESER[eintrag["quelle"]]
    html = gzip.decompress((SEITEN / datei).read_bytes()).decode("utf-8", "replace")
    return quelle.lesen(StillerAbrufer(), eintrag["url"], html)


@pytest.fixture(scope="module", params=sorted(VERZEICHNIS))
def gelesen(request):
    f = lesen(request.param)
    assert f is not None, f"{request.param}: keine Daten aus einer echten Seite"
    return f


def test_jede_quelle_hat_eine_echte_probe():
    """Quellen mit Seiten liegen als HTML bei, Sammelquellen als ganze Datei."""
    from festivalfinder.quellen.basis import Quelle
    abgedeckt = {e["quelle"] for e in VERZEICHNIS.values()}
    mit_datei = {n for n, q in LESER.items()
                 if type(q).sammeldatei is not Quelle.sammeldatei}
    assert abgedeckt | mit_datei == set(LESER), \
        f"ohne echte Probe: {set(LESER) - abgedeckt - mit_datei}"
    assert (SEITEN / "festivalnetworks_feed.json.gz").exists()


class TestJederFund:
    def test_name_ist_sauber(self, gelesen):
        name = gelesen.name
        assert name.strip() == name and name
        assert not re.match(r"^\d+\.\s", name), "Zählnummer im Namen"
        assert not re.search(r"\b(19|20)\d{2}$", name), "Jahr im Namen"
        assert not UNSICHTBAR.search(name), "unsichtbares Zeichen im Namen"

    def test_land_ist_ein_land(self, gelesen):
        assert not gelesen.land or ist_land(gelesen.land)

    def test_termin_ist_ein_datum_oder_keiner(self, gelesen):
        if gelesen.von and gelesen.bis:
            assert gelesen.bis >= gelesen.von, "Ende vor Anfang"

    def test_jahr_passt_zum_termin(self, gelesen):
        if gelesen.von:
            assert gelesen.jahr == str(gelesen.von.year)

    def test_preis_nennt_eine_zahl_oder_freien_eintritt(self, gelesen):
        if gelesen.preis:
            assert re.search(r"[1-9]", gelesen.preis) or \
                re.search(r"(?i)frei|kostenlos|gratis", gelesen.preis)

    def test_besucherzahl_ist_plausibel(self, gelesen):
        if gelesen.besucher:
            assert gelesen.besucher.isdigit()
            assert 10 <= int(gelesen.besucher) <= 5_000_000

    def test_spielstaette_ist_keine_knopfbeschriftung(self, gelesen):
        assert not gelesen.ort or not KNOPFBESCHRIFTUNG.match(gelesen.ort)

    def test_koordinate_ist_vollstaendig_oder_gar_nicht(self, gelesen):
        assert (gelesen.lat is None) == (gelesen.lon is None)

    def test_jeder_act_ist_ein_bandname(self, gelesen):
        for act in gelesen.lineup:
            assert valid_band(act), f"kein Bandname: {act!r}"

    def test_kein_act_steht_zweimal(self, gelesen):
        assert len(set(gelesen.lineup)) == len(gelesen.lineup)

    def test_webseite_ist_eine_adresse(self, gelesen):
        assert not gelesen.webseite or gelesen.webseite.startswith("http")


class TestSammeldatei:
    def test_festivalnetworks_liest_seine_datei(self):
        roh = gzip.decompress(
            (SEITEN / "festivalnetworks_feed.json.gz").read_bytes()).decode("utf-8")
        netz = StillerAbrufer({"https://festivalnetworks.com/data-api.php?r=festivals": roh})
        funde = LESER["festivalnetworks"].sammeldatei(netz, 2000)
        assert len(funde) > 100
        assert all(f.quelle == "festivalnetworks" and f.name for f in funde)
        assert any(f.von for f in funde)

    def test_eine_kaputte_datei_bringt_den_lauf_nicht_um(self):
        netz = StillerAbrufer({"https://festivalnetworks.com/data-api.php?r=festivals":
                               "kein JSON"})
        assert LESER["festivalnetworks"].sammeldatei(netz, 2000) == []


def test_preise_der_echten_seiten_sind_lesbar():
    """„8.900.00" hat float() einmal eine Ausnahme entlockt — und der Aufrufer
    verwarf daraufhin das ganze Festival."""
    for datei in sorted(VERZEICHNIS):
        f = lesen(datei)
        if f and f.preis and re.search(r"\d", f.preis):
            assert betrag(f.preis) is not None or "frei" in f.preis.lower()
