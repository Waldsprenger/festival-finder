"""Die acht Stufen: Was gehört zusammen — und was ausdrücklich nicht.

Die Fälle sind echte: Jeder stand einmal falsch in den Daten und hat eine
Stufe oder eine Sicherung nach sich gezogen.
"""

import pytest

from quellen import datensatz
from zusammenfuehren import (band_registry, name_deckt_sich, ort_deckt_sich,
                             schreibweise_gleich, zeitraum_ueberlappt,
                             zusammenfuehren)


def fund(quelle, name, *, von="", bis="", stadt="", land="DE", lineup=(), **rest):
    """Ein Fund einer Quelle, wie ihn ein Leser abliefert."""
    return datensatz(quelle, f"https://{quelle}.example/{name}", name,
                     date_from=von, date_to=bis, city=stadt, country=land,
                     lineup=list(lineup), **rest)


def fuehre_zusammen(*funde):
    return zusammenfuehren(list(funde), band_registry(list(funde))[0])


class TestStufe1Exakt:
    def test_gleicher_name_ort_jahr_wird_eins(self):
        a = fund("festivalticker", "Wacken Open Air", von="30.07.2026", stadt="Wacken")
        b = fund("festivalsunited", "Wacken Open Air", von="30.07.2026", stadt="Wacken")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_tourformat_bleibt_getrennt(self):
        # Das Irish Spring Festival läuft unter einem Namen an 30 Orten
        a = fund("festivalticker", "Irish Spring Festival", von="26.02.2026", stadt="Mendig")
        b = fund("festivalticker", "Irish Spring Festival", von="27.02.2026", stadt="Gersthofen")
        assert len(fuehre_zusammen(a, b)) == 2

    def test_lineups_und_genres_werden_gesammelt(self):
        a = fund("festivalticker", "Summer Breeze", von="14.08.2026", stadt="Dinkelsbühl",
                 lineup=["Powerwolf"], genre="Metal")
        b = fund("festivalsunited", "Summer Breeze", von="14.08.2026", stadt="Dinkelsbühl",
                 lineup=["Heaven Shall Burn"], genre="Death Metal")
        [ergebnis] = fuehre_zusammen(a, b)
        assert ergebnis["lineup"] == ["Heaven Shall Burn", "Powerwolf"]
        assert ergebnis["genre"] == "Metal, Death Metal"
        assert len(ergebnis["sources"]) == 2

    def test_eine_absage_genuegt(self):
        a = fund("festivalticker", "Testival", von="01.06.2026", stadt="Kiel")
        b = fund("festivalsunited", "Testival", von="01.06.2026", stadt="Kiel", cancelled=True)
        assert fuehre_zusammen(a, b)[0]["cancelled"] is True


class TestStufe3GleicherStart:
    def test_namenszusatz_stoert_nicht(self):
        a = fund("festivalticker", "Kosmos Festival", von="12.06.2026", stadt="Chemnitz")
        b = fund("festivalsunited", "Kosmos Festival Chemnitz", von="12.06.2026", stadt="Chemnitz")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_winterausgabe_bleibt_eigenstaendig(self):
        # "Winter Wutzrock" im Februar und "Wutzrock" im August sind zwei Feste
        a = fund("festivalticker", "Winter Wutzrock", von="14.02.2026", stadt="Hamburg")
        b = fund("festivalsunited", "Wutzrock", von="14.08.2026", stadt="Hamburg")
        assert len(fuehre_zusammen(a, b)) == 2


class TestStufe4Ueberlappung:
    def test_um_einen_tag_versetzte_termine(self):
        # Neuborn: festivalticker zählt den Anreisetag mit, die anderen nicht
        a = fund("festivalticker", "NOAF Neuborn Open Air", von="27.08.2026",
                 bis="30.08.2026", stadt="Wörrstadt")
        b = fund("festivalsunited", "Neuborn Open Air", von="28.08.2026",
                 bis="30.08.2026", stadt="Wörrstadt")
        [ergebnis] = fuehre_zusammen(a, b)
        assert (ergebnis["date_from"], ergebnis["date_to"]) == ("27.08.2026", "30.08.2026")

    def test_gemeinde_gegen_spielstaette(self):
        # festivalhopper nennt die Burg, die anderen die Gemeinde
        a = fund("festivalticker", "Kein Bock auf Nazis Festival", von="02.07.2026",
                 bis="04.07.2026", stadt="Thallichtenberg", venue="Burg Lichtenberg")
        b = fund("festivalhopper", "Kein Bock auf Nazis Festival", von="03.07.2026",
                 bis="04.07.2026", stadt="Burg Lichtenberg")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_gemeinsames_wort_allein_genuegt_nicht(self):
        # Beide heißen "Wien", sind aber zwei Veranstaltungen
        a = fund("festivalticker", "METAStadt Open Air Wien", von="10.07.2026",
                 bis="12.07.2026", stadt="Wien", land="AT")
        b = fund("festivalsunited", "Afrika Tage Wien", von="11.07.2026",
                 bis="13.07.2026", stadt="Wien", land="AT")
        assert len(fuehre_zusammen(a, b)) == 2


