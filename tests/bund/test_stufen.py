"""Die acht Stufen: Was gehört zusammen — und was ausdrücklich nicht.

Die Fälle sind echte: Jeder stand einmal falsch in den Daten und hat eine
Stufe oder eine Sicherung nach sich gezogen.
"""

import pytest

from festivalfinder.bund.lauf import vorbereiten, zusammenfuehren
from festivalfinder.bund.regeln import (name_deckt_sich, ort_deckt_sich,
                                        schreibweise_gleich)
from festivalfinder.kern.fund import fund
from festivalfinder.kern.zeit import aus_deutsch, ueberlappt


def f(quelle, name, *, von=None, bis=None, stadt="", land="DE", lineup=(), **rest):
    """Ein Fund einer Quelle, wie ihn ein Leser abliefert."""
    return fund(quelle, f"https://{quelle}.example/{name}", name,
                von=aus_deutsch(von), bis=aus_deutsch(bis),
                stadt=stadt, land=land, lineup=list(lineup), **rest)


def bund(*funde):
    liste = list(funde)
    namen, _statistik, _doppelt, kuerzel = vorbereiten(liste)
    return zusammenfuehren(liste, namen, kuerzel)


class TestStufe1Exakt:
    def test_gleicher_name_ort_jahr_wird_eins(self):
        a = f("festivalticker", "Wacken Open Air", von="30.07.2026", stadt="Wacken")
        b = f("festivalsunited", "Wacken Open Air", von="30.07.2026", stadt="Wacken")
        assert len(bund(a, b)) == 1

    def test_tourformat_bleibt_getrennt(self):
        # Das Irish Spring Festival läuft unter einem Namen an 30 Orten
        a = f("festivalticker", "Irish Spring Festival", von="26.02.2026", stadt="Mendig")
        b = f("festivalticker", "Irish Spring Festival", von="27.02.2026", stadt="Gersthofen")
        assert len(bund(a, b)) == 2

    def test_lineups_und_genres_werden_gesammelt(self):
        a = f("festivalticker", "Summer Breeze", von="14.08.2026", stadt="Dinkelsbühl",
              lineup=["Powerwolf"], genre="Metal")
        b = f("festivalsunited", "Summer Breeze", von="14.08.2026", stadt="Dinkelsbühl",
              lineup=["Heaven Shall Burn"], genre="Death Metal")
        [ergebnis] = bund(a, b)
        assert ergebnis.lineup == ["Heaven Shall Burn", "Powerwolf"]
        assert ergebnis.genre == "Metal, Death Metal"
        assert len(ergebnis.quellen) == 2

    def test_eine_absage_genuegt(self):
        a = f("festivalticker", "Testival", von="01.06.2026", stadt="Kiel")
        b = f("festivalsunited", "Testival", von="01.06.2026", stadt="Kiel", abgesagt=True)
        assert bund(a, b)[0].abgesagt is True

    def test_eine_quelle_die_sich_selbst_wiederholt(self):
        """Manche Seiten zählen ihre Genres doppelt auf.

        Der Abgleich ohne Groß-/Kleinschreibung räumt das weg — auch beim
        ersten Datensatz, obwohl das nach einem Selbstgespräch aussieht. Ohne
        das stand die Aufzählung bei 271 Festivals zweimal da.
        """
        a = f("festivalticker", "Testival", von="01.06.2026", stadt="Kiel",
              genre="Ska, Elektro, ska, ELEKTRO")
        assert bund(a)[0].genre == "Ska, Elektro"


