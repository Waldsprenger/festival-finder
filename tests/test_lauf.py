"""Die Wächter des Laufs: Selbstprüfung und Einbruchsmeldung."""

import festival_scraper as lauf
import pytest


def festival(**rest):
    grund = {"name": "Testival", "year": "2026", "date_from": "01.06.2026",
             "date_to": "02.06.2026", "city": "Kiel", "country": "DE", "venue": "",
             "plz": "", "lat": 54.3, "lon": 10.1, "location": "Kiel, DE", "price": "",
             "website": "", "genre": "", "visitors": "", "note": "", "cancelled": False,
             "sources": {"festivalticker": "https://x/y"}, "lineup": [], "lineup_count": 0}
    return {**grund, **rest}


class TestSelbstpruefung:
    def test_sauberer_bestand_meldet_nichts(self):
        assert lauf.pruefe_stimmigkeit([festival()]) == []

    @pytest.mark.parametrize("kaputt,meldung", [
        ({"name": "  "}, "ohne Namen"),
        ({"sources": {}}, "ohne Quelle"),
        ({"year": "2027"}, "Jahr passt nicht zum Termin"),
        ({"date_to": "01.05.2026"}, "Ende vor Anfang"),
        ({"lat": -34.6, "lon": -58.4}, "Koordinate außerhalb Europas"),
        ({"lineup": ["Powerwolf"], "lineup_count": 0}, "Lineup falsch gezählt"),
        ({"visitors": "2.000"}, "Besucherzahl keine Zahl"),
        ({"country": "US"}, "Land außerhalb Europas"),
    ])
    def test_jeder_widerspruch_wird_gemeldet(self, kaputt, meldung):
        gefunden = lauf.pruefe_stimmigkeit([festival(**kaputt)])
        assert any(meldung in z for z in gefunden), gefunden

    def test_dublette_faellt_auf(self):
        doppelt = [festival(), festival(sources={"festivalsunited": "https://a/b"})]
        assert any("Dublette" in z for z in lauf.pruefe_stimmigkeit(doppelt))

    def test_zwei_ausgaben_im_jahr_sind_keine_dublette(self):
        juni = festival(date_from="14.06.2026", date_to="14.06.2026")
        september = festival(date_from="05.09.2026", date_to="05.09.2026")
        assert lauf.pruefe_stimmigkeit([juni, september]) == []


class TestEinbruchswaechter:
    def stand(self, tmp_path, monkeypatch, inhalt=None):
        monkeypatch.setattr(lauf, "DATA", tmp_path)
        if inhalt is not None:
            (tmp_path / "quellen_stand.json").write_text(inhalt, encoding="utf-8")

    def test_erster_lauf_warnt_nicht(self, tmp_path, monkeypatch):
        self.stand(tmp_path, monkeypatch)
        assert lauf.pruefe_ausbeute({"festivalticker": 100}, 90) == []

    def test_einbruch_wird_gemeldet(self, tmp_path, monkeypatch):
        self.stand(tmp_path, monkeypatch,
                   '{"quellen": {"festivalticker": 1000}, "festivals": 900}')
        warnungen = lauf.pruefe_ausbeute({"festivalticker": 500}, 890)
        assert warnungen and "festivalticker" in warnungen[0]

    def test_kleine_schwankung_ist_normal(self, tmp_path, monkeypatch):
        self.stand(tmp_path, monkeypatch,
                   '{"quellen": {"festivalticker": 1000}, "festivals": 900}')
        assert lauf.pruefe_ausbeute({"festivalticker": 950}, 890) == []

    def test_massstab_bleibt_bis_es_wieder_stimmt(self, tmp_path, monkeypatch):
        import json
        self.stand(tmp_path, monkeypatch,
                   '{"quellen": {"festivalticker": 1000}, "festivals": 900}')
        lauf.pruefe_ausbeute({"festivalticker": 500}, 890)
        gemerkt = json.loads((tmp_path / "quellen_stand.json").read_text(encoding="utf-8"))
        # Der schlechte Wert darf nicht zum neuen Normal werden
        assert gemerkt["quellen"]["festivalticker"] == 1000
        # ... und der nächste Lauf warnt deshalb erneut
        assert lauf.pruefe_ausbeute({"festivalticker": 500}, 890)
