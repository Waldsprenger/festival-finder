"""Preisgeschichte und mitgebrachter Stand.

Zwei Dateien, die nirgends sonst stehen: Was in ihnen verloren geht, ist
verloren. Deshalb hat jede von beiden eine Regel, die sie davor schützt.
"""

import gzip
import json
from datetime import date

import pytest

from festivalfinder.kern.festival import Festival
from festivalfinder.kern.fund import fund
from festivalfinder.kern.zeit import aus_deutsch
from festivalfinder.werkzeug import preisverlauf, schnappschuss


# --------------------------------------------------------------------------
# Preisgeschichte
# --------------------------------------------------------------------------

def fest(preis, name="Testival", jahr="2026", stadt="Kiel"):
    return Festival(name=name, jahr=jahr, stadt=stadt, preis=preis)


@pytest.fixture
def verlaufsdatei(tmp_path, monkeypatch):
    ziel = tmp_path / "preis_verlauf.json"
    monkeypatch.setattr(preisverlauf, "DATEI", ziel)
    return ziel


class TestPreisverlauf:
    def test_erster_lauf_merkt_sich_den_preis(self, verlaufsdatei):
        f = fest("VVK 89 €")
        preisverlauf.verfolgen([f], heute="2026-08-21")
        assert f.preis_start == ""            # noch keine Änderung
        gespeichert = json.loads(verlaufsdatei.read_text(encoding="utf-8"))
        assert gespeichert["testival|2026|kiel"] == {
            "erst": "VVK 89 €", "seit": "2026-08-21",
            "aktuell": "VVK 89 €", "stand": "2026-08-21"}

    def test_gestiegener_preis_nennt_den_start(self, verlaufsdatei):
        preisverlauf.verfolgen([fest("VVK 89 €")], heute="2026-08-21")
        f = fest("VVK 129 €")
        preisverlauf.verfolgen([f], heute="2026-09-15")
        assert f.preis_start == "VVK 89 €"
        assert f.preis_start_seit == "2026-08-21"

    def test_der_start_bleibt_der_start(self, verlaufsdatei):
        preisverlauf.verfolgen([fest("VVK 89 €")], heute="2026-08-21")
        preisverlauf.verfolgen([fest("VVK 129 €")], heute="2026-09-15")
        f = fest("VVK 149 €")
        preisverlauf.verfolgen([f], heute="2026-10-01")
        assert f.preis_start == "VVK 89 €"     # nicht 129
        assert f.preis_start_seit == "2026-08-21"

    def test_unveraenderter_preis_bleibt_ohne_zusatz(self, verlaufsdatei):
        preisverlauf.verfolgen([fest("VVK 89 €")], heute="2026-08-21")
        f = fest("VVK 89 €")
        preisverlauf.verfolgen([f], heute="2026-09-15")
        assert f.preis_start == ""

    def test_ein_fehlendes_festival_bleibt_erst_einmal_stehen(self, verlaufsdatei):
        """An dem Tag, an dem eine Quelle den Lauf abwies, fehlten 800
        Festivals auf einmal. Ihre Geschichte zu löschen hieße, den Startpreis
        beim nächsten Auftauchen neu zu erfinden."""
        preisverlauf.verfolgen([fest("89 €", name="Altfest")], heute="2026-08-21")
        preisverlauf.verfolgen([fest("89 €", name="Neufest")], heute="2026-08-22")
        verlauf = json.loads(verlaufsdatei.read_text(encoding="utf-8"))
        assert sorted(verlauf) == ["altfest|2026|kiel", "neufest|2026|kiel"]

    def test_nach_zwei_monaten_faellt_es_heraus(self, verlaufsdatei):
        preisverlauf.verfolgen([fest("89 €", name="Altfest")], heute="2026-06-01")
        preisverlauf.verfolgen([fest("89 €", name="Neufest")], heute="2026-08-22")
        verlauf = json.loads(verlaufsdatei.read_text(encoding="utf-8"))
        assert list(verlauf) == ["neufest|2026|kiel"]

    def test_der_startpreis_ueberlebt_eine_luecke(self, verlaufsdatei):
        preisverlauf.verfolgen([fest("89 €")], heute="2026-06-01")
        preisverlauf.verfolgen([], heute="2026-06-02")          # Quelle schweigt
        f = fest("99 €")
        preisverlauf.verfolgen([f], heute="2026-06-03")
        assert f.preis_start == "89 €"
        assert f.preis_start_seit == "2026-06-01"

    def test_festivals_ohne_preis_stehen_nicht_drin(self, verlaufsdatei):
        preisverlauf.verfolgen([fest("")], heute="2026-08-21")
        assert json.loads(verlaufsdatei.read_text(encoding="utf-8")) == {}

    def test_jahrgaenge_werden_getrennt_gefuehrt(self, verlaufsdatei):
        zahlen = preisverlauf.verfolgen(
            [fest("89 €", jahr="2026"), fest("99 €", jahr="2027")], heute="2026-08-21")
        assert zahlen["beobachtet"] == 2

    def test_zaehlt_die_aenderungen(self, verlaufsdatei):
        preisverlauf.verfolgen([fest("89 €")], heute="2026-08-21")
        zahlen = preisverlauf.verfolgen([fest("129 €")], heute="2026-09-15")
        assert zahlen["geändert"] == 1


