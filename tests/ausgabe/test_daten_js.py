"""Die Auslieferung: Was nicht stimmt, darf nicht raus.

Die Webseite liest jede Zeile über feste Spaltennummern und jede Band über
ihren Index. Stimmt daran etwas nicht, bleibt die Seite leer — und zwar still.
Deshalb bricht der Bau lieber ab: Dann behält die Veröffentlichung den letzten
guten Stand.
"""

import json
from datetime import date

import pytest

from festivalfinder.ausgabe import daten_js
from festivalfinder.ausgabe.daten_js import (LINEUP, aufrunden, als_javascript,
                                             datenrahmen,
                                             frueheste_monatsgrenze, pruefe)
from festivalfinder.kern.festival import Festival
from festivalfinder.werkzeug import neuheiten


def zeile(**rest):
    grund = dict(name="Testival", von="2026-06-01", bis="2026-06-02", stadt="Kiel",
                 land="DE", ort="", eur=45.0, preis="45 €", web="", lat=54.3,
                 lon=10.1, lineup=[0], hinweis="", abgesagt=0, genres=[0],
                 preis_start="")
    grund.update(rest)
    return [grund["name"], grund["von"], grund["bis"], grund["stadt"], grund["land"],
            grund["ort"], grund["eur"], grund["preis"], grund["web"], grund["lat"],
            grund["lon"], grund["lineup"], grund["hinweis"], grund["abgesagt"],
            grund["genres"], grund["preis_start"]]


BANDS = ["Powerwolf"]
GENRES = ["rock"]


class TestPruefung:
    def test_saubere_zeile_geht_durch(self):
        pruefe([zeile()], BANDS, GENRES)

    @pytest.mark.parametrize("kaputt,text", [
        ({"name": ""}, "ohne Namen"),
        ({"lineup": [7]}, "Bandnummer"),
        ({"genres": [3]}, "Genrenummer"),
        ({"lon": None}, "Koordinatenhälfte"),
        ({"eur": 99999.0}, "unplausibel"),
    ])
    def test_fehler_brechen_ab(self, kaputt, text):
        with pytest.raises(ValueError, match=text):
            pruefe([zeile(**kaputt)], BANDS, GENRES)

    def test_falsche_spaltenzahl(self):
        with pytest.raises(ValueError, match="16 Spalten"):
            pruefe([zeile()[:12]], BANDS, GENRES)


class TestAlsJavascript:
    def rueckwaerts(self, inhalt):
        """Wie der Browser: erst die JS-Zeichenkette, dann das JSON."""
        roh = inhalt[inhalt.index("('") + 2: inhalt.rindex("')")]
        js = (roh.replace("\\/", "/").replace("\\'", "'")
                 .replace("\\u2028", "\u2028").replace("\\u2029", "\u2029")
                 .replace("\\\\", "\\"))
        return json.loads(js)

    def test_gewoehnliche_daten(self):
        daten = {"bands": ["Powerwolf", "AC/DC"], "n": 5, "leer": None}
        assert self.rueckwaerts(als_javascript("DATA", daten)) == daten

    def test_apostroph_und_anfuehrungszeichen(self):
        daten = {"bands": ["Manfred Mann's Earth Band", 'Zeichen: "Rock"']}
        assert self.rueckwaerts(als_javascript("DATA", daten)) == daten

    def test_rueckstrich_bleibt_erhalten(self):
        daten = {"name": "AC\\DC", "pfad": "C:\\Temp"}
        assert self.rueckwaerts(als_javascript("DATA", daten)) == daten

    def test_script_ende_wird_entschaerft(self):
        """In der gebündelten Einzelseite steht alles in einem <script>."""
        text = als_javascript("DATA", {"name": "</script><b>"})
        assert "</script>" not in text
        assert self.rueckwaerts(text) == {"name": "</script><b>"}

    def test_zeilentrenner(self):
        """In JSON erlaubt, in einer JS-Zeichenkette nicht."""
        daten = {"name": "vor\u2028nach"}
        assert self.rueckwaerts(als_javascript("DATA", daten)) == daten

    def test_der_name_steht_vorn(self):
        assert als_javascript("ORTE_WELT", {}).startswith("window.ORTE_WELT = JSON.parse('")


