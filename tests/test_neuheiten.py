"""Seit wann kennen wir das? — die Grundlage für „was ist neu".

Zwei Arten von Neuigkeit: ein Festival, das es vorher nicht gab, und eine
Band, die bei einem bekannten Festival dazukommt. Aufgezeichnet wird nicht,
*was wann passiert ist*, sondern *seit wann wir etwas kennen* — deshalb gibt es
keine Rückblickgrenze: Wer nach vierzig Tagen wiederkommt, bekommt vierzig
Tage, wer nach einem halben Jahr wiederkommt, ein halbes Jahr.

Dazu zwei Ruheregeln: Der erste Lauf meldet nichts, und eine Quelle, die einen
Tag schweigt, macht ihre Festivals nicht neu.
"""

import json

import pytest

from festivalfinder.kern.festival import Festival
from festivalfinder.werkzeug import neuheiten


def fest(name="Testival", bands=(), jahr="2026", stadt="Kiel"):
    return Festival(name=name, jahr=jahr, stadt=stadt,
                    bands={b.lower(): b for b in bands})


@pytest.fixture(autouse=True)
def eigene_datei(tmp_path, monkeypatch):
    monkeypatch.setattr(neuheiten, "DATEI", tmp_path / "bestand_verlauf.json")
    return tmp_path


def roh():
    return json.loads(neuheiten.DATEI.read_text(encoding="utf-8"))


def zugaenge(f):
    return neuheiten.zugaenge(neuheiten.lesen(), f.kennung)


class TestErsterLauf:
    def test_er_meldet_nichts(self):
        """Sonst wären beim ersten Mal alle 13.338 Festivals neu."""
        zahlen = neuheiten.verfolgen([fest(), fest(name="Zweitival")],
                                     heute="2026-08-24")
        assert (zahlen["festivals"], zahlen["bands"]) == (0, 0)
        assert zugaenge(fest()) == ("", {})

    def test_der_anfangsbestand_bleibt_stumm_auch_spaeter(self):
        """Der Beginn der Aufzeichnung steht in der Datei — was dieses Datum
        trägt, gilt dauerhaft als „schon immer da"."""
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-24")
        for tag in ("2026-09-01", "2027-02-01"):
            neuheiten.verfolgen([fest(bands=["Ghost"])], heute=tag)
        assert roh()["beginn"] == "2026-08-24"
        assert zugaenge(fest()) == ("", {})


class TestNeueFestivals:
    def test_ein_neues_festival_bekommt_sein_datum(self):
        neuheiten.verfolgen([fest()], heute="2026-08-24")
        zahlen = neuheiten.verfolgen([fest(), fest(name="Neufest")],
                                     heute="2026-08-25")
        assert zahlen["festivals"] == 1
        seit, bands = zugaenge(fest(name="Neufest"))
        assert seit == "2026-08-25"
        assert bands == {}, "beim ersten Sehen ist das Lineup keine eigene Meldung"

    def test_sein_lineup_zaehlt_nicht_zusaetzlich(self):
        """Wer beim ersten Sehen schon dabei war, ist keine eigene Neuigkeit —
        sonst stünde jedes neue Festival zweimal da."""
        neuheiten.verfolgen([fest()], heute="2026-08-24")
        neuheiten.verfolgen([fest(), fest(name="Neufest", bands=["Ghost", "Kadavar"])],
                            heute="2026-08-25")
        assert zugaenge(fest(name="Neufest")) == ("2026-08-25", {})

    def test_das_datum_bleibt_stehen(self):
        neuheiten.verfolgen([fest()], heute="2026-08-24")
        for tag in ("2026-08-25", "2026-09-30"):
            neuheiten.verfolgen([fest(), fest(name="Neufest")], heute=tag)
        assert zugaenge(fest(name="Neufest"))[0] == "2026-08-25"


