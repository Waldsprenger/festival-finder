"""Preise lesen, prüfen, umrechnen.

Vorher gab es zwei Stellen dafür — eine im Sammler, eine im Seitenbau, jede
mit eigener Währungsliste. Diese Tests gelten jetzt für beide, weil es nur
noch eine gibt.
"""

import pytest

from festivalfinder.kern.geld import (KURSE, WAEHRUNG_LAND, betrag, in_euro,
                                      ist_preis)


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


class TestIstPreis:
    def test_eine_zahl_genuegt(self):
        assert ist_preis("ab 85,00 EUR") == "ab 85,00 EUR"

    def test_worte_ohne_zahl_nur_wenn_sie_gratis_meinen(self):
        assert ist_preis("Eintritt frei") == "Eintritt frei"
        # Auf einer Seite stand „Preis: Pop Punk" — das Genre war ins
        # Preisfeld gerutscht.
        assert ist_preis("Pop Punk") == ""

    def test_leergebliebenes_feld(self):
        """Eine Ziffer allein genügt nicht: „ab EUR ,00" ist kein Preis."""
        assert ist_preis("ab EUR ,00") == ""


class TestInEuro:
    @pytest.mark.parametrize("text,erwartet", [
        ("ab 85,00 EUR", 85.0),
        ("351 €", 351.0),
        ("EUR 49,50", 49.5),
        ("19,80 - 27,50 €", 19.8),          # die Spanne beginnt unten
        ("ab CHF 100", 106.0),              # umgerechnet
        ("Eintritt frei", 0.0),
        ("kostenlos bis 39 EUR je Event", 0.0),
    ])
    def test_guenstigster_einstieg(self, text, erwartet):
        assert in_euro(text) == pytest.approx(erwartet)

    def test_nur_zahlen_an_einer_waehrung_zaehlen(self):
        """Sonst würde „VVK 199 EUR (Stufe 2)" als 2 EUR gelesen."""
        assert in_euro("VVK 199 EUR (Stufe 2)") == 199.0

    def test_ohne_waehrung_zaehlt_die_erste_zahl(self):
        """Die Nachsätze nennen Preisstufen, nicht den günstigsten Preis."""
        assert in_euro("VVK 42,95 (Stufe 2)") == 42.95

    def test_ein_nachsatz_hebt_den_preis_nicht_auf(self):
        assert in_euro("VVK 45-172 EUR (Pay what you can)") == 45.0

    @pytest.mark.parametrize("text", ["", "Pop Punk", None])
    def test_kein_preis(self, text):
        assert in_euro(text) is None

    def test_unplausibles_faellt_weg(self):
        assert in_euro("999999 EUR") is None


class TestWaehrungen:
    def test_jede_zugeordnete_waehrung_hat_einen_kurs(self):
        """Eine Grenze in einer Währung ohne Kurs wäre eine Zahl ohne
        Bedeutung — die Seite dürfte sie nicht anbieten."""
        ohne = {w for w in WAEHRUNG_LAND.values() if w not in KURSE}
        assert not ohne, f"ohne Kurs: {sorted(ohne)}"

    def test_euro_ist_die_bezugsgroesse(self):
        assert KURSE["EUR"] == 1.0
