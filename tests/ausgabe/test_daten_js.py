"""Die Auslieferung: Was nicht stimmt, darf nicht raus.

Die Webseite liest jede Zeile über feste Spaltennummern und jede Band über
ihren Index. Stimmt daran etwas nicht, bleibt die Seite leer — und zwar still.
Deshalb bricht der Bau lieber ab: Dann behält die Veröffentlichung den letzten
guten Stand.
"""

import json

import pytest

from festivalfinder.ausgabe import daten_js
from festivalfinder.ausgabe.daten_js import (als_javascript, datenrahmen,
                                             frueheste_monatsgrenze, pruefe,
                                             schreiben_wenn_neu)
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


class TestGeodaten:
    """geo.js ändert sich fast nie — und darf deshalb auch nicht neu entstehen.

    Vorher steckten die Geodaten in data.js, und jeder Besucher lud nach jedem
    täglichen Lauf 5 MB neu, die sich nicht geändert hatten.
    """

    @pytest.fixture(autouse=True)
    def eigener_ordner(self, tmp_path, monkeypatch):
        monkeypatch.setattr(daten_js, "SITE", tmp_path)
        return tmp_path

    def test_gleicher_inhalt_gleiche_kennung_keine_neue_datei(self, eigener_ordner):
        k1 = schreiben_wenn_neu("geo.js", "window.GEO = 1;\n")
        zeit = (eigener_ordner / "geo.js").stat().st_mtime_ns
        assert schreiben_wenn_neu("geo.js", "window.GEO = 1;\n") == k1
        assert (eigener_ordner / "geo.js").stat().st_mtime_ns == zeit

    def test_anderer_inhalt_andere_kennung(self, eigener_ordner):
        assert schreiben_wenn_neu("geo.js", "a") != schreiben_wenn_neu("geo.js", "b")
        assert (eigener_ordner / "geo.js").read_text(encoding="utf-8") == "b"


class TestGrenzen:
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
    """`D.neu` — seit wann die Seite welches Festival und welche Band kennt."""

    @pytest.fixture(autouse=True)
    def eigene_datei(self, tmp_path, monkeypatch):
        monkeypatch.setattr(neuheiten, "DATEI", tmp_path / "bestand_verlauf.json")
        return tmp_path

    def aufzeichnen(self, laeufe):
        """Mehrere Laeufe nacheinander: [(datum, [Festival, ...]), ...]"""
        for datum, feste in laeufe:
            neuheiten.verfolgen(feste, heute=datum)

    def test_ein_neuzugang_zeigt_auf_seine_zeile(self):
        alt, neu = Festival(name="Altfest", jahr="2026", stadt="Kiel"),             Festival(name="Neufest", jahr="2026", stadt="Kiel")
        self.aufzeichnen([("2026-08-24", [alt]), ("2026-08-27", [alt, neu])])

        d = daten_js.neuigkeiten([alt, neu], {})
        assert d["beginn"] == "2026-08-24"
        assert d["feste"] == [[1, 3]], "Zeile 1, drei Tage nach dem Beginn"
        assert d["bands"] == []

    def test_eine_bestaetigte_band_zeigt_auf_ihre_nummer(self):
        def wacken(*bands):
            return Festival(name="Wacken", jahr="2026", stadt="Wacken",
                            bands={b.lower(): b for b in bands})
        self.aufzeichnen([("2026-08-24", [wacken("Ghost")]),
                          ("2026-08-25", [wacken("Ghost", "Powerwolf")])])

        d = daten_js.neuigkeiten([wacken("Ghost", "Powerwolf")],
                                 {"Ghost": 0, "Powerwolf": 7})
        assert d["feste"] == [], "das Festival selbst ist nicht neu"
        assert d["bands"] == [[0, 7, 1]], "Zeile 0, Band 7, einen Tag nach dem Beginn"

    def test_der_anfangsbestand_kommt_nicht_vor(self):
        """Sonst waere beim ersten Lauf alles neu."""
        f = Festival(name="Testival", jahr="2026", stadt="Kiel",
                     bands={"ghost": "Ghost"})
        self.aufzeichnen([("2026-08-24", [f]), ("2026-08-25", [f])])
        d = daten_js.neuigkeiten([f], {"Ghost": 0})
        assert (d["feste"], d["bands"]) == ([], [])

    def test_eine_band_ohne_nummer_faellt_weg(self):
        """Sie kann aus allen Quellen verschwunden sein — dann gibt es keine
        Zeile, auf die sich die Meldung beziehen koennte."""
        def f(*bands):
            return Festival(name="Testival", jahr="2026", stadt="Kiel",
                            bands={b.lower(): b for b in bands})
        self.aufzeichnen([("2026-08-24", [f("Ghost")]),
                          ("2026-08-25", [f("Ghost", "Powerwolf")])])
        assert daten_js.neuigkeiten([f("Ghost")], {"Ghost": 0})["bands"] == []

    def test_ohne_aufzeichnung_bleibt_es_leer(self):
        d = daten_js.neuigkeiten([], {})
        assert d == {"beginn": "", "feste": [], "bands": []}
