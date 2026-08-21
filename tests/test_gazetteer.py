"""Welche Postleitzahlen die Seite mitbekommt — und welche sie nachlädt."""

from build_gazetteer import kurze_codes


def eintrag(code, cc):
    return [code, "Musterstadt", 50.0, 8.0, cc]


def test_vierstellige_laender_werden_erkannt():
    alle = [eintrag("1012", "NL"), eintrag("2000", "BE"), eintrag("75001", "FR")]
    assert kurze_codes(alle) == {"NL", "BE"}


def test_ein_langer_code_zaehlt_fuers_ganze_land():
    # Frankreich hat fünfstellige Codes - dort antwortet Nominatim zuverlässig
    alle = [eintrag("7500", "FR"), eintrag("75001", "FR")]
    assert kurze_codes(alle) == set()


def test_buchstabencodes_zaehlen_nach_laenge():
    # Großbritannien führt Bezirkscodes wie "SW1A"
    assert kurze_codes([eintrag("SW1A", "GB")]) == {"GB"}


def test_ohne_daten_kein_land():
    assert kurze_codes([]) == set()
