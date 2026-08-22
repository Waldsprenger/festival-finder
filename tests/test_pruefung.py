"""Die Wächter des Laufs: Selbstprüfung und Einbruchsmeldung."""

from datetime import date

import pytest

from festivalfinder import pruefung
from festivalfinder.kern.festival import Festival


def festival(**rest):
    grund = dict(name="Testival", jahr="2026", von=date(2026, 6, 1),
                 bis=date(2026, 6, 2), stadt="Kiel", land="DE",
                 lat=54.3, lon=10.1, quellen={"festivalticker": "https://x/y"})
    return Festival(**{**grund, **rest})


class TestStimmigkeit:
    def test_sauberer_bestand_meldet_nichts(self):
        assert pruefung.stimmigkeit([festival()]) == []

    @pytest.mark.parametrize("kaputt,meldung", [
        ({"name": "  "}, "ohne Namen"),
        ({"quellen": {}}, "ohne Quelle"),
        ({"jahr": "2027"}, "Jahr passt nicht zum Termin"),
        ({"bis": date(2026, 5, 1)}, "Ende vor Anfang"),
        ({"lat": 91.0, "lon": -58.4}, "Koordinate ausserhalb der Erde"),
        ({"besucher": "2.000"}, "Besucherzahl keine Zahl"),
        ({"besucher": "99999999"}, "Besucherzahl unplausibel"),
        ({"land": "Bayern"}, "Land nicht erkannt"),
        ({"stadt": "104 45 Athen"}, "Postleitzahl im Ortsfeld"),
        ({"preis": "Pop Punk"}, "Preis ohne Preis"),
        ({"ort": "Tickets Ticket"}, "Spielstätte ist eine Knopfbeschriftung"),
    ])
    def test_jeder_widerspruch_wird_gemeldet(self, kaputt, meldung):
        gefunden = pruefung.stimmigkeit([festival(**kaputt)])
        assert any(meldung in z for z in gefunden), gefunden

    def test_dublette_faellt_auf(self):
        doppelt = [festival(), festival(quellen={"festivalsunited": "https://a/b"})]
        assert any("Dublette" in z for z in pruefung.stimmigkeit(doppelt))

    def test_zwei_ausgaben_im_jahr_sind_keine_dublette(self):
        """Heartbeatz gibt es im Juni und im September."""
        juni = festival(von=date(2026, 6, 14), bis=date(2026, 6, 14))
        september = festival(von=date(2026, 9, 5), bis=date(2026, 9, 5))
        assert pruefung.stimmigkeit([juni, september]) == []


class TestGeweseneAusgabe:
    def test_terminlos_mit_vergangenem_jahr_im_namen(self):
        """„Big Day Out 2000 Auckland" ist keine offene Ankündigung."""
        alt = festival(name="Big Day Out 2000 Auckland", von=None, bis=None, jahr="")
        assert pruefung.gewesene_ausgabe(alt, 2026) is True

    def test_mit_termin_zaehlt_der_termin(self):
        assert pruefung.gewesene_ausgabe(festival(name="Fest 2000"), 2026) is False

    def test_ohne_jahr_im_namen_bleibt_es_offen(self):
        offen = festival(name="Irgendein Fest", von=None, bis=None, jahr="")
        assert pruefung.gewesene_ausgabe(offen, 2026) is False


class TestAusbeute:
    @pytest.fixture(autouse=True)
    def eigener_stand(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pruefung, "STAND", tmp_path / "quellen_stand.json")

    def test_der_erste_lauf_meldet_nichts(self):
        assert pruefung.ausbeute({"festivalticker": 1000}, 900) == []

    def test_ein_fuenftel_weniger_ist_ein_einbruch(self):
        pruefung.ausbeute({"festivalticker": 1000}, 900)
        warnungen = pruefung.ausbeute({"festivalticker": 700}, 900)
        assert any("700 statt 1000" in w for w in warnungen)

    def test_kein_einziger_fund_ist_die_schlimmste_stoerung(self):
        """Eine Null ist als Maßstab unbrauchbar (`0 < 0 * 0.8` ist falsch) —
        deshalb der eigene Fall. Ohne ihn blieb es monatelang stumm."""
        pruefung.ausbeute({"festivalticker": 0}, 900)
        assert any("kein einziger Fund" in w
                   for w in pruefung.ausbeute({"festivalticker": 0}, 900))

    def test_der_alte_massstab_bleibt_bei_einem_einbruch_stehen(self):
        """Sonst gilt der schlechte Wert ab morgen als normal."""
        pruefung.ausbeute({"festivalticker": 1000}, 900)
        pruefung.ausbeute({"festivalticker": 700}, 900)
        assert any("statt 1000" in w
                   for w in pruefung.ausbeute({"festivalticker": 700}, 900))

    def test_kleine_schwankungen_sind_normal(self):
        pruefung.ausbeute({"festivalticker": 1000}, 900)
        assert pruefung.ausbeute({"festivalticker": 850}, 900) == []

    def test_ein_mitgebrachter_stand_wird_nach_seinem_alter_beurteilt(self):
        """Nicht das Schweigen der Quelle zählt, sondern das Datum."""
        warnungen = pruefung.ausbeute({"festivalticker": 1900}, 900,
                                      {"festivalticker": "2020-01-01"})
        assert any("Tage alt" in w for w in warnungen)

    def test_ein_frischer_mitgebrachter_stand_ist_in_ordnung(self):
        heute = date.today().isoformat()
        assert pruefung.ausbeute({"festivalticker": 1900}, 900,
                                 {"festivalticker": heute}) == []
