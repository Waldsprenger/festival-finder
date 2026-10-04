"""Werkzeuge, die fremde Dienste fragen — und was sie sich merken dürfen.

Der Geokodierer wird nur gefragt, was das eigene Ortsverzeichnis nicht hergibt,
und jede Antwort landet dauerhaft im Cache — auch die leere. Wäre „gerade nicht
erreichbar" dasselbe wie „kennt den Ort nicht", ließe ein einziger Ausfall
hunderte Festivals auf Dauer ohne Koordinaten.
"""

import pytest

from festivalfinder.werkzeug import gazetteer, geokodieren


class Antwort:
    def __init__(self, status=200, treffer=None):
        self.status_code = status
        self._treffer = treffer or []

    def json(self):
        return self._treffer


class Dienst:
    """Ein Nominatim, das sich so verhält, wie der Test es braucht."""

    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.gefragt = 0
        #: die Parameter jeder Anfrage, in der Reihenfolge des Fragens
        self.fragen = []

    def get(self, _url, params=None, **_kwargs):
        self.gefragt += 1
        self.fragen.append(params or {})
        wert = self.antworten.pop(0) if self.antworten else Antwort()
        if isinstance(wert, Exception):
            raise wert
        return wert


def treffer(lat="54.3", lon="10.1", anzeige="Kiel, Deutschland", land="de"):
    return [{"lat": lat, "lon": lon, "display_name": anzeige,
             "address": {"country_code": land}}]


TREFFER = treffer()


@pytest.fixture(autouse=True)
def ohne_warten(monkeypatch):
    monkeypatch.setattr(geokodieren.time, "sleep", lambda _s: None)


class TestGeokodieren:
    def test_treffer_wird_gemeldet(self):
        ort, geantwortet = geokodieren.nachschlagen(
            Dienst(Antwort(200, TREFFER)), "Kiel", "DE")
        assert geantwortet is True
        assert ort == {"lat": 54.3, "lon": 10.1, "display": "Kiel, Deutschland"}

    def test_unbekannter_ort_ist_eine_antwort(self):
        ort, geantwortet = geokodieren.nachschlagen(
            Dienst(Antwort(200, [])), "Nirgendwo", "DE")
        assert ort is None
        assert geantwortet is True      # darf als „kennt ihn nicht" gemerkt werden

    def test_ausfall_ist_keine_antwort(self):
        ort, geantwortet = geokodieren.nachschlagen(
            Dienst(*[ConnectionError("weg")] * 4), "Kiel", "DE")
        assert ort is None
        assert geantwortet is False     # morgen noch einmal fragen

    def test_serverfehler_ist_keine_antwort(self):
        ort, geantwortet = geokodieren.nachschlagen(
            Dienst(*[Antwort(503)] * 4), "Kiel", "DE")
        assert ort is None
        assert geantwortet is False

    def test_zweiter_versuch_zaehlt_auch(self):
        dienst = Dienst(Antwort(200, []), Antwort(200, TREFFER))
        ort, geantwortet = geokodieren.nachschlagen(dienst, "Kiel", "DE")
        assert ort and geantwortet
        assert dienst.gefragt == 2

    def test_das_land_bleibt_bei_jedem_versuch_bedingung(self):
        """Es stand einmal nur im ersten Versuch. Scheiterte der, suchte der
        zweite weltweit — und Nominatim antwortete willig: Buenos Aires lag
        danach in Spanien, Jakarta in Berlin, Hongkong in Paris."""
        dienst = Dienst(Antwort(200, []), Antwort(200, []))
        geokodieren.nachschlagen(dienst, "Buenos Aires", "AR")
        assert dienst.gefragt == 2
        assert all(f.get("countrycodes") == "ar" for f in dienst.fragen),             dienst.fragen

    def test_ein_treffer_im_falschen_land_gilt_nicht(self):
        """Lieber kein Punkt als ein falscher."""
        spanien = treffer("40.95", "-5.70", "Buenos Aires, Salamanca", "es")
        ort, geantwortet = geokodieren.nachschlagen(
            Dienst(Antwort(200, spanien), Antwort(200, spanien)),
            "Buenos Aires", "AR")
        assert ort is None
        assert geantwortet is True

    def test_ohne_landesangabe_wird_weltweit_gesucht(self):
        dienst = Dienst(Antwort(200, []), Antwort(200, TREFFER))
        ort, _ = geokodieren.nachschlagen(dienst, "Kiel", "")
        assert ort and all("countrycodes" not in f for f in dienst.fragen)

    def test_das_land_geht_mit(self):
        """Bei mehrdeutigen Namen liefert Nominatim den weltweit bekanntesten
        Ort: „Newark" wurde New Jersey statt England."""
        assert geokodieren.cc("Deutschland") == "de"
        assert geokodieren.cc("Bayern") == ""


class TestPostleitzahlenDerWelt:
    """Die Postleitzahlen der Wohnortsuche: so genau wie nötig, so klein wie möglich."""

    def test_schreibform_und_schluessel(self):
        assert gazetteer.plz_schluessel("3750-000", "PT") == ("3750-000", "3750000")
        assert gazetteer.plz_schluessel("624 66", "SE") == ("624 66", "62466")
        # Der Ländervorsatz gehört nicht zum Code
        assert gazetteer.plz_schluessel("LV-5101", "LV") == ("5101", "5101")
        assert gazetteer.plz_schluessel("L-4968", "LU") == ("4968", "4968")
        # „CEDEX" ist in Frankreich ein Zusatz für Großkunden
        assert gazetteer.plz_schluessel("97491 CEDEX", "RE") == ("97491", "97491")

    def test_form_erkennt_das_land(self):
        """An der Form liest die Seite ab, aus welchem Land ein Code sein kann."""
        assert gazetteer.form_von("490-1401") == "999-9999"       # Japan
        assert gazetteer.form_von("3750-000") == "9999-999"       # Portugal
        assert gazetteer.form_von("624 66") == "999-99"           # Schweden
        assert gazetteer.form_von("SW1A") == "AA9A"               # Großbritannien

    def test_nahe_codes_fallen_zusammen(self):
        """Lissabon führt jede Straße mit eigenem Code; für den Umkreis genügt das Viertel."""
        codes = {f"110014{n}": (38.72 + n * 0.0005, -9.13) for n in range(10)}
        # Zwei Stellen dürfen wegfallen, mehr nicht
        assert gazetteer.plz_verdichten(codes) == {"11001": [38.722, -9.13]}

    def test_ferne_codes_bleiben_getrennt(self):
        codes = {"10115": (52.53, 13.38), "10117": (52.52, 13.39), "80331": (48.14, 11.57)}
        verdichtet = gazetteer.plz_verdichten(codes)
        assert "80331" in verdichtet or "803" in verdichtet
        assert not any(k in verdichtet for k in ("", "1", "8"))

    def test_hoechstens_zwei_stellen_fallen_weg(self):
        """Monaco liegt ganz in fünf Kilometern. Fiele es auf den leeren Präfix,
        wäre jede fünfstellige Zahl der Welt eine Postleitzahl in Monaco."""
        codes = {f"980{n:02d}": (43.73, 7.42) for n in range(20)}
        assert set(gazetteer.plz_verdichten(codes)) == {"980"}
