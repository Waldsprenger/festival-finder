"""Termine: von jeder Schreibweise der Quellen zu einem `date`.

Vorher waren Termine Zeichenketten. Zwei Fehler konnten dadurch nicht
auffallen: ein Datum, das es nicht gibt, und ein leerer Monatsname, der zu
Januar wurde. Beide fängt die Umrechnung jetzt ab.
"""

from datetime import date

import pytest

from festivalfinder.kern import zeit


class TestLesen:
    def test_iso(self):
        assert zeit.aus_iso("2026-08-19") == date(2026, 8, 19)
        assert zeit.aus_iso("2026-08-19T18:00") == date(2026, 8, 19)
        assert zeit.aus_iso("2026-8-9") == date(2026, 8, 9)

    def test_deutsch(self):
        assert zeit.aus_deutsch("19.08.2026") == date(2026, 8, 19)
        # festivalticker schreibt schon mal ein Leerzeichen hinein
        assert zeit.aus_deutsch("26. 7.2026") == date(2026, 7, 26)

    def test_englisch_in_beiden_stellungen(self):
        assert zeit.aus_englisch("August 19, 2026") == date(2026, 8, 19)
        assert zeit.aus_englisch("19 Aug 2026") == date(2026, 8, 19)
        assert zeit.aus_englisch("Aug. 19 2026") == date(2026, 8, 19)

    def test_kurzform_von_festivalnetworks(self):
        assert zeit.aus_kurz("27-Aug-26") == date(2026, 8, 27)

    @pytest.mark.parametrize("wert", ["", None, "demnächst", "Sommer 2026"])
    def test_was_kein_datum_ist_gibt_none(self, wert):
        assert zeit.aus_iso(wert) is None
        assert zeit.aus_deutsch(wert) is None
        assert zeit.aus_englisch(wert) is None
        assert zeit.aus_kurz(wert) is None

    def test_den_31_februar_gibt_es_nicht(self):
        """Vorher entstand daraus die Zeichenkette „31.02.2026"."""
        assert zeit.aus_englisch("31 Feb 2026") is None
        assert zeit.aus_deutsch("31.02.2026") is None
        assert zeit.aus_iso("2026-02-31") is None


class TestMonatsnamen:
    def test_deutsch_und_englisch(self):
        assert zeit.monat_nummer("August") == zeit.monat_nummer("Aug") == 8
        assert zeit.monat_nummer("March") == zeit.monat_nummer("Mär") == 3
        assert zeit.monat_nummer("Dez.") == 12

    def test_ein_leerer_name_ist_kein_januar(self):
        """Der alte Vergleich über startswith() traf bei "" den ersten Eintrag."""
        assert zeit.monat_nummer("") == 0
        assert zeit.monat_nummer("xyz") == 0


class TestDarstellung:
    def test_hin_und_zurueck(self):
        tag = date(2026, 8, 19)
        assert zeit.deutsch(tag) == "19.08.2026"
        assert zeit.iso(tag) == "2026-08-19"
        assert zeit.aus_deutsch(zeit.deutsch(tag)) == tag

    def test_ohne_termin_bleibt_leer(self):
        assert zeit.deutsch(None) == zeit.iso(None) == zeit.jahr_text(None) == ""


class TestZeitraum:
    def test_ueberlappung(self):
        a0, a1 = date(2026, 8, 19), date(2026, 8, 22)
        assert zeit.ueberlappt(a0, a1, date(2026, 8, 22), date(2026, 8, 24))
        assert not zeit.ueberlappt(a0, a1, date(2026, 8, 23), date(2026, 8, 24))

    def test_ein_tag_zaehlt_als_zeitraum(self):
        tag = date(2026, 8, 19)
        assert zeit.ueberlappt(tag, None, tag, None)

    def test_ohne_beginn_kein_ueberlapp(self):
        assert not zeit.ueberlappt(None, None, date(2026, 8, 19), None)

    def test_abstand(self):
        assert zeit.abstand_tage(date(2026, 8, 19), date(2026, 8, 22)) == 3
        assert zeit.abstand_tage(date(2026, 8, 22), date(2026, 8, 19)) == 3
        assert zeit.abstand_tage(None, date(2026, 8, 19)) is None
