"""Länder und Koordinaten.

Der Kasten je Land fängt zwei Arten von Unsinn ab: einen Punkt, den es auf der
Erde nicht gibt, und einen, der nicht zu dem Land passt, das die Quelle nennt.
"""

import pytest

from festivalfinder.kern.orte import (FEINRAHMEN, ISO_CODES, ist_land,
                                      kontinent, land_code, punkt_plausibel,
                                      punkt_passt_zum_land, zahl_oder_nichts)


class TestLandCode:
    @pytest.mark.parametrize("angabe,code", [
        ("Deutschland", "DE"), ("germany", "DE"), ("BRD", "DE"), ("de", "DE"),
        ("England", "GB"), ("United Kingdom", "GB"),
        ("Japan", "JP"), ("USA", "US"), ("Südafrika", "ZA"),
    ])
    def test_schreibweisen_werden_zum_kuerzel(self, angabe, code):
        assert land_code(angabe) == code

    def test_unbekanntes_bleibt_stehen(self):
        assert land_code("Bayern") == "Bayern"
        assert land_code("") == ""

    def test_zwei_buchstaben_gelten_als_kuerzel(self):
        assert land_code("br") == "BR"


class TestIstLand:
    @pytest.mark.parametrize("angabe", ["Japan", "BR", "DE", "Neuseeland"])
    def test_staaten(self, angabe):
        assert ist_land(angabe)

    @pytest.mark.parametrize("angabe", ["Bayern", "Region Hannover", "", "XX"])
    def test_keine_staaten(self, angabe):
        assert not ist_land(angabe)

    def test_die_welt_ist_dabei(self):
        """Früher hieß die Frage „liegt das in Europa?"."""
        assert len(ISO_CODES) > 200


class TestKontinent:
    def test_erdteile(self):
        assert kontinent("DE") == "EU"
        assert kontinent("JP") == "AS"
        assert kontinent("Bayern") == ""


class TestPunktPlausibel:
    @pytest.mark.parametrize("lat,lon,gut", [
        (52.5, 13.4, True),
        (0, 0, False),            # Golf von Guinea: „kein Wert eingetragen"
        (0.005, -0.004, False),
        (91, 13.4, False),
        (52.5, 181, False),
        (None, 13.4, False),
    ])
    def test_ein_punkt_auf_der_erde(self, lat, lon, gut):
        assert punkt_plausibel(lat, lon) is gut


class TestPunktZumLand:
    @pytest.mark.parametrize("lat,lon,land,passt", [
        (46.00, 8.95, "CH", True),        # Lugano
        (-34.69, -58.50, "CH", False),    # Buenos Aires für Lugano
        (52.50, 13.40, "DE", True),       # Berlin
        (41.87, -87.62, "DE", False),     # Chicago für Berlin
        (28.10, -15.46, "ES", True),      # Las Palmas gehört zu Spanien
        (32.64, -16.91, "PT", True),      # Funchal gehört zu Portugal
        (35.65, 139.70, "JP", True),
        (52.51, 13.45, "HU", False),      # Berlin für Budapest
        (41.87, -87.62, "", True),        # ohne Land wird nicht geraten
        (41.87, -87.62, "Bayern", True),  # ohne Kasten auch nicht
    ])
    def test_kasten_des_landes(self, lat, lon, land, passt):
        assert punkt_passt_zum_land(lat, lon, land) is passt


class TestZahlOderNichts:
    def test_datenblaetter_liefern_beides(self):
        assert zahl_oder_nichts("47.47") == 47.47
        assert zahl_oder_nichts(47.47) == 47.47
        assert zahl_oder_nichts(None) is None
        assert zahl_oder_nichts("keine") is None


def test_der_feine_kartenausschnitt_ist_ein_rechteck():
    lat0, lat1, lon0, lon1 = FEINRAHMEN
    assert lat0 < lat1 and lon0 < lon1
    assert -90 <= lat0 and lat1 <= 90