class TestStufe2Quellenpaare:
    def test_weit_auseinanderliegende_termine_bleiben_getrennt(self):
        # „Campus Festival" gibt es in Dresden und in Debrecen; ohne diese
        # Sicherung verschwand eines der beiden aus der Liste.
        a = f("festivalsunited", "Campus Festival", von="02.07.2026", stadt="Dresden")
        b = f("wannafest", "Campus Festival", von="22.07.2026", stadt="Debrecen", land="HU")
        assert len(bund(a, b)) == 2

    def test_ein_tag_versatz_ist_noch_dasselbe_fest(self):
        a = f("festivalticker", "Beispielfest", von="04.06.2026", stadt="Kattowitz", land="PL")
        b = f("festivalsunited", "Beispielfest", von="05.06.2026", stadt="Katowice", land="PL")
        assert len(bund(a, b)) == 1

    def test_terminlose_uebersicht_stoert_die_pruefung_nicht(self):
        a = f("festivalticker", "Beispielfest", von="04.06.2026", stadt="Kiel")
        b = f("festivalsunited", "Beispielfest", stadt="Kiel")
        assert len(bund(a, b)) == 1

    def test_mehrere_quellen_gegen_eine(self):
        """Beim San Hejmo standen fünf Quellen für „Weeze" gegen eine für
        „Airport Weeze" — und blieben getrennt, weil früher jeder Kandidat aus
        genau einer Quelle stammen musste."""
        weeze = [f(q, "San Hejmo", von="08.08.2026", stadt="Weeze")
                 for q in ("festivalticker", "festivalsunited", "festivalalarm")]
        airport = f("festapp", "San Hejmo", von="08.08.2026", stadt="Airport Weeze")
        assert len(bund(*weeze, airport)) == 1


class TestStufe3GleicherStart:
    def test_namenszusatz_stoert_nicht(self):
        a = f("festivalticker", "Kosmos Festival", von="12.06.2026", stadt="Chemnitz")
        b = f("festivalsunited", "Kosmos Festival Chemnitz", von="12.06.2026", stadt="Chemnitz")
        assert len(bund(a, b)) == 1

    def test_winterausgabe_bleibt_eigenstaendig(self):
        # „Winter Wutzrock" im Februar und „Wutzrock" im August sind zwei Feste
        a = f("festivalticker", "Winter Wutzrock", von="14.02.2026", stadt="Hamburg")
        b = f("festivalsunited", "Wutzrock", von="14.08.2026", stadt="Hamburg")
        assert len(bund(a, b)) == 2


class TestStufe4Ueberlappung:
    def test_um_einen_tag_versetzte_termine(self):
        # Neuborn: festivalticker zählt den Anreisetag mit, die anderen nicht
        a = f("festivalticker", "NOAF Neuborn Open Air", von="27.08.2026",
              bis="30.08.2026", stadt="Wörrstadt")
        b = f("festivalsunited", "Neuborn Open Air", von="28.08.2026",
              bis="30.08.2026", stadt="Wörrstadt")
        [ergebnis] = bund(a, b)
        assert ergebnis.von == aus_deutsch("27.08.2026")
        assert ergebnis.bis == aus_deutsch("30.08.2026")

    def test_gemeinde_gegen_spielstaette(self):
        # festivalhopper nennt die Burg, die anderen die Gemeinde
        a = f("festivalticker", "Kein Bock auf Nazis Festival", von="02.07.2026",
              bis="04.07.2026", stadt="Thallichtenberg", ort="Burg Lichtenberg")
        b = f("festivalhopper", "Kein Bock auf Nazis Festival", von="03.07.2026",
              bis="04.07.2026", stadt="Burg Lichtenberg")
        assert len(bund(a, b)) == 1

    def test_gemeinsames_wort_allein_genuegt_nicht(self):
        # Beide heißen „Wien", sind aber zwei Veranstaltungen
        a = f("festivalticker", "METAStadt Open Air Wien", von="10.07.2026",
              bis="12.07.2026", stadt="Wien", land="AT")
        b = f("festivalsunited", "Afrika Tage Wien", von="11.07.2026",
              bis="13.07.2026", stadt="Wien", land="AT")
        assert len(bund(a, b)) == 2


class TestStufe5Schreibweise:
    def test_zusammen_und_getrennt_geschrieben(self):
        a = f("festivalticker", "SonneMondSterne", von="07.08.2026", stadt="Saalburg")
        b = f("festivalsunited", "Sonne Mond Sterne", von="07.08.2026", stadt="Saalburg")
        assert len(bund(a, b)) == 1

    def test_nordischer_buchstabe_gegen_umschrift(self):
        # Vom Schlüssel bleibt nur „soerd" und „sord" — zu kurz. Deshalb wird
        # zusätzlich der volle Name verglichen.
        a = f("festivalticker", "Soerdfest Open Air", von="09.05.2026", stadt="Landscheide")
        b = f("festivalsunited", "Sørdfest Open Air", von="09.05.2026", stadt="Landscheide")
        assert len(bund(a, b)) == 1

    def test_gemeinde_gegen_ortsteil(self):
        a = f("festivalticker", "Hai in den Mai", von="30.04.2026", stadt="Stemwede")
        b = f("festivalsunited", "Hai in den Mai", von="30.04.2026", stadt="Wehdem")
        assert len(bund(a, b)) == 1


