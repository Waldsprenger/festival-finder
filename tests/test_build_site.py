"""Preise, Verortung und die Auslieferung als JS-Datei."""

import json

import pytest

from build_site import (Verorter, als_javascript, frueheste_monatsgrenze, iso,
                        laender_rahmen, platzhalter, preis_eur)


class TestPreisEur:
    @pytest.mark.parametrize("text,erwartet", [
        ("ab 85,00 EUR", 85.0),
        ("ab € 85,00", 85.0),
        ("VVK 19,80 - 27,50 €", 19.8),          # Spannen liefern den unteren Wert
        ("Tagesticket 45 €, Kombi 120 €", 45.0),
        ("ab CHF 100", 106.0),                  # umgerechnet
        ("kostenlos", 0.0),
        ("Eintritt frei", 0.0),
        ("Spende erwünscht", 0.0),
        ("VVK 42,95 (Stufe 2)", 42.95),         # ohne Währung zählt die erste Zahl
    ])
    def test_preise_aus_freitext(self, text, erwartet):
        assert preis_eur(text) == pytest.approx(erwartet, abs=0.51)

    def test_nachsatz_hebt_den_preis_nicht_auf(self):
        # "Pay what you can" hinter einer Preisangabe macht sie nicht kostenlos
        assert preis_eur("VVK 45-172 € (Pay what you can)") == 45.0

    def test_gratis_vor_dem_preis_zaehlt(self):
        assert preis_eur("Kostenlos bis 39 EUR je Event") == 0.0

    def test_stufenangabe_wird_nicht_zum_preis(self):
        # "199 EUR (Stufe 2)" darf nicht als 2 EUR gelesen werden
        assert preis_eur("VVK 199 EUR (Stufe 2)") == 199.0

    @pytest.mark.parametrize("text", ["", "auf Anfrage", "Pop Punk"])
    def test_kein_preis(self, text):
        assert preis_eur(text) is None


class TestAlsJavascript:
    def rueckwaerts(self, datei_inhalt):
        """Wie der Browser: erst die JS-Zeichenkette, dann das JSON."""
        inhalt = datei_inhalt[datei_inhalt.index("('") + 2: datei_inhalt.rindex("')")]
        js = (inhalt.replace("\\/", "/").replace("\\'", "'")
                    .replace("\\u2028", "\u2028").replace("\\u2029", "\u2029")
                    .replace("\\\\", "\\"))
        return json.loads(js)

    def test_gewoehnliche_daten(self):
        daten = {"bands": ["Powerwolf", "AC/DC"], "n": 5, "leer": None}
        assert self.rueckwaerts(als_javascript(daten)) == daten

    def test_apostroph_und_anfuehrungszeichen(self):
        daten = {"bands": ["Manfred Mann's Earth Band", 'Zeichen: "Rock"']}
        assert self.rueckwaerts(als_javascript(daten)) == daten

    def test_rueckstrich_bleibt_erhalten(self):
        daten = {"name": "AC\\DC", "pfad": "C:\\Temp"}
        assert self.rueckwaerts(als_javascript(daten)) == daten

    def test_script_ende_wird_entschaerft(self):
        # In der gebündelten Einzelseite steht alles in einem <script>
        text = als_javascript({"name": "</script><b>"})
        assert "</script>" not in text
        assert self.rueckwaerts(text) == {"name": "</script><b>"}

    def test_zeilentrenner(self):
        daten = {"name": "vor\u2028nach"}
        assert self.rueckwaerts(als_javascript(daten)) == daten

    def test_beginnt_mit_json_parse(self):
        assert als_javascript({}).startswith("window.DATA = JSON.parse('")


