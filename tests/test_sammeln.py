"""Der Ablauf des Sammellaufs — nicht die Kunst der einzelnen Quelle.

Geprüft wird hier, was `sammeln.py` selbst entscheidet: dass ein Parsefehler
das Festival kostet und nicht den Lauf, dass eine schweigende Quelle ihren
mitgebrachten Stand bekommt — und dass ein Lauf, der jede Seite von der Platte
nimmt, diesen Stand nicht neu datiert.
"""

from datetime import date

import pytest

from festivalfinder import sammeln
from festivalfinder.kern.fund import fund
from festivalfinder.quellen import Quelle
from festivalfinder.werkzeug import schnappschuss

from .conftest import StillerAbrufer


class Verzeichnis(Quelle):
    """Eine erfundene Quelle mit zwei Detailseiten."""

    name = "festivalticker"          # eine Quelle mit mitgebrachtem Stand
    startseite = "https://ft.test/"

    def __init__(self, seiten=("a", "b"), kaputt=()):
        self.seiten = list(seiten)
        self.kaputt = set(kaputt)

    def adressen(self, netz, seit):
        return [f"https://ft.test/{s}" for s in self.seiten]

    def lesen(self, netz, url, html):
        kennung = url.rsplit("/", 1)[-1]
        if kennung in self.kaputt:
            raise ValueError("Aufbau geändert")
        return fund(self.name, url, f"Fest {kennung}",
                    von=date(2026, 6, 1), stadt="Kiel", land="DE")


@pytest.fixture
def ordner(tmp_path, monkeypatch):
    monkeypatch.setattr(schnappschuss, "ORDNER", tmp_path / "schnappschuss")


def netz_mit(seiten):
    return StillerAbrufer({f"https://ft.test/{s}": "<html>x</html>"
                           for s in seiten})


class TestEinlesen:
    def test_ein_parsefehler_kostet_das_festival_nicht_den_lauf(self, ordner):
        netz = netz_mit(["a", "b"])
        quelle = Verzeichnis(kaputt=["a"])
        funde, ergebnis = sammeln.funde_sammeln(netz, 2026, quellen=[quelle])
        assert [f.name for f in funde] == ["Fest b"]
        assert ergebnis.parsefehler == {"festivalticker": 1}

    def test_eine_seite_ohne_antwort_wird_uebergangen(self, ordner):
        netz = netz_mit(["a"])                     # b antwortet nicht
        funde, _ = sammeln.funde_sammeln(netz, 2026, quellen=[Verzeichnis()])
        assert [f.name for f in funde] == ["Fest a"]


class TestMitgebrachterStand:
    def test_eine_schweigende_quelle_bekommt_ihren_stand(self, ordner):
        schnappschuss.schreiben("festivalticker", [
            fund("festivalticker", "https://ft.test/alt", "Fest alt")])
        netz = netz_mit([])                        # keine Seite antwortet
        funde, ergebnis = sammeln.funde_sammeln(netz, 2026,
                                                quellen=[Verzeichnis()])
        assert [f.name for f in funde] == ["Fest alt"]
        assert ergebnis.mitgebracht == {"festivalticker": date.today().isoformat()}

    def test_ein_lauf_aus_dem_zwischenspeicher_datiert_nichts_um(self, ordner):
        """Der Zwischenspeicher liefert die Seiten weiter, auch wenn die Quelle
        den Lauf längst abweist. Dass sie geantwortet hätte, darf daraus nicht
        werden: Sonst trägt der Stand jeden Tag das heutige Datum, und die
        Alterswarnung verstummt für immer."""
        schnappschuss.schreiben("festivalticker", [
            fund("festivalticker", "https://ft.test/a", "Fest a")])
        alt = "2026-01-15"
        _stand_setzen(alt)

        netz = netz_mit(["a", "b"])                # kommt alles von der Platte
        sammeln.funde_sammeln(netz, 2026, quellen=[Verzeichnis()])
        assert schnappschuss.stand_von("festivalticker") == alt

    def test_eine_quelle_die_wirklich_antwortet_datiert_neu(self, ordner):
        schnappschuss.schreiben("festivalticker", [
            fund("festivalticker", "https://ft.test/a", "Fest a")])
        _stand_setzen("2026-01-15")

        netz = netz_mit(["a", "b"])
        netz.geholt["ft.test"] = 2                 # zwei Seiten kamen frisch
        sammeln.funde_sammeln(netz, 2026, quellen=[Verzeichnis()])
        assert schnappschuss.stand_von("festivalticker") == date.today().isoformat()


def _stand_setzen(datum: str) -> None:
    """Den abgelegten Stand künstlich altern lassen."""
    import gzip
    import json
    p = schnappschuss.datei("festivalticker")
    inhalt = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    inhalt["stand"] = datum
    p.write_bytes(gzip.compress(json.dumps(inhalt).encode("utf-8")))