class TestOrtsangabenVerschiedenGenau:
    def test_spielstaette_vor_dem_ort(self):
        a = f("festivalticker", "adriAkustik Liedermacherfest", von="12.08.2026",
              stadt="Kulturpark Deutzen")
        b = f("festivalsunited", "adriAkustik", von="12.08.2026", stadt="Deutzen")
        assert len(bund(a, b)) == 1

    def test_gemeinde_mit_ortsteil(self):
        a = f("festivalsunited", "Waldfrieden Wonderland Festival", von="06.08.2026",
              bis="09.08.2026", stadt="Stemwede-Wehdem")
        b = f("festivalticker", "Wonderland", von="06.08.2026", bis="09.08.2026",
              stadt="Wehdem")
        assert len(bund(a, b)) == 1


class TestStufe6OhneTermin:
    def test_terminlose_uebersichtsseite_findet_ihren_jahrgang(self):
        a = f("festivalticker", "Elbriot Festival", von="08.08.2026", stadt="Hamburg")
        b = f("festivalsunited", "Elb Riot Festival", stadt="Hamburg")
        [ergebnis] = bund(a, b)
        assert ergebnis.von == aus_deutsch("08.08.2026")
        assert len(ergebnis.quellen) == 2

    def test_spielstaette_im_ortsfeld(self):
        a = f("festivalticker", "Die Festung Rockt", von="30.05.2026",
              stadt="Kronach", ort="Festung Rosenberg")
        b = f("festivalhopper", "Die Festung Rockt", stadt="Festung Rosenberg")
        assert len(bund(a, b)) == 1

    def test_frueheste_ausgabe_gewinnt(self):
        a = f("festivalticker", "Beispielfest", von="01.06.2026", stadt="Bonn")
        b = f("festivalticker", "Beispielfest", von="01.06.2027", stadt="Bonn")
        c = f("festivalsunited", "Beispielfest", stadt="Bonn")
        nach_termin = {x.von: x for x in bund(a, b, c)}
        assert len(nach_termin) == 2
        # die terminlose kam zum früheren Jahrgang
        assert len(nach_termin[aus_deutsch("01.06.2026")].quellen) == 2
        assert len(nach_termin[aus_deutsch("01.06.2027")].quellen) == 1

    def test_ohne_ortsangabe_hilft_die_offizielle_adresse(self):
        # Vier von fünf terminlosen Einträgen nennen keinen Ort. Die Adresse
        # kosmosfestival.fi gehört aber genau einem Fest.
        a = f("festivalticker", "Kosmos Festival", von="09.07.2026", stadt="Närhilä",
              land="FI", webseite="https://kosmosfestival.fi/")
        b = f("festivalsunited", "Kosmos Festival", land="FI",
              webseite="http://www.kosmosfestival.fi")
        [ergebnis] = bund(a, b)
        assert ergebnis.stadt == "Närhilä"

    def test_fremde_adresse_verbindet_nichts(self):
        a = f("festivalticker", "Beispielfest", von="09.07.2026", stadt="Bonn",
              webseite="https://beispielfest-bonn.de")
        b = f("festivalsunited", "Beispielfest", webseite="https://beispielfest.at")
        assert len(bund(a, b)) == 2

    def test_zwei_orte_bleiben_unentschieden(self):
        # Dieselbe Adresse führt zwei Feste — welches gemeint ist, steht nicht
        # fest, also bleibt der terminlose Eintrag stehen.
        a = f("festivalticker", "Sommerfest", von="01.06.2026", stadt="Bonn",
              webseite="https://veranstalter.de")
        b = f("festivalticker", "Sommerfest", von="01.08.2026", stadt="Kiel",
              webseite="https://veranstalter.de")
        c = f("festivalsunited", "Sommerfest", webseite="https://veranstalter.de")
        assert len(bund(a, b, c)) == 3


