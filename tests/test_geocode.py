"""Der Geokodierer: Ein Ausfall des Dienstes darf sich nicht festschreiben.

Nominatim wird nur gefragt, was das eigene Ortsverzeichnis nicht hergibt, und
jede Antwort landet dauerhaft im Cache — auch die leere. Wäre "gerade nicht
erreichbar" dasselbe wie "kennt den Ort nicht", würde ein einziger Ausfall
hunderte Festivals auf Dauer ohne Koordinaten lassen.
"""

import geocode


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


def ohne_warten(monkeypatch):
    monkeypatch.setattr(geocode.time, "sleep", lambda _s: None)


def test_treffer_wird_gemeldet(monkeypatch):
    ohne_warten(monkeypatch)
    ort, geantwortet = geocode.lookup(Dienst(Antwort(200, TREFFER)), "Kiel", "DE")
    assert geantwortet is True
    assert ort == {"lat": 54.3, "lon": 10.1, "display": "Kiel, Deutschland"}


def test_unbekannter_ort_ist_eine_antwort(monkeypatch):
    ohne_warten(monkeypatch)
    ort, geantwortet = geocode.lookup(Dienst(Antwort(200, [])), "Nirgendwo", "DE")
    assert ort is None
    assert geantwortet is True          # darf als "kennt ihn nicht" gemerkt werden


def test_ausfall_ist_keine_antwort(monkeypatch):
    ohne_warten(monkeypatch)
    ort, geantwortet = geocode.lookup(
        Dienst(*[ConnectionError("weg")] * 4), "Kiel", "DE")
    assert ort is None
    assert geantwortet is False         # morgen noch einmal fragen


def test_serverfehler_ist_keine_antwort(monkeypatch):
    ohne_warten(monkeypatch)
    ort, geantwortet = geocode.lookup(
        Dienst(*[Antwort(503)] * 4), "Kiel", "DE")
    assert ort is None
    assert geantwortet is False


def test_zweiter_versuch_zaehlt_auch(monkeypatch):
    ohne_warten(monkeypatch)
    dienst = Dienst(Antwort(200, []), Antwort(200, TREFFER))
    ort, geantwortet = geocode.lookup(dienst, "Kiel", "DE")
    assert ort and geantwortet
    assert dienst.gefragt == 2
