"""Lesen und Schreiben: Was passiert, wenn ein Lauf mittendrin abbricht?

`data/preis_verlauf.json` und `data/geo.json` stehen nirgends sonst — die eine
trägt die beobachtete Preisgeschichte, die andere rund 2.000 erfragte
Koordinaten. Eine halb geschriebene Datei kostet beides.
"""

import json

import pytest
from gemeinsam import lies_json, schreib_json


def test_hin_und_zurueck(tmp_path):
    ziel = tmp_path / "probe.json"
    schreib_json(ziel, {"a": [1, 2], "ü": "ö"})
    assert lies_json(ziel) == {"a": [1, 2], "ü": "ö"}


def test_fehlende_datei_gibt_den_standard(tmp_path):
    assert lies_json(tmp_path / "gibtsnicht.json", {"leer": True}) == {"leer": True}


def test_nichts_bleibt_liegen(tmp_path):
    ziel = tmp_path / "probe.json"
    schreib_json(ziel, {"a": 1}, kompakt=True)
    assert [p.name for p in tmp_path.iterdir()] == ["probe.json"]


def test_der_alte_stand_bleibt_bis_der_neue_vollstaendig_ist(tmp_path, monkeypatch):
    """Ein Abbruch mitten im Schreiben darf die alte Datei nicht anfassen."""
    ziel = tmp_path / "probe.json"
    schreib_json(ziel, {"alt": True})

    def platzt(*_args, **_kwargs):
        raise KeyboardInterrupt("Abbruch mitten im Schreiben")

    monkeypatch.setattr("os.replace", platzt)
    with pytest.raises(KeyboardInterrupt):
        schreib_json(ziel, {"neu": True})
    assert lies_json(ziel) == {"alt": True}


def test_zerrissene_datei_wird_beiseitegelegt(tmp_path):
    ziel = tmp_path / "probe.json"
    ziel.write_text('{"halb": ', encoding="utf-8")
    assert lies_json(ziel, {"standard": True}) == {"standard": True}
    assert not ziel.exists()
    beiseite = tmp_path / "probe.json.kaputt"
    assert beiseite.exists() and beiseite.read_text(encoding="utf-8") == '{"halb": '


def test_nach_dem_beiseitelegen_laesst_sich_neu_schreiben(tmp_path):
    ziel = tmp_path / "probe.json"
    ziel.write_text("kein JSON", encoding="utf-8")
    lies_json(ziel, {})
    schreib_json(ziel, {"wieder": "da"})
    assert json.loads(ziel.read_text(encoding="utf-8")) == {"wieder": "da"}