# --------------------------------------------------------------------------
# Mitgebrachter Stand
# --------------------------------------------------------------------------

@pytest.fixture
def ordner(tmp_path, monkeypatch):
    monkeypatch.setattr(schnappschuss, "ORDNER", tmp_path / "schnappschuss")
    return tmp_path


def satz(name="Testival"):
    return fund("festivalticker", f"https://ft/{name}", name,
                von=aus_deutsch("01.06.2026"), stadt="Kiel", land="DE",
                lineup=["Powerwolf"])


class TestSchnappschuss:
    def test_hin_und_zurueck(self, ordner):
        assert schnappschuss.schreiben("festivalticker", [satz()]) is True
        funde, datum = schnappschuss.lesen("festivalticker")
        assert len(funde) == 1
        assert funde[0] == satz()
        assert datum == date.today().isoformat()

    def test_ein_lauf_ohne_funde_leert_nichts(self, ordner):
        """Sonst löschte ausgerechnet der Lauf, der nichts erreicht, die
        letzte Abschrift."""
        schnappschuss.schreiben("festivalticker", [satz()])
        assert schnappschuss.schreiben("festivalticker", []) is False
        funde, _ = schnappschuss.lesen("festivalticker")
        assert len(funde) == 1

    def test_nur_vorgesehene_quellen(self, ordner):
        assert schnappschuss.schreiben("festivalsunited", [satz()]) is False
        assert schnappschuss.lesen("festivalsunited") == ([], "")

    def test_ohne_datei_kommt_nichts(self, ordner):
        assert schnappschuss.lesen("festivalticker") == ([], "")

    def test_dieselben_funde_ergeben_dieselbe_datei(self, ordner):
        """Sonst stünde sie nach jedem Lauf als neue Fassung in der
        Versionsgeschichte, obwohl kein einziges Festival anders ist."""
        schnappschuss.schreiben("festivalticker", [satz()])
        erste = schnappschuss.datei("festivalticker").read_bytes()
        schnappschuss.schreiben("festivalticker", [satz()])
        assert schnappschuss.datei("festivalticker").read_bytes() == erste

    def test_die_reihenfolge_spielt_keine_rolle(self, ordner):
        a, b = satz("A"), satz("B")
        schnappschuss.schreiben("festivalticker", [a, b])
        erste = schnappschuss.datei("festivalticker").read_bytes()
        schnappschuss.schreiben("festivalticker", [b, a])
        assert schnappschuss.datei("festivalticker").read_bytes() == erste

    def test_termine_reisen_als_iso_datum(self, ordner):
        schnappschuss.schreiben("festivalticker", [satz()])
        roh = gzip.decompress(
            schnappschuss.datei("festivalticker").read_bytes()).decode("utf-8")
        assert '"von":"2026-06-01"' in roh

    def test_alter(self):
        assert schnappschuss.alter_in_tagen(date.today().isoformat()) == 0
        assert schnappschuss.alter_in_tagen("2020-01-01") > 200
        assert schnappschuss.alter_in_tagen("neulich") is None


def test_der_mitgelieferte_stand_laesst_sich_lesen():
    """Die Datei im Projekt ist die letzte Abschrift von festivalticker —
    sie lässt sich nicht mehr auffrischen, also muss sie lesbar bleiben."""
    funde, datum = schnappschuss.lesen("festivalticker")
    assert len(funde) > 1000, "der mitgebrachte Stand fehlt oder ist leer"
    assert datum, "ohne Datum lässt sich sein Alter nicht beurteilen"
    assert all(f.quelle == "festivalticker" and f.name for f in funde)
