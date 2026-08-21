"""Die Wächter des Laufs: Selbstprüfung und Einbruchsmeldung."""

import festival_scraper as lauf
import netz
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


class TestAbweisung:
    def vergessen(self):
        netz.ABGEWIESEN.clear()
        netz.MELDUNGEN.clear()

    def test_eine_absage_sperrt_noch_nichts(self):
        self.vergessen()
        assert netz.abweisung_vermerken("https://beispiel.de/a", 403) is False
        assert netz.weist_ab("https://beispiel.de/b") is False

    def test_nach_fuenf_absagen_bleibt_der_rechner_in_ruhe(self):
        self.vergessen()
        for i in range(netz.SPERRE_AB):
            netz.abweisung_vermerken(f"https://beispiel.de/{i}", 403)
        assert netz.weist_ab("https://beispiel.de/noch-eine") is True
        assert netz.MELDUNGEN == ["beispiel.de weist den Lauf ab (403) - "
                                  "keine weiteren Anfragen dorthin"]

    def test_andere_rechner_bleiben_unberuehrt(self):
        self.vergessen()
        for i in range(netz.SPERRE_AB + 3):
            netz.abweisung_vermerken(f"https://beispiel.de/{i}", 403)
        assert netz.weist_ab("https://andere.de/x") is False

    def test_nur_403_zaehlt(self):
        # 429 heisst "zu schnell", 500 ist eine Panne - beides keine Absage
        self.vergessen()
        for code in (429, 500, 503, None):
            for i in range(netz.SPERRE_AB + 1):
                netz.abweisung_vermerken(f"https://beispiel.de/{i}", code)
        assert netz.weist_ab("https://beispiel.de/x") is False


class TestFehlerherkunft:
    def test_nicht_ladbare_adressen_je_haus(self):
        assert lauf.haeuser([
            "https://www.festivalticker.de/2026/ (HTTPError)",
            "https://www.festivalticker.de/alle-festivals/ (HTTPError)",
            "https://festapp.io/x (Timeout)",
        ]) == {"www.festivalticker.de": 2, "festapp.io": 1}

    def test_ohne_fehler_leeres_verzeichnis(self):
        assert lauf.haeuser([]) == {}

    def test_fehlerart_steht_dabei(self):
        # Abgewiesen zu werden ist etwas anderes, als keine Leitung zu bekommen
        assert lauf.gruende([
            "https://www.festivalticker.de/2026/ (ConnectionError)",
            "https://www.festivalticker.de/alle-festivals/ (ConnectionError)",
            "https://festapp.io/x (HTTPError)",
        ]) == {"www.festivalticker.de ConnectionError": 2, "festapp.io HTTPError": 1}

    def test_statuscode_bleibt_erhalten(self):
        # 403 waere eine Entscheidung des Betreibers, 429 nur zu schnelles Fragen
        assert lauf.gruende(["https://www.festivalticker.de/2026/ (HTTPError 403)"]) == {
            "www.festivalticker.de HTTPError 403": 1}


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

    def test_gar_kein_fund_wird_gemeldet(self, tmp_path, monkeypatch):
        # Die schlimmste Störung war die stumme: Eine Null taugt nicht als
        # Maßstab, also verglich niemand mehr - festivalticker lieferte beim
        # Lauf auf fremden Servern monatelang nichts, ohne eine Zeile Protokoll.
        self.stand(tmp_path, monkeypatch,
                   '{"quellen": {"festivalticker": 0}, "festivals": 900}')
        warnungen = lauf.pruefe_ausbeute({"festivalticker": 0}, 890)
        assert warnungen == ["festivalticker: kein einziger Fund"]

    def test_null_meldet_auch_ohne_massstab(self, tmp_path, monkeypatch):
        self.stand(tmp_path, monkeypatch)
        assert lauf.pruefe_ausbeute({"festivalticker": 0}, 890)

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
