"""Der Trichter, durch den jede Quelle geht.

Was hier steht, gilt für alle zwölf — und nirgends sonst. Dazu die Zusage, die
ein eingefrorener Datensatz gibt: Ein Tippfehler im Feldnamen fällt sofort auf,
und nachträglich ändern lässt sich nichts.
"""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from festivalfinder.kern.festival import Festival
from festivalfinder.kern.fund import Fund, fund


class TestTrichter:
    def test_grundform(self):
        f = fund("festivalticker", "https://x/y", "Testival",
                 von=date(2026, 6, 1), stadt="Kiel", land="DE")
        assert f.bis == date(2026, 6, 1)        # ein Tag heißt von = bis
        assert f.jahr == "2026"
        assert f.lineup == ()

    def test_termin_schlaegt_jahresangabe(self):
        """„Sommer im Park Gera 2027" mit Termin im August 2026: Der Termin ist
        die genauere Angabe."""
        f = fund("festivalhopper", "u", "Sommer im Park",
                 von=date(2026, 8, 27), jahr="2027")
        assert f.jahr == "2026"

    def test_jahr_ohne_termin_bleibt(self):
        assert fund("festivalsunited", "u", "X", jahr="2027").jahr == "2027"

    def test_land_wird_zum_kuerzel(self):
        assert fund("festapp", "u", "X", land="Deutschland").land == "DE"

    def test_besucherzahl_wird_zur_zahl(self):
        assert fund("festivalticker", "u", "X", besucher="ca. 18.000").besucher == "18000"

    def test_preis_ohne_preis_faellt_weg(self):
        assert fund("festivalticker", "u", "X", preis="Pop Punk").preis == ""

    def test_ein_act_steht_einmal_im_lineup(self):
        """jambase nennt Acts zweimal, wenn sie an mehreren Tagen spielen."""
        f = fund("jambase", "u", "X", lineup=["A", "B", "A"])
        assert f.lineup == ("A", "B")

    def test_postleitzahl_aus_dem_ortsfeld(self):
        f = fund("festapp", "u", "X", stadt="104 45 Athen", land="GR")
        assert (f.stadt, f.plz) == ("Athen", "10445")

    def test_falsche_koordinate_wird_verworfen(self):
        f = fund("festivalsunited", "u", "Budapest Park",
                 stadt="Budapest", land="HU", lat=52.51, lon=13.45)
        assert (f.lat, f.lon) == (None, None)

    def test_richtige_koordinate_bleibt(self):
        f = fund("festivalsunited", "u", "Budapest Park",
                 stadt="Budapest", land="HU", lat=47.47, lon=19.09)
        assert (f.lat, f.lon) == (47.47, 19.09)

    def test_nullpunkt_ist_keine_koordinate(self):
        f = fund("festivalabroad", "u", "X", land="DE", lat=0.0, lon=0.0)
        assert (f.lat, f.lon) == (None, None)


class TestEingefroren:
    def test_ein_fund_laesst_sich_nicht_nachtraeglich_aendern(self):
        f = fund("festivalticker", "u", "X")
        with pytest.raises(FrozenInstanceError):
            f.name = "Y"

    def test_ein_tippfehler_im_feldnamen_faellt_sofort_auf(self):
        """Beim Wörterbuch kam bei `.get()` still None zurück."""
        f = fund("festivalticker", "u", "X")
        with pytest.raises(AttributeError):
            _ = f.stdat

    def test_ein_unbekanntes_feld_laesst_sich_nicht_anlegen(self):
        with pytest.raises(TypeError):
            Fund(quelle="x", url="u", name="n", stdat="Kiel")


class TestFestival:
    def test_aus_einem_fund(self):
        f = fund("festivalticker", "u", "X", von=date(2026, 6, 1), stadt="Kiel",
                 land="DE")
        fest = Festival.aus_fund(f, rang=0)
        assert fest.name == "X" and fest.location == "Kiel, DE"

    def test_lineup_kommt_alphabetisch(self):
        fest = Festival(name="X")
        fest.bands = {"b": "Beatles", "a": "ABBA"}
        assert fest.lineup == ["ABBA", "Beatles"]

    def test_die_ausgelieferte_form_ist_eine_zusage(self):
        """data/festivals.json wird mitveröffentlicht — Namen und Reihenfolge
        der Felder bleiben, auch wenn intern anders gerechnet wird."""
        fest = Festival(name="X", jahr="2026", von=date(2026, 6, 1),
                        bis=date(2026, 6, 2), stadt="Kiel", land="DE")
        d = fest.als_json()
        assert list(d) == [
            "name", "year", "date_from", "date_to", "city", "country", "venue",
            "plz", "lat", "lon", "location", "price", "website", "genre",
            "visitors", "note", "cancelled", "sources", "price_start",
            "price_start_seit", "lineup", "lineup_count"]
        assert d["date_from"] == "01.06.2026"
        assert d["lineup_count"] == 0

    def test_ein_tippfehler_faellt_auch_hier_auf(self):
        fest = Festival(name="X")
        with pytest.raises(AttributeError):
            fest.stdat = "Kiel"
