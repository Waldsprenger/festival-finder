"""Die Ausgabeprüfung von build_site: Was nicht stimmt, darf nicht raus."""

import pytest

from build_site import pruefe_zeilen


def zeile(**rest):
    grund = dict(name="Testival", von="2026-06-01", bis="2026-06-02", ort="Kiel",
                 land="DE", venue="", eur=45.0, preis="45 €", web="", lat=54.3,
                 lon=10.1, lineup=[0], hinweis="", abgesagt=0, genres=[0])
    grund.update(rest)
    return [grund["name"], grund["von"], grund["bis"], grund["ort"], grund["land"],
            grund["venue"], grund["eur"], grund["preis"], grund["web"], grund["lat"],
            grund["lon"], grund["lineup"], grund["hinweis"], grund["abgesagt"],
            grund["genres"]]


BANDS = ["Powerwolf"]
GENRES = ["rock"]


def test_saubere_zeile_geht_durch():
    pruefe_zeilen([zeile()], BANDS, GENRES)


@pytest.mark.parametrize("kaputt,text", [
    ({"name": ""}, "ohne Namen"),
    ({"lineup": [7]}, "Bandnummer"),
    ({"genres": [3]}, "Genrenummer"),
    ({"lon": None}, "Koordinatenhälfte"),
    ({"eur": 99999.0}, "unplausibel"),
])
def test_fehler_brechen_ab(kaputt, text):
    with pytest.raises(ValueError, match=text):
        pruefe_zeilen([zeile(**kaputt)], BANDS, GENRES)


def test_falsche_spaltenzahl():
    with pytest.raises(ValueError, match="15 Spalten"):
        pruefe_zeilen([zeile()[:12]], BANDS, GENRES)