class TestBestaetigteBands:
    def test_eine_neue_band_bei_einem_bekannten_festival(self):
        """Wacken kennt jeder — interessant wird es, wenn dort Powerwolf
        dazukommt."""
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-24")
        zahlen = neuheiten.verfolgen([fest(bands=["Ghost", "Powerwolf"])],
                                     heute="2026-08-25")
        assert zahlen["bands"] == 1
        assert zugaenge(fest()) == ("", {"Powerwolf": "2026-08-25"})

    def test_ein_unveraendertes_lineup_meldet_nichts(self):
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-24")
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-25")
        assert zugaenge(fest()) == ("", {})

    def test_eine_abgesagte_band_meldet_nichts(self):
        """Aufgezeichnet werden Zugänge. Ein Abgang ist keine Neuigkeit, für
        die jemand geweckt werden will."""
        neuheiten.verfolgen([fest(bands=["Ghost", "Powerwolf"])], heute="2026-08-24")
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-25")
        assert zugaenge(fest()) == ("", {})

    def test_wer_wiederkommt_behaelt_sein_erstes_datum(self):
        """Eine Band, die aus einem Lauf herausfällt und im nächsten wieder
        dasteht, ist keine neue Bestätigung."""
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-24")
        neuheiten.verfolgen([fest(bands=["Ghost", "Powerwolf"])], heute="2026-09-01")
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-09-02")
        neuheiten.verfolgen([fest(bands=["Ghost", "Powerwolf"])], heute="2026-09-03")
        assert zugaenge(fest())[1] == {"Powerwolf": "2026-09-03"}


class TestOhneRueckblickgrenze:
    def test_auch_nach_einem_halben_jahr_stimmt_das_datum_noch(self):
        """Die Seite wird über den Winter oft aufgerufen und im Frühling
        selten. Wer nach vierzig Tagen wiederkommt, soll die Änderungen aus
        vierzig Tagen sehen — nicht nichts, weil ein Fenster abgelaufen ist."""
        neuheiten.verfolgen([fest()], heute="2026-01-01")
        neuheiten.verfolgen([fest(), fest(name="Neufest")], heute="2026-02-15")
        for tag in ("2026-04-01", "2026-06-01", "2026-08-01"):
            neuheiten.verfolgen([fest(), fest(name="Neufest")], heute=tag)
        assert zugaenge(fest(name="Neufest"))[0] == "2026-02-15"

    def test_die_datei_waechst_nicht_mit_den_jahren(self):
        """Begrenzt wird über den Bestand, nicht über die Zeit: Was aus allen
        Quellen verschwunden ist, fliegt heraus."""
        dauerhaft = fest(name="Dauerfest")
        neuheiten.verfolgen([dauerhaft] + [fest(name=f"Alt{i}") for i in range(5)],
                            heute="2026-01-01")
        assert len(roh()["feste"]) == 6
        neuheiten.verfolgen([dauerhaft], heute="2026-02-15")
        zahlen = neuheiten.verfolgen([dauerhaft], heute="2026-03-31")
        assert zahlen["bekannt"] == 1

    def test_ein_lauf_nach_langer_pause_urteilt_nicht(self):
        """GitHub schaltet zeitgesteuerte Läufe nach 60 Tagen ohne Aktivität
        ab. Wird danach wieder gesammelt, ist der Bestand nicht neu — es hat
        nur niemand gefragt."""
        alle = [fest(), fest(name="Zweit"), fest(name="Dritt")]
        neuheiten.verfolgen(alle, heute="2026-01-01")
        zahlen = neuheiten.verfolgen(alle, heute="2026-05-01")   # 120 Tage Pause
        assert (zahlen["festivals"], zahlen["bekannt"]) == (0, 3)
        assert zugaenge(fest()) == ("", {})


class TestRuhe:
    def test_eine_quelle_die_einen_tag_schweigt_macht_nichts_neu(self):
        """An dem Tag, an dem festivalticker den Serverlauf abwies, fehlten
        1.900 Festivals auf einmal."""
        neuheiten.verfolgen([fest(), fest(name="Zweit")], heute="2026-08-24")
        neuheiten.verfolgen([fest(name="Zweit")], heute="2026-08-25")
        zahlen = neuheiten.verfolgen([fest(), fest(name="Zweit")], heute="2026-08-26")
        assert zahlen["festivals"] == 0
        assert zugaenge(fest()) == ("", {})

    def test_nach_zwei_monaten_gilt_es_doch_als_neu(self):
        """Länger als die Geduld weg heißt: Es kommt wieder, nicht: Es war die
        ganze Zeit da."""
        dauerhaft = fest(name="Dauerfest")
        neuheiten.verfolgen([fest(), dauerhaft], heute="2026-01-01")
        neuheiten.verfolgen([dauerhaft], heute="2026-06-01")
        zahlen = neuheiten.verfolgen([fest(), dauerhaft], heute="2026-06-02")
        assert zahlen["festivals"] == 1
        assert zugaenge(fest())[0] == "2026-06-02"
