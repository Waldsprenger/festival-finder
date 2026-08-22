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

    def get(self, _url, **_kwargs):
        self.gefragt += 1
        wert = self.antworten.pop(0) if self.antworten else Antwort()
        if isinstance(wert, Exception):
            raise wert
        return wert


TREFFER = [{"lat": "54.3", "lon": "10.1", "display_name": "Kiel, Deutschland"}]


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

    def test_das_land_geht_mit(self):
        """Bei mehrdeutigen Namen liefert Nominatim den weltweit bekanntesten
        Ort: „Newark" wurde New Jersey statt England."""
        assert geokodieren.cc("Deutschland") == "de"
        assert geokodieren.cc("Bayern") == ""


class TestKurzeCodes:
    """Welche Postleitzahlen die Seite mitbekommt — und welche sie nachlädt."""

    def eintrag(self, code, cc):
        return [code, "Musterstadt", 50.0, 8.0, cc]

    def test_vierstellige_laender_werden_erkannt(self):
        alle = [self.eintrag("1012", "NL"), self.eintrag("2000", "BE"),
                self.eintrag("75001", "FR")]
        assert gazetteer.kurze_codes(alle) == {"NL", "BE"}

    def test_ein_langer_code_zaehlt_fuers_ganze_land(self):
        """Frankreich hat fünfstellige Codes — dort antwortet Nominatim."""
        alle = [self.eintrag("7500", "FR"), self.eintrag("75001", "FR")]
        assert gazetteer.kurze_codes(alle) == set()

    def test_buchstabencodes_zaehlen_nach_laenge(self):
        """Großbritannien führt Bezirkscodes wie „SW1A"."""
        assert gazetteer.kurze_codes([self.eintrag("SW1A", "GB")]) == {"GB"}

    def test_ohne_daten_kein_land(self):
        assert gazetteer.kurze_codes([]) == set()