class TestVerorter:
    def festival(self, **rest):
        grund = {"name": "Testival", "city": "", "country": "DE", "plz": "",
                 "lat": None, "lon": None, "venue": ""}
        return {**grund, **rest}

    def test_postleitzahl_hat_vorrang(self):
        verortung = {"plz": [["12345", 50.0, 8.0, "DE"]],
                     "orte": [["Musterstadt", 51.0, 9.0, "DE"]]}
        geo = {"Musterstadt|DE": {"lat": 52.0, "lon": 10.0}}
        v = Verorter([], geo, verortung, [], [])
        lat, lon, land = v(self.festival(city="Musterstadt", plz="12345"))
        assert (lat, lon, land) == (50.0, 8.0, "DE")
        assert v.aus_plz == 1

    def test_dann_der_geo_cache(self):
        verortung = {"plz": [], "orte": [["Musterstadt", 51.0, 9.0, "DE"]]}
        geo = {"Musterstadt|DE": {"lat": 52.0, "lon": 10.0}}
        v = Verorter([], geo, verortung, [], [])
        assert v(self.festival(city="Musterstadt"))[:2] == (52.0, 10.0)

    def test_dann_das_ortsverzeichnis(self):
        verortung = {"plz": [], "orte": [["Musterstadt", 51.0, 9.0, "DE"]]}
        v = Verorter([], {}, verortung, [], [])
        assert v(self.festival(city="Musterstadt"))[:2] == (51.0, 9.0)
        assert v.aus_ort == 1

    def test_ortsverzeichnis_kennt_die_umschrift(self):
        verortung = {"plz": [], "orte": [["Zürich", 47.4, 8.5, "CH"]]}
        v = Verorter([], {}, verortung, [], [])
        assert v(self.festival(city="Zurich", country="CH"))[:2] == (47.4, 8.5)

    def test_quellpunkt_nur_im_richtigen_land(self):
        verortung = {"plz": [], "orte": [["Lugano", 46.0, 8.95, "CH"],
                                         ["Zürich", 47.4, 8.5, "CH"]]}
        v = Verorter([], {}, verortung, [], [])
        # Punkt in Buenos Aires für ein Schweizer Festival: verworfen
        weit = self.festival(city="Unbekannt", country="CH", lat=-34.6, lon=-58.4)
        assert v(weit)[:2] == (None, None)
        # Punkt in der Schweiz: übernommen
        nah = self.festival(city="Unbekannt", country="CH", lat=46.5, lon=8.6)
        assert v(nah)[:2] == (46.5, 8.6)

    def test_eindeutige_postleitzahl_ergaenzt_das_land(self):
        verortung = {"plz": [["1010", 48.2, 16.3, "AT"]], "orte": []}
        v = Verorter([], {}, verortung, [], [])
        assert v(self.festival(plz="1010", country=""))[2] == "AT"

    def test_mehrdeutige_postleitzahl_ohne_land_zaehlt_nicht(self):
        verortung = {"plz": [["1010", 48.2, 16.3, "AT"], ["1010", 47.0, 8.0, "CH"]],
                     "orte": []}
        v = Verorter([], {}, verortung, [], [])
        assert v(self.festival(plz="1010", country=""))[:2] == (None, None)


class TestHilfen:
    def test_iso_datum(self):
        assert iso("09.05.2026") == "2026-05-09"
        assert iso("") == ""

    def test_frueheste_monatsgrenze(self):
        zeilen = [["A", "2026-05-16"], ["B", "2026-08-01"], ["C", ""]]
        assert frueheste_monatsgrenze(zeilen) == "2026-05-01"

    def test_laender_rahmen(self):
        orte = [["A", 47.0, 6.0, "CH"], ["B", 48.0, 10.0, "CH"], ["C", 52.0, 13.0, "DE"]]
        assert laender_rahmen(orte)["CH"] == (47.0, 48.0, 6.0, 10.0)

    def test_platzhalter_erkennt_sammelpunkte(self):
        # Dieselbe Koordinate für drei verschiedene Orte ist ein Platzhalter
        fest = [{"lat": 51.5, "lon": 10.5, "city": ort} for ort in ("A", "B", "C")]
        fest.append({"lat": 48.0, "lon": 11.0, "city": "München"})
        assert platzhalter(fest) == {(51.5, 10.5)}
