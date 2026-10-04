"""Die Eigenheiten einzelner Quellen.

festivalabroad führt Feste, deren nächster Termin noch aussteht, ohne
Datenblatt; jambase nennt Acts doppelt, die an zwei Tagen spielen; festivism
kennt Konzerte in Minecraft; wannafest listet überwiegend Clubabende;
festivalticker reiht Bandnamen ohne Trennzeichen. Jede dieser Eigenheiten stand
einmal falsch in den Daten.
"""

from datetime import date

import pytest

from festivalfinder.quellen import alle
from festivalfinder.quellen.festivalticker import bands as ft_bands
from festivalfinder.quellen.wannafest import land_und_ort

from ..conftest import StillerAbrufer, seite

LESER = {q.name: q for q in alle()}


@pytest.fixture
def netz():
    return StillerAbrufer()


class TestFestivalabroad:
    def test_datenblatt_wird_vollstaendig_gelesen(self, netz):
        f = LESER["festivalabroad"].lesen(
            netz, "https://www.festivalabroad.com/festivals/jazztage-dresden",
            seite("festivalabroad_1.html.gz"))
        assert f.name == "Jazztage Dresden"
        assert (f.von, f.bis) == (date(2026, 1, 16), date(2026, 10, 17))
        assert (f.stadt, f.land) == ("Dresden", "DE")
        assert f.ort == "Weingut Zimmerling"
        assert (round(f.lat, 3), round(f.lon, 3)) == (51.049, 13.856)
        assert f.webseite == "https://www.jazztage-dresden.de"
        assert f.besucher == "18000"
        assert "Jazz" in f.genre

    def test_ohne_datenblatt_zaehlt_der_titel(self, netz):
        """„2000trees – Gloucestershire, United Kingdom 2027": Der Termin steht
        noch nicht fest, alles andere schon."""
        html = ("<html><head><title>2000trees – Gloucestershire, United Kingdom"
                " 2027</title></head><body>TBA – last edition: 8 Jul 2026</body></html>")
        f = LESER["festivalabroad"].lesen(
            netz, "https://www.festivalabroad.com/festivals/2000trees", html)
        assert f.name == "2000trees"
        assert (f.stadt, f.land) == ("Gloucestershire", "GB")
        assert f.von is None

    def test_abgeschnittener_titel_erfindet_kein_land(self, netz):
        """Lange Titel schneidet die Seite mit Auslassungszeichen ab: aus
        „United States" wird „United State…"."""
        html = ("<html><head><title>Songwriters – Santa Rosa Beach, United State…"
                "</title></head><body></body></html>")
        f = LESER["festivalabroad"].lesen(
            netz, "https://www.festivalabroad.com/festivals/x", html)
        assert f.stadt == "Santa Rosa Beach"
        assert f.land == ""

    def test_der_ort_steht_nicht_hinter_dem_hinweis_auf_den_termin(self, netz):
        """Seit 2026: „… – Dates to Be Announced | Bend, Unit…". Der volle Ort
        steht im Verweis auf die Länderseite."""
        html = ("<html><head><title>4 Peaks Music Festival – Dates to Be Announced"
                " | Bend, Unit…</title></head><body><h1>4 Peaks Music Festival</h1>"
                '<span><a href="/festivals-in-united-states">Bend, United States</a>'
                "</span></body></html>")
        f = LESER["festivalabroad"].lesen(
            netz, "https://www.festivalabroad.com/festivals/4-peaks", html)
        assert f.name == "4 Peaks Music Festival"
        assert (f.stadt, f.land) == ("Bend", "US")

    def test_ohne_verweis_hilft_der_titel(self, netz):
        html = ("<html><head><title>Ability Fest – Dates to Be Announced | "
                "Melbourne, Australia</title></head><body></body></html>")
        f = LESER["festivalabroad"].lesen(
            netz, "https://www.festivalabroad.com/festivals/ability", html)
        assert (f.stadt, f.land) == ("Melbourne", "AU")

    def test_ohne_titel_kein_datensatz(self, netz):
        assert LESER["festivalabroad"].lesen(
            netz, "https://www.festivalabroad.com/festivals/x",
            "<html><body>nichts</body></html>") is None


class TestJambase:
    def test_acts_stehen_einmal(self, netz):
        """jambase nennt einzelne Acts zweimal, wenn sie an mehreren Tagen
        spielen — der Trichter räumt das weg."""
        f = LESER["jambase"].lesen(netz, "https://www.jambase.com/festival/x",
                                   seite("jambase_1.html.gz"))
        assert len(set(f.lineup)) == len(f.lineup)
        assert f.lineup

    def test_keine_ticketseite_als_offizielle_adresse(self, netz):
        f = LESER["jambase"].lesen(netz, "https://www.jambase.com/festival/x",
                                   seite("jambase_1.html.gz"))
        assert "ticketmaster" not in f.webseite
        assert "jambase" not in f.webseite


class TestFestivism:
    def test_die_spielwelt_zaehlt_nicht(self, netz):
        """„XW" steht bei dieser Quelle für Konzerte in Minecraft und Roblox.
        Die gibt es wirklich — hinfahren kann man nicht."""
        html = ('<script type="application/ld+json">{"@type":"Event",'
                '"name":"Block Party","location":{"address":'
                '{"addressCountry":"XW","addressLocality":"Minecraft"}}}</script>')
        assert LESER["festivism"].lesen(netz, "https://www.festivism.com/festivals/x",
                                        html) is None

    def test_online_zaehlt_auch_nicht(self, netz):
        html = ('<script type="application/ld+json">{"@type":"Event",'
                '"name":"Stream Fest","eventAttendanceMode":'
                '"https://schema.org/OnlineEventAttendanceMode",'
                '"location":{"address":{"addressCountry":"DE"}}}</script>')
        assert LESER["festivism"].lesen(netz, "https://www.festivism.com/festivals/x",
                                        html) is None

    def test_ein_echtes_fest_kommt_durch(self, netz):
        f = LESER["festivism"].lesen(netz, "https://www.festivism.com/festivals/x",
                                     seite("festivism_1.html.gz"))
        assert f is not None and f.name and f.von is None