class TestStufe5Schreibweise:
    def test_zusammen_und_getrennt_geschrieben(self):
        a = fund("festivalticker", "SonneMondSterne", von="07.08.2026", stadt="Saalburg")
        b = fund("festivalsunited", "Sonne Mond Sterne", von="07.08.2026", stadt="Saalburg")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_nordischer_buchstabe_gegen_umschrift(self):
        # Vom Schlüssel bleibt nur "soerd" und "sord" - zu kurz. Deshalb wird
        # zusätzlich der volle Name verglichen.
        a = fund("festivalticker", "Soerdfest Open Air", von="09.05.2026", stadt="Landscheide")
        b = fund("festivalsunited", "Sørdfest Open Air", von="09.05.2026", stadt="Landscheide")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_gleicher_name_gleicher_tag_andere_ortsschreibweise(self):
        # Gemeinde gegen Ortsteil: Das ist dasselbe Fest, und Stufe 2 darf es
        # verbinden - jede Quelle nennt genau einen Kandidaten.
        a = fund("festivalticker", "Hai in den Mai", von="30.04.2026", stadt="Stemwede")
        b = fund("festivalsunited", "Hai in den Mai", von="30.04.2026", stadt="Wehdem")
        assert len(fuehre_zusammen(a, b)) == 1


class TestStufe2Quellenpaare:
    def test_weit_auseinanderliegende_termine_bleiben_getrennt(self):
        # "Campus Festival" gibt es in Dresden und in Debrecen; ohne diese
        # Sicherung verschwand eines der beiden aus der Liste.
        a = fund("festivalsunited", "Campus Festival", von="02.07.2026", stadt="Dresden")
        b = fund("wannafest", "Campus Festival", von="22.07.2026", stadt="Debrecen",
                 land="HU")
        assert len(fuehre_zusammen(a, b)) == 2

    def test_ein_tag_versatz_ist_noch_dasselbe_fest(self):
        a = fund("festivalticker", "Beispielfest", von="04.06.2026", stadt="Kattowitz",
                 land="PL")
        b = fund("festivalsunited", "Beispielfest", von="05.06.2026", stadt="Katowice",
                 land="PL")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_terminlose_uebersicht_stoert_die_pruefung_nicht(self):
        a = fund("festivalticker", "Beispielfest", von="04.06.2026", stadt="Kiel")
        b = fund("festivalsunited", "Beispielfest", stadt="Kiel")
        assert len(fuehre_zusammen(a, b)) == 1


class TestOrtsangabenVerschiedenGenau:
    def test_spielstaette_vor_dem_ort(self):
        a = fund("festivalticker", "adriAkustik Liedermacherfest", von="12.08.2026",
                 stadt="Kulturpark Deutzen")
        b = fund("festivalsunited", "adriAkustik", von="12.08.2026", stadt="Deutzen")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_gemeinde_mit_ortsteil(self):
        a = fund("festivalsunited", "Waldfrieden Wonderland Festival", von="06.08.2026",
                 bis="09.08.2026", stadt="Stemwede-Wehdem")
        b = fund("festivalticker", "Wonderland", von="06.08.2026", bis="09.08.2026",
                 stadt="Wehdem")
        assert len(fuehre_zusammen(a, b)) == 1


