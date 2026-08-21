"""Preise über die Zeit: Was war es zuerst, was ist es heute?"""

import json

import preisverlauf
import pytest


def festival(preis, name="Testival", jahr="2026", stadt="Kiel"):
    return {"name": name, "year": jahr, "city": stadt, "price": preis,
            "price_start": "", "price_start_seit": ""}


@pytest.fixture
def datei(tmp_path, monkeypatch):
    ziel = tmp_path / "preis_verlauf.json"
    monkeypatch.setattr(preisverlauf, "DATEI", ziel)
    return ziel


def test_erster_lauf_merkt_sich_den_preis(datei):
    f = festival("VVK 89 €")
    preisverlauf.verfolgen([f], heute="2026-08-21")
    assert f["price_start"] == ""            # noch keine Änderung
    assert json.loads(datei.read_text(encoding="utf-8"))["testival|2026|kiel"] == {
        "erst": "VVK 89 €", "seit": "2026-08-21",
        "aktuell": "VVK 89 €", "stand": "2026-08-21"}


def test_gestiegener_preis_nennt_den_start(datei):
    preisverlauf.verfolgen([festival("VVK 89 €")], heute="2026-08-21")
    f = festival("VVK 129 €")
    preisverlauf.verfolgen([f], heute="2026-09-15")
    assert f["price_start"] == "VVK 89 €"
    assert f["price_start_seit"] == "2026-08-21"


def test_der_start_bleibt_der_start(datei):
    preisverlauf.verfolgen([festival("VVK 89 €")], heute="2026-08-21")
    preisverlauf.verfolgen([festival("VVK 129 €")], heute="2026-09-15")
    f = festival("VVK 149 €")
    preisverlauf.verfolgen([f], heute="2026-10-01")
    assert f["price_start"] == "VVK 89 €"     # nicht 129
    assert f["price_start_seit"] == "2026-08-21"


def test_unveraenderter_preis_bleibt_ohne_zusatz(datei):
    preisverlauf.verfolgen([festival("VVK 89 €")], heute="2026-08-21")
    f = festival("VVK 89 €")
    preisverlauf.verfolgen([f], heute="2026-09-15")
    assert f["price_start"] == ""


def test_ein_fehlendes_festival_bleibt_erst_einmal_stehen(datei):
    # An dem Tag, an dem eine Quelle den Lauf abwies, fehlten 800 Festivals auf
    # einmal. Ihre Geschichte zu löschen hiesse, den Startpreis zu vergessen.
    preisverlauf.verfolgen([festival("89 €", name="Altfest")], heute="2026-08-21")
    preisverlauf.verfolgen([festival("89 €", name="Neufest")], heute="2026-08-22")
    verlauf = json.loads(datei.read_text(encoding="utf-8"))
    assert sorted(verlauf) == ["altfest|2026|kiel", "neufest|2026|kiel"]


def test_nach_zwei_monaten_faellt_es_heraus(datei):
    preisverlauf.verfolgen([festival("89 €", name="Altfest")], heute="2026-06-01")
    preisverlauf.verfolgen([festival("89 €", name="Neufest")], heute="2026-08-22")
    verlauf = json.loads(datei.read_text(encoding="utf-8"))
    assert list(verlauf) == ["neufest|2026|kiel"]


def test_der_startpreis_ueberlebt_eine_luecke(datei):
    preisverlauf.verfolgen([festival("89 €")], heute="2026-06-01")
    preisverlauf.verfolgen([], heute="2026-06-02")            # Quelle schweigt
    fest = festival("99 €")
    preisverlauf.verfolgen([fest], heute="2026-06-03")
    assert fest["price_start"] == "89 €"
    assert fest["price_start_seit"] == "2026-06-01"


def test_festivals_ohne_preis_stehen_nicht_drin(datei):
    preisverlauf.verfolgen([festival("")], heute="2026-08-21")
    assert json.loads(datei.read_text(encoding="utf-8")) == {}


def test_jahrgaenge_werden_getrennt_gefuehrt(datei):
    a = festival("89 €", jahr="2026")
    b = festival("99 €", jahr="2027")
    zahlen = preisverlauf.verfolgen([a, b], heute="2026-08-21")
    assert zahlen["beobachtet"] == 2


def test_zaehlt_die_aenderungen(datei):
    preisverlauf.verfolgen([festival("89 €")], heute="2026-08-21")
    zahlen = preisverlauf.verfolgen([festival("129 €")], heute="2026-09-15")
    assert zahlen["geändert"] == 1
