"""Das Tagebuch der Neuzugänge.

Zwei Arten von Neuigkeit — ein Festival, das es gestern nicht gab, und eine
Band, die bei einem bekannten Festival dazukommt. Und zwei Ruheregeln, ohne
die das Tagebuch nur Lärm macht: Der erste Lauf meldet nichts, und eine
Quelle, die einen Tag schweigt, macht ihre Festivals nicht neu.
"""

import json

import pytest

from festivalfinder.kern.festival import Festival
from festivalfinder.werkzeug import neuheiten


def fest(name="Testival", bands=(), jahr="2026", stadt="Kiel"):
    return Festival(name=name, jahr=jahr, stadt=stadt,
                    bands={b.lower(): b for b in bands})


@pytest.fixture(autouse=True)
def eigene_dateien(tmp_path, monkeypatch):
    monkeypatch.setattr(neuheiten, "ZUSTAND", tmp_path / "bestand_verlauf.json")
    monkeypatch.setattr(neuheiten, "TAGEBUCH", tmp_path / "neuheiten.json")
    return tmp_path


def tagebuch():
    return json.loads(neuheiten.TAGEBUCH.read_text(encoding="utf-8"))


class TestErsterLauf:
    def test_er_meldet_nichts(self):
        """Sonst wären beim ersten Mal alle 13.338 Festivals neu und die
        Meldung wertlos."""
        zahlen = neuheiten.verfolgen([fest(), fest(name="Zweitival")],
                                     heute="2026-08-24")
        assert zahlen == {"festivals": 0, "bands": 0, "tagebuch": 0}
        assert tagebuch() == []

    def test_er_merkt_sich_trotzdem_alles(self):
        neuheiten.verfolgen([fest(bands=["Powerwolf"])], heute="2026-08-24")
        zustand = json.loads(neuheiten.ZUSTAND.read_text(encoding="utf-8"))
        assert zustand["testival|2026|kiel"] == {
            "seit": "2026-08-24", "stand": "2026-08-24", "bands": ["Powerwolf"]}


class TestNeueFestivals:
    def test_ein_neues_festival_kommt_ins_tagebuch(self):
        neuheiten.verfolgen([fest()], heute="2026-08-24")
        zahlen = neuheiten.verfolgen([fest(), fest(name="Neufest")],
                                     heute="2026-08-25")
        assert zahlen["festivals"] == 1
        assert tagebuch() == [{"k": "neufest|2026|kiel", "seit": "2026-08-25",
                               "grund": "neu", "bands": []}]

    def test_sein_ganzes_lineup_gilt_als_neu(self):
        neuheiten.verfolgen([fest()], heute="2026-08-24")
        neuheiten.verfolgen([fest(), fest(name="Neufest", bands=["Ghost", "Kadavar"])],
                            heute="2026-08-25")
        assert tagebuch()[0]["bands"] == ["Ghost", "Kadavar"]

    def test_dasselbe_festival_zweimal_gemeldet_bleibt_einmal(self):
        neuheiten.verfolgen([fest()], heute="2026-08-24")
        neuheiten.verfolgen([fest(), fest(name="Neufest")], heute="2026-08-25")
        neuheiten.verfolgen([fest(), fest(name="Neufest")], heute="2026-08-26")
        assert len(tagebuch()) == 1


class TestBestaetigteBands:
    def test_eine_neue_band_bei_einem_bekannten_festival(self):
        """Wacken kennt jeder — interessant wird es, wenn dort Powerwolf
        dazukommt."""
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-24")
        zahlen = neuheiten.verfolgen([fest(bands=["Ghost", "Powerwolf"])],
                                     heute="2026-08-25")
        assert zahlen["bands"] == 1
        assert tagebuch() == [{"k": "testival|2026|kiel", "seit": "2026-08-25",
                               "grund": "lineup", "bands": ["Powerwolf"]}]

    def test_ein_unveraendertes_lineup_meldet_nichts(self):
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-24")
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-25")
        assert tagebuch() == []

    def test_eine_abgesagte_band_meldet_nichts(self):
        """Das Tagebuch führt Zugänge. Ein Abgang ist keine Neuigkeit, für die
        jemand geweckt werden will."""
        neuheiten.verfolgen([fest(bands=["Ghost", "Powerwolf"])], heute="2026-08-24")
        neuheiten.verfolgen([fest(bands=["Ghost"])], heute="2026-08-25")
        assert tagebuch() == []


class TestRuhe:
    def test_eine_quelle_die_einen_tag_schweigt_macht_nichts_neu(self):
        """An dem Tag, an dem festivalticker den Serverlauf abwies, fehlten
        1.900 Festivals auf einmal."""
        neuheiten.verfolgen([fest()], heute="2026-08-24")
        neuheiten.verfolgen([], heute="2026-08-25")            # Quelle schweigt
        zahlen = neuheiten.verfolgen([fest()], heute="2026-08-26")
        assert zahlen["festivals"] == 0
        assert tagebuch() == []

    def test_nach_zwei_monaten_gilt_es_doch_als_neu(self):
        """Länger als die Geduld weg heißt: Es kommt wieder, nicht: Es war die
        ganze Zeit da."""
        dauerhaft = fest(name="Dauerfest")
        neuheiten.verfolgen([fest(), dauerhaft], heute="2026-01-01")
        for tag in ("2026-01-02", "2026-06-01"):
            zahlen = neuheiten.verfolgen([dauerhaft], heute=tag)
        assert zahlen["festivals"] == 0
        zahlen = neuheiten.verfolgen([fest(), dauerhaft], heute="2026-06-02")
        assert zahlen["festivals"] == 1

    def test_eine_lange_pause_meldet_gar_nichts(self):
        """Ist der letzte Lauf so lange her, dass vom Zustand nichts übrig
        ist, weiß niemand mehr, was in der Zwischenzeit dazukam. Dann wäre
        „alles neu" die einzige Antwort — und die ist keine."""
        neuheiten.verfolgen([fest()], heute="2026-01-01")
        zahlen = neuheiten.verfolgen([fest(), fest(name="Neufest")],
                                     heute="2026-09-01")
        assert zahlen == {"festivals": 0, "bands": 0, "tagebuch": 0}

    def test_das_tagebuch_reicht_dreissig_tage_zurueck(self):
        neuheiten.verfolgen([fest()], heute="2026-01-01")
        neuheiten.verfolgen([fest(), fest(name="Neufest")], heute="2026-01-02")
        assert len(tagebuch()) == 1
        neuheiten.verfolgen([fest(), fest(name="Neufest")], heute="2026-01-25")
        assert len(tagebuch()) == 1, "innerhalb der dreißig Tage"
        neuheiten.verfolgen([fest(), fest(name="Neufest")], heute="2026-03-01")
        assert tagebuch() == [], "danach nicht mehr"
