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
from festivalfinder.werkzeug import chronik, schnappschuss

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


class Ruhend(Verzeichnis):
    """Eine Quelle, die ruht — und bei der Prüfung antwortet, wie man sie lässt."""

    ruht = "verlangt ein Zugangszeichen"

    def __init__(self, offen=None):
        super().__init__()
        self.offen = offen
        self.geprueft = 0

    def wieder_offen(self, netz, seit):
        self.geprueft += 1
        if isinstance(self.offen, Exception):
            raise self.offen
        return self.offen


class TestRuhendeQuelle:
    def test_sie_wird_nicht_gefragt_und_zaehlt_nicht(self, ordner):
        """Keine Anfrage, keine Null in den Funden — sonst stünde jeden Tag
        „kein einziger Fund" im Bericht, obwohl das Schweigen gewollt ist."""
        netz = netz_mit(["a", "b"])
        quelle = Ruhend(offen=True)
        funde, ergebnis = sammeln.funde_sammeln(netz, 2026, quellen=[quelle],
                                                pruefen=False)
        assert funde == [] and netz.gefragt == [] and quelle.geprueft == 0
        assert ergebnis.ruhend == {"festivalticker": "verlangt ein Zugangszeichen"}
        assert "festivalticker" not in ergebnis.funde
        assert ergebnis.geprueft == {}

    def test_bei_der_pruefung_wird_nachgesehen(self, ordner):
        """Was die Prüfung bringt, fließt nicht in den Bestand."""
        quelle = Ruhend(offen=True)
        funde, ergebnis = sammeln.funde_sammeln(netz_mit(["a"]), 2026,
                                                quellen=[quelle], pruefen=True)
        assert quelle.geprueft == 1 and funde == []
        assert ergebnis.geprueft == {"festivalticker": True}

    def test_weiter_gesperrt_steht_auch_da(self, ordner):
        _, ergebnis = sammeln.funde_sammeln(netz_mit([]), 2026,
                                            quellen=[Ruhend(offen=False)],
                                            pruefen=True)
        assert ergebnis.geprueft == {"festivalticker": False}

    def test_eine_gescheiterte_pruefung_heisst_nicht_gesperrt(self, ordner):
        netz = netz_mit([])
        _, ergebnis = sammeln.funde_sammeln(
            netz, 2026, quellen=[Ruhend(offen=ValueError("kaputt"))], pruefen=True)
        assert ergebnis.geprueft == {}
        assert any("Prüfung gescheitert" in m for m in netz.meldungen)

    def test_ohne_angabe_prueft_der_erste_lauf_des_monats(self, ordner, tmp_path,
                                                         monkeypatch):
        """Takt ist die Chronik: Fehlt die Zeile des Monats, wird geprüft."""
        monkeypatch.setattr(chronik, "DATEI", tmp_path / "chronik.jsonl")
        quelle = Ruhend(offen=False)
        sammeln.funde_sammeln(netz_mit([]), 2026, quellen=[quelle])
        assert quelle.geprueft == 1

        chronik.nachtragen({"quellen": {}}, 0)
        sammeln.funde_sammeln(netz_mit([]), 2026, quellen=[quelle])
        assert quelle.geprueft == 1


def _stand_setzen(datum: str) -> None:
    """Den abgelegten Stand künstlich altern lassen."""
    import gzip
    import json
    p = schnappschuss.datei("festivalticker")
    inhalt = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    inhalt["stand"] = datum
    p.write_bytes(gzip.compress(json.dumps(inhalt).encode("utf-8")))
