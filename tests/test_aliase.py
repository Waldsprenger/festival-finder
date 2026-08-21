"""Kürzel, die eine andere Band meinen — und die Tabelle, die sich dabei ändert.

„TBS" und The Butcher Sisters sind dasselbe; „LP" und Linkin Park nicht — das
ist die Sängerin LP. Entscheidend ist, ob Kürzel und ausgeschriebener Name je
gemeinsam auf einem Plakat stehen.

Der zweite Teil ist heikler: `alias_kollisionen` schaltet Kürzel im Modul ab.
Dieselbe Funktion `band_key` antwortet danach anders, ohne dass sich an den
Daten etwas geändert hat. Diese Tests halten fest, dass das nur innerhalb eines
Laufs gilt und nicht von einem Test zum nächsten durchschlägt.
"""

import text
from quellen import datensatz
from zusammenfuehren import alias_kollisionen


def fund(nr, name, lineup, jahr="2026"):
    return datensatz("festivalticker", f"https://x/{nr}", name,
                     date_from=f"01.06.{jahr}", city="Kiel", lineup=lineup)


def test_kuerzel_neben_dem_vollen_namen_bleibt_ein_alias():
    # Beide Schreibweisen auf demselben Plakat: dieselbe Band, zweimal genannt
    funde = [fund(1, "Testival", ["TBS", "The Butcher Sisters"])]
    assert alias_kollisionen(funde) == []
    assert text.band_key("TBS") == text.band_key("The Butcher Sisters")


def test_kuerzel_allein_im_programm_wird_abgeschaltet():
    funde = [fund(1, "Testival", ["TBS", "Powerwolf"])]
    assert alias_kollisionen(funde) == ["tbs"]
    assert text.band_key("TBS") != text.band_key("The Butcher Sisters")


def test_die_tabelle_ist_im_naechsten_test_wieder_vollstaendig():
    # Steht absichtlich nach dem Test, der abschaltet: Ohne die Rückstellung
    # in conftest.py schlüge dieser hier fehl - je nach Reihenfolge.
    assert "tbs" in text.ALIAS_KEY
    assert text.band_key("TBS") == text.band_key("The Butcher Sisters")


def test_geprueft_wird_je_festival_nicht_je_seite():
    # Die beiden Schreibweisen stehen oft auf Seiten verschiedener Quellen und
    # treffen sich erst im zusammengeführten Programm.
    funde = [fund(1, "Testival", ["TBS"]),
             fund(2, "Testival", ["The Butcher Sisters"])]
    assert alias_kollisionen(funde) == []


def test_verschiedene_jahrgaenge_zaehlen_getrennt():
    funde = [fund(1, "Testival", ["TBS"], jahr="2026"),
             fund(2, "Testival", ["The Butcher Sisters"], jahr="2027")]
    assert alias_kollisionen(funde) == ["tbs"]


def test_zuruecksetzen_stellt_alles_wieder_her():
    vorher = dict(text.ALIAS_KEY)
    text.alias_abschalten("tbs")
    assert "tbs" not in text.ALIAS_KEY
    text.aliase_zuruecksetzen()
    assert text.ALIAS_KEY == vorher


def test_zuruecksetzen_behaelt_dieselbe_tabelle():
    # Andere Module binden die Tabelle unter ihrem Namen ein; sie darf deshalb
    # geleert und neu gefüllt, aber nicht ersetzt werden.
    dieselbe = text.ALIAS_KEY
    text.aliase_zuruecksetzen()
    assert text.ALIAS_KEY is dieselbe
