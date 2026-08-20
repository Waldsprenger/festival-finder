"""Namen, Schlüssel, Zahlen und Daten.

Jeder Fall hier stand einmal falsch in den Daten — die Tests halten fest,
warum die Regel so aussieht, wie sie aussieht.
"""

import pytest

from text import (band_key, betrag, canonical_band, city_key, clean, datum_de,
                  datum_englisch, festival_key, fold, genres_vereinen, tag_zahl,
                  valid_band)


class TestFold:
    def test_umlaute_und_akzente_verschwinden(self):
        assert fold("Züri West") == fold("Zuri West") == "zuri west"
        assert fold("Björk") == "bjork"

    def test_nordische_buchstaben(self):
        # NFKD zerlegt diese nicht, ohne Ersatz fielen sie ersatzlos weg
        assert fold("Sørdfest") == "sordfest"
        assert fold("Aħna") == "ahna"
        assert fold("Straße") == "strasse"

    def test_artikel_am_anfang_faellt_weg(self):
        assert fold("The Butcher Sisters") == fold("Butcher Sisters")
        assert fold("Die Toten Hosen") == fold("Toten Hosen")

    def test_und_zeichen_vereinheitlicht(self):
        assert fold("Rock & Roll") == fold("Rock and Roll") == fold("Rock + Roll")

    def test_zusatz_am_ende_faellt_weg(self):
        assert fold("Powerwolf Live") == "powerwolf"
        assert fold("Deichkind DJ Set") == "deichkind"


class TestBandKey:
    def test_getrennt_und_zusammen_ist_dieselbe_band(self):
        assert band_key("1000 Mods") == band_key("1000mods")

    def test_kurze_namen_bleiben_getrennt(self):
        # "B-One" und "Bone" sind zwei Bands; darum die Mindestlänge
        assert band_key("B-One") != band_key("Bone")

    def test_kuerzel_loest_sich_auf(self, monkeypatch):
        import text
        monkeypatch.setitem(text.ALIAS_KEY, "tbs", "The Butcher Sisters")
        assert band_key("TBS") == band_key("The Butcher Sisters")


class TestFestivalKey:
    def test_jahr_und_gattungswort_fallen_weg(self):
        assert festival_key("Wacken Open Air 2026") == "wacken"
        assert festival_key("Reload Festival") == "reload"

    def test_angehaengtes_gattungswort_faellt_auch_weg(self):
        # festivalticker schreibt "Reloadfestival" in einem Wort
        assert festival_key("Reloadfestival") == festival_key("Reload Festival")

    def test_kurzer_rumpf_bleibt_stehen(self):
        # aus "Festa" darf kein leerer Schlüssel werden
        assert festival_key("Festa") == "festa"

    def test_nie_leer(self):
        assert festival_key("Festival") != ""


class TestCityKey:
    def test_postleitzahl_faellt_weg(self):
        assert city_key("55116 Mainz") == "mainz"

    def test_umlaut_wird_zum_grundbuchstaben(self):
        assert city_key("Zürich") == city_key("Zurich")

    def test_umschrift_wird_nicht_vereinheitlicht(self):
        # Verlockend, aber falsch: Das einzige Paar im Bestand, das sich nur in
        # dieser Umschrift unterscheidet, sind zwei verschiedene Orte.
        assert city_key("Neuenkirchen") != city_key("Neunkirchen")


class TestValidBand:
    @pytest.mark.parametrize("name", [
        "Powerwolf", "K.I.Z.", "AC/DC", "1000mods", "Die Ärzte",
        "Werden Wir Uns Wiedersehen",          # Satzwörter, aber kurz genug
    ])
    def test_echte_bandnamen(self, name):
        assert valid_band(name)

    @pytest.mark.parametrize("kein_name", [
        "", "u.v.m.", "TBA", "line-up", "weitere", "-",
        "26. 7.2026", "04.07.2026 Auch der zweite Festivaltag",
        "VVK 45 EUR", "Kategorie: Rock", "Camping ist möglich",
        "Das Festival findet in diesem Jahr zum ersten Mal statt",
        "x" * 100,
    ])
    def test_bruchstuecke_fallen_durch(self, kein_name):
        assert not valid_band(kein_name)


class TestCanonicalBand:
    def test_haeufigste_schreibweise_gewinnt(self):
        assert canonical_band(["Powerwolf", "POWERWOLF", "Powerwolf"]) == "Powerwolf"

    def test_grossbuchstabe_am_anfang_schlaegt_kleinschreibung(self):
        assert canonical_band(["b.o.s.c.h.", "B.O.S.C.H."]) == "B.O.S.C.H."


class TestBetrag:
    @pytest.mark.parametrize("roh,erwartet", [
        ("1690.00", 1690.0),
        ("8.900.00", 8900.0),        # Tausenderpunkt plus Nachkommastellen
        ("1.690,00", 1690.0),
        ("85,00", 85.0),
        ("175.000.00", 175000.0),
    ])
    def test_zahlen_aus_datenblaettern(self, roh, erwartet):
        assert betrag(roh) == erwartet

    @pytest.mark.parametrize("roh", ["", "kostenlos", "abc", None])
    def test_keine_zahl(self, roh):
        assert betrag(roh) is None


class TestDatum:
    def test_iso_mit_und_ohne_fuehrende_null(self):
        assert datum_de("2026-08-09") == "09.08.2026"
        assert datum_de("2026-8-9T11:00+01:00") == "09.08.2026"

    def test_kein_datum(self):
        assert datum_de("") == datum_de(None) == datum_de("morgen") == ""

    def test_englische_schreibweisen(self):
        assert datum_englisch("August 19, 2026") == "19.08.2026"
        assert datum_englisch("19 Aug 2026") == "19.08.2026"
        assert datum_englisch("Foo 19, 2026") == ""

    def test_tag_zahl_ist_vergleichbar(self):
        assert tag_zahl("01.02.2026") < tag_zahl("28.02.2026") < tag_zahl("01.03.2026")
        assert tag_zahl("") == 0


class TestGenresVereinen:
    def test_sammelt_statt_zu_ersetzen(self):
        assert genres_vereinen("Rock, Metal", "Punk") == "Rock, Metal, Punk"

    def test_doppelte_fallen_weg_ohne_ruecksicht_auf_grossschreibung(self):
        assert genres_vereinen("Rock", "rock, Punk") == "Rock, Punk"

    def test_leere_angaben_stoeren_nicht(self):
        assert genres_vereinen("", "Rock", "") == "Rock"


def test_clean_glaettet_umbrueche():
    assert clean("  Rock \n  am   Ring ") == "Rock am Ring"
    assert clean(None) == ""
