"""Vier Ränge, in denen ein Festival zu seiner Koordinate kommt.

Die Reihenfolge ist Absicht und jede Stufe hat einen Grund: Die Postleitzahl
trifft den Zustellbereich, der Geo-Cache steht schon in den Daten, das
Ortsverzeichnis erspart eine fremde Anfrage — und die Koordinate der Quellseite
gilt nur, wenn sie überhaupt ins richtige Land zeigt.
"""

from festivalfinder.ausgabe.verorten import Verorter, laender_rahmen, platzhalter
from festivalfinder.kern.festival import Festival


def fest(**rest):
    return Festival(**{"name": "Testival", "land": "DE", **rest})


class TestRangfolge:
    def test_postleitzahl_hat_vorrang(self):
        verortung = {"plz": [["12345", 50.0, 8.0, "DE"]],
                     "orte": [["Musterstadt", 51.0, 9.0, "DE"]]}
        geo = {"Musterstadt|DE": {"lat": 52.0, "lon": 10.0}}
        v = Verorter([], geo, verortung, [], [])
        assert v(fest(stadt="Musterstadt", plz="12345")) == (50.0, 8.0, "DE")
        assert v.aus_plz == 1

    def test_dann_der_geo_cache(self):
        verortung = {"plz": [], "orte": [["Musterstadt", 51.0, 9.0, "DE"]]}
        geo = {"Musterstadt|DE": {"lat": 52.0, "lon": 10.0}}
        v = Verorter([], geo, verortung, [], [])
        assert v(fest(stadt="Musterstadt"))[:2] == (52.0, 10.0)
        assert v.aus_cache == 1

    def test_dann_das_ortsverzeichnis(self):
        verortung = {"plz": [], "orte": [["Musterstadt", 51.0, 9.0, "DE"]]}
        v = Verorter([], {}, verortung, [], [])
        assert v(fest(stadt="Musterstadt"))[:2] == (51.0, 9.0)
        assert v.aus_ort == 1

    def test_ortsverzeichnis_kennt_die_umschrift(self):
        """GeoNames schreibt „Zürich", die Quellen mal „Zurich"."""
        verortung = {"plz": [], "orte": [["Zürich", 47.4, 8.5, "CH"]]}
        v = Verorter([], {}, verortung, [], [])
        assert v(fest(stadt="Zurich", land="CH"))[:2] == (47.4, 8.5)


class TestQuellkoordinate:
    def test_nur_im_richtigen_land(self):
        verortung = {"plz": [], "orte": [["Lugano", 46.0, 8.95, "CH"],
                                         ["Zürich", 47.4, 8.5, "CH"]]}
        v = Verorter([], {}, verortung, [], [])
        # Punkt in Buenos Aires für ein Schweizer Festival: verworfen
        weit = fest(stadt="Unbekannt", land="CH", lat=-34.6, lon=-58.4)
        assert v(weit)[:2] == (None, None)
        # Punkt in der Schweiz: übernommen
        nah = fest(stadt="Unbekannt", land="CH", lat=46.5, lon=8.6)
        assert v(nah)[:2] == (46.5, 8.6)
        assert v.aus_quelle == 1

    def test_ein_sammelpunkt_zaehlt_nicht(self):
        """Die Quelle setzt bei unbekanntem Ort gern den Landesmittelpunkt ein
        — 51.5/10.5 steht dreizehnmal da, quer durch Deutschland."""
        viele = [fest(stadt=ort, lat=51.5, lon=10.5) for ort in ("A", "B", "C")]
        v = Verorter(viele, {}, {"plz": [], "orte": []}, [], [])
        assert v(viele[0])[:2] == (None, None)


class TestPostleitzahlen:
    def test_eindeutige_postleitzahl_ergaenzt_das_land(self):
        verortung = {"plz": [["1010", 48.2, 16.3, "AT"]], "orte": []}
        v = Verorter([], {}, verortung, [], [])
        assert v(fest(plz="1010", land=""))[2] == "AT"

    def test_mehrdeutige_postleitzahl_ohne_land_zaehlt_nicht(self):
        verortung = {"plz": [["1010", 48.2, 16.3, "AT"], ["1010", 47.0, 8.0, "CH"]],
                     "orte": []}
        v = Verorter([], {}, verortung, [], [])
        assert v(fest(plz="1010", land=""))[:2] == (None, None)


class TestHilfen:
    def test_laender_rahmen(self):
        orte = [["A", 47.0, 6.0, "CH"], ["B", 48.0, 10.0, "CH"],
                ["C", 52.0, 13.0, "DE"]]
        assert laender_rahmen(orte)["CH"] == (47.0, 48.0, 6.0, 10.0)

    def test_platzhalter_erkennt_sammelpunkte(self):
        viele = [fest(stadt=ort, lat=51.5, lon=10.5) for ort in ("A", "B", "C")]
        viele.append(fest(stadt="München", lat=48.0, lon=11.0))
        assert platzhalter(viele) == {(51.5, 10.5)}

    def test_derselbe_ort_mehrfach_ist_kein_platzhalter(self):
        """Ein echter Veranstaltungsort taucht auch mehrfach auf — dann aber
        immer mit demselben Ortsnamen."""
        viele = [fest(stadt="Wacken", lat=54.0, lon=9.4) for _ in range(5)]
        assert platzhalter(viele) == set()