class TestStufe7GleicheQuelle:
    def test_dieselbe_quelle_zweimal_mit_anderer_schreibweise(self):
        """wannafest führt „Nacht Wacht XL" und „Nachtwacht XL" getrennt."""
        a = f("wannafest", "Nacht Wacht XL", von="12.09.2026", stadt="Arnheim", land="NL")
        b = f("wannafest", "Nachtwacht XL", von="12.09.2026", stadt="Arnheim", land="NL")
        assert len(bund(a, b)) == 1


class TestStufe8GleicherPunkt:
    def test_gleiche_koordinate_gleicher_tag_verwandter_name(self):
        """Vom Schlüssel bleibt bei „Das Fest" nur „das" — die Koordinate ist
        hier das stärkere Zeichen."""
        a = f("festivalticker", "Das Fest", von="24.07.2026", stadt="Karlsruhe",
              lat=48.99, lon=8.40)
        b = f("festivalabroad", "DAS FEST Karlsruhe", von="24.07.2026",
              stadt="Karlsruhe", lat=48.99, lon=8.40)
        assert len(bund(a, b)) == 1

    def test_derselbe_punkt_mit_fremdem_namen_bleibt_getrennt(self):
        # In Attard auf Malta liegen am 11. September zwei Veranstaltungen auf
        # demselben Punkt.
        a = f("festivalticker", "Erstes Fest", von="11.09.2026", stadt="Attard",
              land="MT", lat=35.89, lon=14.44)
        b = f("festivalabroad", "Ganz anderes Fest", von="11.09.2026", stadt="Attard",
              land="MT", lat=35.89, lon=14.44)
        assert len(bund(a, b)) == 2


class TestReihenfolgeSpieltKeineRolle:
    def test_dieselben_funde_ergeben_denselben_bestand(self):
        """Die Stufen sind nicht reihenfolgeunabhängig; deshalb wird vor der
        ersten Stufe sortiert. Ohne das unterschieden sich zwei Läufe über
        denselben Funden um bis zu 29 Festivals."""
        funde = [
            f("festivalticker", "Wacken Open Air", von="30.07.2026", stadt="Wacken"),
            f("festivalsunited", "Wacken Open Air", von="30.07.2026", stadt="Wacken"),
            f("festivalalarm", "Wacken", von="31.07.2026", stadt="Wacken"),
            f("festapp", "Summer Breeze", von="14.08.2026", stadt="Dinkelsbühl"),
            f("wannafest", "Summer Breeze Open Air", von="14.08.2026",
              stadt="Dinkelsbühl"),
        ]
        vorwaerts = [x.name for x in bund(*funde)]
        rueckwaerts = [x.name for x in bund(*reversed(funde))]
        assert vorwaerts == rueckwaerts


class TestVergleiche:
    @pytest.mark.parametrize("a,b", [
        ("oberndorf am neckar", "oberndorf"),
        ("stemwede wehdem", "wehdem"),
        ("kulturpark deutzen", "deutzen"),
    ])
    def test_ort_deckt_sich(self, a, b):
        assert ort_deckt_sich(a, b) and ort_deckt_sich(b, a)

    def test_wortanfang_genuegt_nicht(self):
        assert not ort_deckt_sich("kiel", "kieler bucht")

    def test_name_muss_ganz_stecken(self):
        assert name_deckt_sich("neuborn", "noaf neuborn")
        assert not name_deckt_sich("metastadt wien", "afrika tage wien")

    def test_schreibweise(self):
        assert schreibweise_gleich("Sonne Mond Sterne", "SonneMondSterne")
        assert schreibweise_gleich("Sziget", "Szigit")
        assert not schreibweise_gleich("Wutz", "Watz")

    def test_ueberlappung_ist_symmetrisch(self):
        a0, a1 = aus_deutsch("19.08.2026"), aus_deutsch("22.08.2026")
        b0, b1 = aus_deutsch("22.08.2026"), aus_deutsch("24.08.2026")
        assert ueberlappt(a0, a1, b0, b1) == ueberlappt(b0, b1, a0, a1) is True