class TestFestivalnetworks:
    def test_die_sammeldatei(self, netz):
        roh = seite("festivalnetworks_feed.json.gz")
        netz.seiten["https://festivalnetworks.com/data-api.php?r=festivals"] = roh
        funde = LESER["festivalnetworks"].sammeldatei(netz, 2000)
        assert len(funde) > 100
        mit_termin = [f for f in funde if f.von]
        assert mit_termin, "kein einziger Termin gelesen"

    def test_alte_jahrgaenge_fallen_weg(self, netz):
        roh = seite("festivalnetworks_feed.json.gz")
        netz.seiten["https://festivalnetworks.com/data-api.php?r=festivals"] = roh
        spaet = LESER["festivalnetworks"].sammeldatei(netz, 2099)
        assert all(f.von is None for f in spaet)


def startseite(*orte: str) -> str:
    """Eine festivalflyer-Startseite mit je einem Datenblatt je Ort."""
    return "".join(
        '<script type="application/ld+json">{"@type":"Event","name":"Fest",'
        f'"startDate":"2027-8-25","location":[{{"@type":"Place","name":"{ort}"}}]}}'
        "</script>" for ort in orte)


class TestFestivalflyer:
    """Die Quelle ruht: Die Startseite nennt nur noch Festivals ohne Land."""

    START = "https://festivalflyer.com/"

    def test_ohne_land_bleibt_sie_zu(self, netz):
        """So sieht die Startseite seit September 2026 aus."""
        netz.seiten[self.START] = startseite("Queens Hall", "Damyns Hall Aerodrome")
        netz.geholt["festivalflyer.com"] = 1
        assert LESER["festivalflyer"].wieder_offen(netz, 2026) is False

    def test_mit_land_ist_sie_wieder_offen(self, netz):
        netz.seiten[self.START] = startseite(
            "Fernhill Farm, Cheddar Road, BS40 6LD Compton Martin, United Kingdom")
        netz.geholt["festivalflyer.com"] = 1
        assert LESER["festivalflyer"].wieder_offen(netz, 2026) is True

    def test_vergangene_termine_zaehlen_nicht(self, netz):
        netz.seiten[self.START] = startseite("Farm, BS40 6LD Compton, United Kingdom")
        netz.geholt["festivalflyer.com"] = 1
        assert LESER["festivalflyer"].wieder_offen(netz, 2030) is False

    def test_aus_dem_zwischenspeicher_zaehlt_nichts(self, netz):
        netz.seiten[self.START] = startseite("Farm, BS40 6LD Compton, United Kingdom")
        assert LESER["festivalflyer"].wieder_offen(netz, 2026) is None


class TestWannafest:
    def test_land_vor_der_spielstaette(self):
        """„Austria Festivalterrein Salzburgring": erst das Land, dann der Platz."""
        assert land_und_ort("Austria Festivalterrein Salzburgring") == \
            ("AT", "Festivalterrein Salzburgring")

    def test_mehrwortige_laender(self):
        assert land_und_ort("United Kingdom Somewhere")[0] == "GB"

    def test_clubabend_ohne_festivalwort_faellt_durch(self, netz):
        html = ("<html><head><title>Bootshaus DJ Contest - WannaFest</title></head>"
                "<body>Date August 19, 2026 Location Köln, Germany Bootshaus "
                "Place Type Indoor</body></html>")
        assert LESER["wannafest"].lesen(netz, "https://wannafest.com/festivals/x",
                                        html) is None

    def test_draussen_genuegt_auch_ohne_festivalwort(self, netz):
        html = ("<html><head><title>Bootshaus Sommer - WannaFest</title></head>"
                "<body>Date August 19, 2026 Location Köln, Germany Bootshaus "
                "Place Type Outdoor</body></html>")
        f = LESER["wannafest"].lesen(netz, "https://wannafest.com/festivals/x", html)
        assert f is not None and f.stadt == "Köln"


class TestFestivaltickerBands:
    def test_komma_trennt(self):
        assert ft_bands("Powerwolf, Amon Amarth") == ["Powerwolf", "Amon Amarth"]

    def test_klammer_hinter_jedem_namen_trennt_auch(self):
        assert ft_bands("Powerwolf (Metal) Amon Amarth (Death)") == \
            ["Powerwolf", "Amon Amarth"]

    def test_ablaufplan_mit_uhrzeiten(self):
        assert ft_bands("17:30 Powerwolf 19:45 Amon Amarth") == \
            ["Powerwolf", "Amon Amarth"]

    def test_ohne_trenner_wird_nicht_geraten(self):
        """Eine Aufteilung nach Leerzeichen machte aus „Nebula Allstars" die
        Band „Nebula" — lieber kein Lineup als ein erfundenes."""
        assert ft_bands("Deep Purple Manfred Mann's Earth Band") == []

    def test_ein_kurzer_block_gilt_als_ein_act(self):
        assert ft_bands("Nebula Allstars") == ["Nebula Allstars"]

    def test_der_rest_hinter_der_liste_faellt_weg(self):
        assert ft_bands("Powerwolf, Amon Amarth Kommentare zu: irgendwas") == \
            ["Powerwolf", "Amon Amarth"]
