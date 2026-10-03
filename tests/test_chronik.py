"""Ein Strich je Monat — und was er nebenbei am Leben hält.

Die Chronik ist die einzige mitversionierte Spur der Läufe: `data/lauf.json`
beschreibt nur den letzten und wird bei jedem überschrieben. Dass ihr Commit
zugleich verhindert, dass GitHub den Zeitplan nach 60 Tagen ohne
Schreibvorgang abschaltet, ist die Folge davon — nicht der Zweck. Deshalb muss
sie genau einmal im Monat schreiben: öfter wäre Lärm, seltener wirkungslos.
"""

import json

import pytest

from festivalfinder.werkzeug import chronik


LAUF = {"stand": "2026-08-23T04:41+0200", "festivals": 13338,
        "quellen": {"festivalticker": 1971, "jambase": 2348},
        "warnungen": ["festivalticker: mitgebrachter Stand ist 30 Tage alt"]}


@pytest.fixture(autouse=True)
def eigene_datei(tmp_path, monkeypatch):
    monkeypatch.setattr(chronik, "DATEI", tmp_path / "chronik.jsonl")
    return tmp_path


class TestNachtragen:
    def test_die_erste_zeile_entsteht(self):
        assert chronik.nachtragen(LAUF, 86266, heute="2026-08-23") is True
        assert chronik.zeilen() == [{
            "monat": "2026-08", "stand": "2026-08-23T04:41+0200",
            "festivals": 13338, "acts": 86266,
            "quellen": {"festivalticker": 1971, "jambase": 2348},
            "warnungen": ["festivalticker: mitgebrachter Stand ist 30 Tage alt"]}]

    def test_derselbe_monat_schreibt_kein_zweites_mal(self):
        """Sonst stünde in der Versionsgeschichte jeden Tag ein Commit."""
        chronik.nachtragen(LAUF, 86266, heute="2026-08-23")
        assert chronik.nachtragen(LAUF, 86266, heute="2026-08-31") is False
        assert len(chronik.zeilen()) == 1

    def test_der_naechste_monat_kommt_dazu(self):
        chronik.nachtragen(LAUF, 86266, heute="2026-08-23")
        assert chronik.nachtragen(LAUF, 90000, heute="2026-09-01") is True
        assert [z["monat"] for z in chronik.zeilen()] == ["2026-08", "2026-09"]

    def test_ein_uebersprungener_monat_reisst_kein_loch(self):
        """Läuft der Zeitplan zwei Monate nicht, fehlen die Monate — die
        Reihenfolge bleibt trotzdem."""
        for tag in ("2026-08-23", "2026-11-02", "2026-09-15"):
            chronik.nachtragen(LAUF, 86266, heute=tag)
        assert [z["monat"] for z in chronik.zeilen()] == \
            ["2026-08", "2026-09", "2026-11"]

    def test_die_warnungen_des_monats_stehen_dabei(self):
        """Ohne sie stünde später eine niedrige Zahl da, ohne dass jemand
        wüsste, warum."""
        chronik.nachtragen(LAUF, 86266, heute="2026-08-23")
        assert chronik.zeilen()[0]["warnungen"]

    def test_eine_ruhende_quelle_steht_mit_grund_dabei(self):
        """Unter „quellen" fehlt sie; ohne Grund sähe das aus wie ein Ausfall."""
        lauf = dict(LAUF, ruhend={"festivalnetworks": "verlangt ein Zeichen"})
        chronik.nachtragen(lauf, 86266, heute="2026-10-01")
        assert chronik.zeilen()[0]["ruhend"] == \
            {"festivalnetworks": "verlangt ein Zeichen"}

    def test_die_monatliche_pruefung_steht_dabei(self):
        lauf = dict(LAUF, ruhend={"festivalnetworks": "verlangt ein Zeichen"},
                    ruhend_geprueft={"festivalnetworks": False})
        chronik.nachtragen(lauf, 86266, heute="2026-11-01")
        assert chronik.zeilen()[0]["ruhend_geprueft"] == {"festivalnetworks": False}

    def test_steht_schon_kennt_den_monat(self):
        """Daran hängt, ob ruhende Quellen geprüft werden."""
        assert chronik.steht_schon("2026-10-01") is False
        chronik.nachtragen(LAUF, 86266, heute="2026-10-01")
        assert chronik.steht_schon("2026-10-31") is True
        assert chronik.steht_schon("2026-11-01") is False


class TestRobust:
    def test_ohne_datei_gibt_es_keine_zeilen(self):
        assert chronik.zeilen() == []

    def test_eine_zerrissene_zeile_haelt_nichts_auf(self):
        """Ein abgebrochener Schreibvorgang darf nicht jeden weiteren Lauf
        scheitern lassen."""
        chronik.DATEI.write_text('{"monat":"2026-07"}\n{kaputt\n',
                                 encoding="utf-8")
        assert [z["monat"] for z in chronik.zeilen()] == ["2026-07"]
        assert chronik.nachtragen(LAUF, 86266, heute="2026-08-23") is True
        assert [z["monat"] for z in chronik.zeilen()] == ["2026-07", "2026-08"]

    def test_jede_zeile_bleibt_fuer_sich_lesbar(self):
        """Zeilenweises JSON: Wer die Datei anschaut, soll sie lesen können,
        und ein Diff soll den neuen Monat als eine Zeile zeigen."""
        chronik.nachtragen(LAUF, 86266, heute="2026-08-23")
        chronik.nachtragen(LAUF, 86266, heute="2026-09-01")
        roh = chronik.DATEI.read_text(encoding="utf-8")
        assert roh.endswith("\n")
        for zeile in roh.splitlines():
            assert json.loads(zeile)["monat"]