class TestStufe6OhneTermin:
    def test_terminlose_uebersichtsseite_findet_ihren_jahrgang(self):
        a = fund("festivalticker", "Elbriot Festival", von="08.08.2026", stadt="Hamburg")
        b = fund("festivalsunited", "Elb Riot Festival", stadt="Hamburg")
        [ergebnis] = fuehre_zusammen(a, b)
        assert ergebnis["date_from"] == "08.08.2026"
        assert len(ergebnis["sources"]) == 2

    def test_spielstaette_im_ortsfeld(self):
        a = fund("festivalticker", "Die Festung Rockt", von="30.05.2026",
                 stadt="Kronach", venue="Festung Rosenberg")
        b = fund("festivalhopper", "Die Festung Rockt", stadt="Festung Rosenberg")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_frueheste_ausgabe_gewinnt(self):
        a = fund("festivalticker", "Beispielfest", von="01.06.2026", stadt="Bonn")
        b = fund("festivalticker", "Beispielfest", von="01.06.2027", stadt="Bonn")
        c = fund("festivalsunited", "Beispielfest", stadt="Bonn")
        ergebnis = {f["date_from"]: f for f in fuehre_zusammen(a, b, c)}
        assert len(ergebnis) == 2
        assert len(ergebnis["01.06.2026"]["sources"]) == 2      # die terminlose kam hierher
        assert len(ergebnis["01.06.2027"]["sources"]) == 1

    def test_ohne_ortsangabe_hilft_die_offizielle_adresse(self):
        # Vier von fünf terminlosen Einträgen nennen keinen Ort. Die Adresse
        # kosmosfestival.fi gehört aber genau einem Fest.
        a = fund("festivalticker", "Kosmos Festival", von="09.07.2026",
                 stadt="Närhilä", land="FI", website="https://kosmosfestival.fi/")
        b = fund("festivalsunited", "Kosmos Festival", land="FI",
                 website="http://www.kosmosfestival.fi")
        [ergebnis] = fuehre_zusammen(a, b)
        assert ergebnis["city"] == "Närhilä"

    def test_fremde_adresse_verbindet_nichts(self):
        a = fund("festivalticker", "Beispielfest", von="09.07.2026", stadt="Bonn",
                 website="https://beispielfest-bonn.de")
        b = fund("festivalsunited", "Beispielfest", website="https://beispielfest.at")
        assert len(fuehre_zusammen(a, b)) == 2

    def test_zwei_orte_bleiben_unentschieden(self):
        # Dieselbe Adresse führt zwei Feste - welches gemeint ist, steht nicht
        # fest, also bleibt der terminlose Eintrag stehen.
        a = fund("festivalticker", "Sommerfest", von="01.06.2026", stadt="Bonn",
                 website="https://veranstalter.de")
        b = fund("festivalticker", "Sommerfest", von="01.08.2026", stadt="Kiel",
                 website="https://veranstalter.de")
        c = fund("festivalsunited", "Sommerfest", website="https://veranstalter.de")
        assert len(fuehre_zusammen(a, b, c)) == 3


class TestStufe7GleicheQuelle:
    def test_dieselbe_quelle_fuehrt_dasselbe_fest_zweimal(self):
        a = fund("wannafest", "Nacht Wacht XL Festival", von="08.08.2026",
                 bis="09.08.2026", stadt="Arnhem", land="NL")
        b = fund("wannafest", "Nachtwacht XL Festival", von="08.08.2026", stadt="Arnhem",
                 land="NL")
        assert len(fuehre_zusammen(a, b)) == 1

    def test_zwei_ausgaben_im_selben_jahr_bleiben_getrennt(self):
        # Heartbeatz im Juni und im September - kein Versehen, zwei Termine
        a = fund("wannafest", "Heartbeatz Festival", von="14.06.2026", stadt="München")
        b = fund("festivalsunited", "Heart BeatZ Festival", von="05.09.2026", stadt="München")
        assert len(fuehre_zusammen(a, b)) == 2


class TestZweitnamen:
    def test_uebersetzter_name_findet_zusammen(self):
        # festivalfinder nennt den Berliner Karneval der Kulturen englisch
        a = fund("festivalhopper", "Karneval der Kulturen", von="22.05.2026", stadt="Berlin")
        b = fund("festivalfinder", "Carnival of Cultures", von="22.05.2026", stadt="Berlin")
        [ergebnis] = fuehre_zusammen(a, b)
        assert ergebnis["name"] == "Karneval der Kulturen"

    def test_tippfehler_im_kennwort(self):
        a = fund("festivalticker", "Die Schlagernacht des Jahres", von="28.03.2026",
                 stadt="München")
        b = fund("festivalsunited", "Die Schagernacht München", von="28.03.2026",
                 stadt="München")
        assert len(fuehre_zusammen(a, b)) == 1


