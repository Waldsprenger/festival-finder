"""Kürzel, die eine andere Band meinen — und die Tabelle, die sich dabei ändert.

„TBS" und The Butcher Sisters sind dasselbe; „LP" und Linkin Park nicht — das
ist die Sängerin LP. Entscheidend ist, ob Kürzel und ausgeschriebener Name je
gemeinsam auf einem Plakat stehen.

Die Tabelle ist jetzt ein Objekt. Vorher war sie ein Modulwörterbuch, das
`kollisionen` unterwegs veränderte — jeder Test musste das zurücknehmen, sonst
hing sein Ergebnis davon ab, welcher vorher lief.
"""

from festivalfinder.bund.bandnamen import kollisionen, verzeichnis
from festivalfinder.kern.fund import fund
from festivalfinder.kern.text import Kuerzel
from festivalfinder.kern.zeit import aus_deutsch


def f(name, lineup, von="01.06.2026", stadt="Kiel"):
    return fund("festivalticker", f"https://x/{name}", name,
                von=aus_deutsch(von), stadt=stadt, lineup=list(lineup))


class TestKollisionen:
    def test_kuerzel_und_name_auf_demselben_plakat_gehoeren_zusammen(self):
        kuerzel = Kuerzel({"TBS": "The Butcher Sisters"})
        funde = [f("A", ["TBS", "The Butcher Sisters"])]
        assert kollisionen(funde, kuerzel) == []
        assert kuerzel.band_key("TBS") == kuerzel.band_key("The Butcher Sisters")

    def test_kuerzel_allein_meint_eine_andere_band(self):
        kuerzel = Kuerzel({"LP": "Linkin Park"})
        funde = [f("A", ["LP"]), f("B", ["Linkin Park"], stadt="Bonn")]
        assert kollisionen(funde, kuerzel) == ["lp"]
        assert kuerzel.band_key("LP") != kuerzel.band_key("Linkin Park")

    def test_geprueft_wird_je_festival_nicht_je_quellseite(self):
        """Die beiden Schreibweisen stehen oft auf Seiten verschiedener
        Quellen und treffen sich erst beim Zusammenführen."""
        kuerzel = Kuerzel({"TBS": "The Butcher Sisters"})
        a = fund("festivalticker", "https://a", "Fest", von=aus_deutsch("01.06.2026"),
                 stadt="Kiel", lineup=["TBS"])
        b = fund("festivalsunited", "https://b", "Fest", von=aus_deutsch("01.06.2026"),
                 stadt="Kiel", lineup=["The Butcher Sisters"])
        assert kollisionen([a, b], kuerzel) == []

    def test_ein_kuerzel_das_nirgends_vorkommt_bleibt(self):
        kuerzel = Kuerzel({"XYZ": "Irgendeine Band"})
        assert kollisionen([f("A", ["Powerwolf"])], kuerzel) == []
        assert "xyz" in kuerzel.nach_kuerzel

    def test_eine_eigene_tabelle_faerbt_nicht_ab(self):
        """Der Kern des Umbaus: Zwei Tabellen wissen nichts voneinander."""
        eine = Kuerzel({"LP": "Linkin Park"})
        andere = Kuerzel({"LP": "Linkin Park"})
        kollisionen([f("A", ["LP"])], eine)
        assert "lp" not in eine.nach_kuerzel
        assert "lp" in andere.nach_kuerzel


class TestVerzeichnis:
    def test_haeufigste_schreibweise_gewinnt(self):
        funde = [f("A", ["Powerwolf"]), f("B", ["POWERWOLF"], stadt="Bonn"),
                 f("C", ["Powerwolf"], stadt="Mainz")]
        namen, _ = verzeichnis(funde, Kuerzel({}))
        assert set(namen.values()) == {"Powerwolf"}

    def test_hinterlegter_alias_schlaegt_die_mehrheit(self):
        """Sonst gewänne bei gleicher Häufigkeit die Abkürzung."""
        kuerzel = Kuerzel({"TBS": "The Butcher Sisters"})
        funde = [f("A", ["TBS"]), f("B", ["The Butcher Sisters"], stadt="Bonn")]
        namen, _ = verzeichnis(funde, kuerzel)
        assert set(namen.values()) == {"The Butcher Sisters"}

    def test_statistik_zaehlt_die_vereinheitlichten(self):
        funde = [f("A", ["Powerwolf"]), f("B", ["POWERWOLF"], stadt="Bonn")]
        _namen, statistik = verzeichnis(funde, Kuerzel({}))
        assert statistik["gruppen"] == 1
        assert statistik["vereinheitlicht"] == 1
        assert statistik["roh_schreibweisen"] == 2