class TestGrenzen:
    def test_aufrunden(self):
        assert aufrunden(137) == 140
        assert aufrunden(455) == 500
        assert aufrunden(1234) == 1300

    def test_datenrahmen_umschliesst_alle_punkte(self):
        zeilen = [zeile(lat=54.3, lon=10.1), zeile(lat=48.1, lon=11.6)]
        lat0, lat1, lon0, lon1 = datenrahmen(zeilen)
        assert lat0 == 48.1 and lat1 == 54.3
        assert lon0 == 10.1 and lon1 == 11.6

    def test_der_rahmen_schliesst_auch_die_raender_ein(self):
        """Gerundet wird nach aussen: round(-46.4137, 2) laege noerdlich des
        suedlichsten Punktes, und die Karte schnitte ihn ab."""
        zeilen = [zeile(lat=-46.4137, lon=-73.5561),
                  zeile(lat=64.1466, lon=178.0042)]
        lat0, lat1, lon0, lon1 = datenrahmen(zeilen)
        for z in zeilen:
            assert lat0 <= z[9] <= lat1 and lon0 <= z[10] <= lon1

    def test_ohne_punkte_der_feine_ausschnitt(self):
        from festivalfinder.kern.orte import FEINRAHMEN
        assert datenrahmen([zeile(lat=None, lon=None)]) == list(FEINRAHMEN)

    def test_kalender_beginnt_am_monatsersten(self):
        """Damit sich nichts einstellen lässt, wofür es keine Daten gibt."""
        assert frueheste_monatsgrenze([zeile(von="2026-05-16")]) == "2026-05-01"

    def test_ohne_termine_keine_untergrenze(self):
        assert frueheste_monatsgrenze([zeile(von="")]) == ""


class TestNeuigkeiten:
    """`site/neu.json` — was die Seite gegen ihre gemerkten Wunschlisten hält."""

    @pytest.fixture(autouse=True)
    def eigene_dateien(self, tmp_path, monkeypatch):
        monkeypatch.setattr(neuheiten, "TAGEBUCH", tmp_path / "neuheiten.json")
        monkeypatch.setattr(daten_js, "SITE", tmp_path)
        return tmp_path

    def eintraege(self, tmp_path):
        return json.loads((tmp_path / "neu.json").read_text(encoding="utf-8"))

    def test_ein_neuzugang_kommt_mit(self, tmp_path):
        f = Festival(name="Neufest", jahr="2026", stadt="Kiel")
        neuheiten.TAGEBUCH.write_text(json.dumps(
            [{"k": f.kennung, "seit": "2026-08-25", "grund": "neu",
              "bands": ["Powerwolf"]}]), encoding="utf-8")

        anzahl = daten_js.neuigkeiten([f], [zeile(name="Neufest")], "2026-08-25T05:00")
        assert anzahl == 1
        inhalt = self.eintraege(tmp_path)
        assert inhalt["stand"] == "2026-08-25T05:00"
        assert inhalt["eintraege"][0]["g"] == "neu"
        assert inhalt["eintraege"][0]["b"] == ["Powerwolf"]
        assert inhalt["eintraege"][0]["z"][0] == "Neufest"

    def test_die_lineupnummern_bleiben_draussen(self, tmp_path):
        """Sie werden bei jedem Bauen neu vergeben — eine gemerkte 4711 meinte
        morgen eine andere Band. Was dazukam, steht als Name daneben."""
        f = Festival(name="Neufest", jahr="2026", stadt="Kiel")
        neuheiten.TAGEBUCH.write_text(json.dumps(
            [{"k": f.kennung, "seit": "2026-08-25", "grund": "lineup",
              "bands": ["Ghost"]}]), encoding="utf-8")
        daten_js.neuigkeiten([f], [zeile(lineup=[3, 7])], "2026-08-25T05:00")
        assert self.eintraege(tmp_path)["eintraege"][0]["z"][LINEUP] == []

    def test_die_zeile_behaelt_ihre_spaltenordnung(self, tmp_path):
        """Es soll nur eine Zeilenform geben — sonst prüft die Seite zweierlei
        Zeilen mit zweierlei Regeln."""
        f = Festival(name="Neufest", jahr="2026", stadt="Kiel")
        neuheiten.TAGEBUCH.write_text(json.dumps(
            [{"k": f.kennung, "seit": "2026-08-25", "grund": "neu", "bands": []}]),
            encoding="utf-8")
        daten_js.neuigkeiten([f], [zeile()], "2026-08-25T05:00")
        assert len(self.eintraege(tmp_path)["eintraege"][0]["z"]) == len(zeile())

    def test_was_es_nicht_mehr_gibt_kommt_nicht_mit(self, tmp_path):
        """Ein Festival, das inzwischen wieder verschwunden ist, muss niemand
        gemeldet bekommen."""
        neuheiten.TAGEBUCH.write_text(json.dumps(
            [{"k": "verschwunden|2026|kiel", "seit": "2026-08-25",
              "grund": "neu", "bands": []}]), encoding="utf-8")
        assert daten_js.neuigkeiten([], [], "2026-08-25T05:00") == 0

    def test_ohne_tagebuch_bleibt_die_datei_leer(self, tmp_path):
        assert daten_js.neuigkeiten([], [], "2026-08-25T05:00") == 0
        assert self.eintraege(tmp_path)["eintraege"] == []