class TestAufraeumenAmEnde:
    def test_jahr_folgt_dem_termin(self):
        a = fund("festivalhopper", "Sommer im Park", von="27.08.2026", stadt="Gera", year="2027")
        assert fuehre_zusammen(a)[0]["year"] == "2026"

    def test_unmoegliche_koordinate_faellt_weg(self):
        a = fund("festivalsunited", "LongLake Festival", von="01.07.2026", stadt="Lugano",
                 land="CH", lat=91.0, lon=-58.49)
        assert fuehre_zusammen(a)[0]["lat"] is None

    def test_besucherzahl_wird_zur_zahl(self):
        a = fund("festivalticker", "Afdreiht un Buten", von="01.07.2026", stadt="Kiel",
                 visitors="2.000")
        assert fuehre_zusammen(a)[0]["visitors"] == "2000"

    def test_ortsangabe_wird_gesetzt(self):
        a = fund("festivalticker", "Testival", von="01.07.2026", stadt="Kiel",
                 land="Deutschland")
        ergebnis = fuehre_zusammen(a)[0]
        assert ergebnis["country"] == "DE"
        assert ergebnis["location"] == "Kiel, DE"

    def test_die_ganze_welt_kommt_mit(self):
        funde = [fund("festapp", "Hulaween", von="30.10.2026", stadt="Live Oak", land="US"),
                 fund("festapp", "Fuji Rock", von="24.07.2026", stadt="Yuzawa", land="JP"),
                 fund("festapp", "Rock in Rio", von="18.09.2026", stadt="Rio", land="BR")]
        laender = {f["country"] for f in fuehre_zusammen(*funde)}
        assert laender == {"US", "JP", "BR"}

    def test_chronologisch_sortiert(self):
        spaet = fund("festivalticker", "Spaetfest", von="01.09.2026", stadt="Kiel")
        frueh = fund("festivalticker", "Fruehfest", von="01.03.2026", stadt="Kiel")
        assert [f["name"] for f in fuehre_zusammen(spaet, frueh)] == ["Fruehfest", "Spaetfest"]


class TestVergleiche:
    def test_zeitraum_ueberlappt(self):
        a = {"date_from": "27.08.2026", "date_to": "30.08.2026"}
        b = {"date_from": "28.08.2026", "date_to": "30.08.2026"}
        c = {"date_from": "01.09.2026", "date_to": "03.09.2026"}
        leer = {"date_from": "", "date_to": ""}
        assert zeitraum_ueberlappt(a, b)
        assert not zeitraum_ueberlappt(a, c)
        assert not zeitraum_ueberlappt(a, leer)

    def test_ort_deckt_sich(self):
        assert ort_deckt_sich("oberndorf", "oberndorf am neckar")   # Gemeinde vorn
        assert ort_deckt_sich("stemwede wehdem", "wehdem")          # Ortsteil hinten
        assert ort_deckt_sich("kulturpark deutzen", "deutzen")      # Spielstaette davor
        assert not ort_deckt_sich("kiel", "kieler bucht")           # kein Wortanfang
        assert not ort_deckt_sich("", "kiel")

    def test_name_deckt_sich(self):
        assert name_deckt_sich("neuborn", "noaf neuborn")
        assert name_deckt_sich("r o i rock on isens", "roi rock on isens")
        assert not name_deckt_sich("metastadt wien", "afrika tage wien")

    @pytest.mark.parametrize("a,b,gleich", [
        ("Sonne Mond Sterne", "SonneMondSterne", True),
        ("Sziget", "Szigit", True),
        ("Soerdfest Open Air", "Sørdfest Open Air", True),
        ("Wutzrock", "Wutz", False),          # zu kurz für einen Vergleich
        ("Highfield", "Hurricane", False),
    ])
    def test_schreibweise_gleich(self, a, b, gleich):
        assert schreibweise_gleich(a, b) is gleich


class TestBandRegistry:
    def test_haeufigste_schreibweise_setzt_sich_durch(self):
        funde = [fund("festivalticker", "A", von="01.06.2026", stadt="Kiel",
                      lineup=["Powerwolf", "POWERWOLF"]),
                 fund("festivalsunited", "B", von="02.06.2026", stadt="Kiel",
                      lineup=["Powerwolf"])]
        [ergebnis_a, ergebnis_b] = fuehre_zusammen(*funde)
        assert ergebnis_a["lineup"] == ["Powerwolf"]
        assert ergebnis_b["lineup"] == ["Powerwolf"]
