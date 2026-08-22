"""Namen und Schlüssel.

Jeder Fall hier stand einmal falsch in den Daten — die Tests halten fest,
warum die Regel so aussieht, wie sie aussieht.
"""

import pytest

from festivalfinder.kern.text import (Kuerzel, band_key, canonical_band,
                                      city_key, clean, festival_key, fold,
                                      genres_vereinen, plz_und_stadt,
                                      besucherzahl, valid_band)


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

    def test_andere_schriften_behalten_ihren_namen(self):
        # „[^a-z0-9]" ließ von kyrillischen Namen nichts übrig: Der Act galt
        # als namenlos und fiel aus jedem Lineup.
        assert fold("Мумий Тролль") == "мумии тролль"
        assert fold("Ελλάδα") == "ελλαδα"

    def test_griechischer_name_faellt_nicht_auf_band_zusammen(self):
        assert fold("Ελλάδα Band") != fold("Καλημέρα Band")

    @pytest.mark.parametrize("name,erwartet", [
        ("AC/DC", "ac dc"), ("Sigur Rós", "sigur ros"),
        ("Małgorzata", "malgorzata"), ("!!!", ""),
        ("Motörhead", "motorhead"), ("P!nk", "p nk"),
    ])
    def test_lateinische_namen_bleiben_wie_sie_waren(self, name, erwartet):
        assert fold(name) == erwartet

    def test_die_regeln_stehen_in_der_datei(self):
        """Sie reisen mit in die Webseite; ohne sie liefen beide auseinander."""
        from festivalfinder.kern.text import REGELN
        assert REGELN["verbinder"] and REGELN["artikel"] and REGELN["sonderzeichen"]


class TestEntschluesseln:
    """HTML-Ersatzschreibweisen aus Datenblättern.

    Im Fließtext nimmt der Parser sie einem ab, im JSON-Datenblatt nicht:
    „Shaq&#8217;s Fun House" und „Larry &amp; Joe" standen so auf 236 Karten.
    """

    @pytest.mark.parametrize("roh,erwartet", [
        ("Shaq&#8217;s Fun House", "Shaq’s Fun House"),
        ("Larry &amp; Joe", "Larry & Joe"),
        ("Moon Palace Golf &#038; Spa", "Moon Palace Golf & Spa"),
        ("VVV &#91;Trippin&#39;you&#93;", "VVV [Trippin'you]"),
        ("ganz normal", "ganz normal"),
        ("", ""),
    ])
    def test_entschluesselt(self, roh, erwartet):
        assert clean(roh) == erwartet

    def test_bandnamen_finden_dadurch_zusammen(self):
        assert band_key("Larry &amp; Joe") == band_key("Larry & Joe")

    def test_glaettet_umbrueche(self):
        assert clean("  Rock \n  am   Ring ") == "Rock am Ring"
        assert clean(None) == ""


class TestBandKey:
    def test_getrennt_und_zusammen_ist_dieselbe_band(self):
        assert band_key("1000 Mods") == band_key("1000mods")

    def test_kurze_namen_bleiben_getrennt(self):
        # „B-One" und „Bone" sind zwei Bands; darum die Mindestlänge
        assert band_key("B-One") != band_key("Bone")

    def test_kuerzel_loest_sich_auf(self):
        """Die Tabelle ist ein Objekt — der Test braucht kein Modul zu ändern
        und muss danach nichts zurücknehmen."""
        kuerzel = Kuerzel({"TBS": "The Butcher Sisters"})
        assert kuerzel.band_key("TBS") == kuerzel.band_key("The Butcher Sisters")

    def test_eine_eigene_tabelle_faerbt_nicht_ab(self):
        Kuerzel({"XYZ": "Irgendeine Band"})
        assert band_key("XYZ") != band_key("Irgendeine Band")


class TestFestivalKey:
    def test_jahr_und_gattungswort_fallen_weg(self):
        assert festival_key("Wacken Open Air 2026") == "wacken"
        assert festival_key("Reload Festival") == "reload"

    def test_angehaengtes_gattungswort_faellt_auch_weg(self):
        # festivalticker schreibt „Reloadfestival" in einem Wort
        assert festival_key("Reloadfestival") == festival_key("Reload Festival")

    def test_kurzer_rumpf_bleibt_stehen(self):
        # aus „Festa" darf kein leerer Schlüssel werden
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
        "Мумий Тролль",
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


class TestGenresVereinen:
    def test_sammelt_statt_zu_ersetzen(self):
        assert genres_vereinen("Rock, Metal", "Punk") == "Rock, Metal, Punk"

    def test_doppelte_fallen_weg_ohne_ruecksicht_auf_grossschreibung(self):
        assert genres_vereinen("Rock", "rock, Punk") == "Rock, Punk"

    def test_eine_quelle_die_sich_selbst_wiederholt(self):
        assert genres_vereinen("Ska, Elektro, ska") == "Ska, Elektro"

    def test_leere_angaben_stoeren_nicht(self):
        assert genres_vereinen("", "Rock", "") == "Rock"


class TestPlzUndStadt:
    def test_postleitzahl_vor_dem_ortsnamen(self):
        assert plz_und_stadt("104 45 Athen", "") == ("Athen", "10445")
        assert plz_und_stadt("170 00 Prague", "") == ("Prague", "17000")

    def test_vorhandene_postleitzahl_gewinnt(self):
        assert plz_und_stadt("55116 Mainz", "55118") == ("Mainz", "55118")

    def test_ohne_postleitzahl_bleibt_alles(self):
        assert plz_und_stadt("Kiel", "24103") == ("Kiel", "24103")


class TestBesucherzahl:
    def test_eine_zahl_wird_uebernommen(self):
        assert besucherzahl("ca. 18.000") == "18000"

    def test_mehrere_zahlen_ergeben_nichts(self):
        """Früher blieben alle Ziffern übrig — auf manchen Seiten ergab das
        Zahlen mit 66 Stellen, zusammengeklebt aus Datumsangaben."""
        assert besucherzahl("2026 Besucher: 18.000 am 24.07.") == ""

    @pytest.mark.parametrize("roh", ["", "viele", "3", "99999999"])
    def test_unplausibles_faellt_weg(self, roh):
        assert besucherzahl(roh) == ""
