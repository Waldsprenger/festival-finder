"""Die vier weltweiten Quellen — und ihre Eigenheiten.

festivalabroad führt Feste, deren nächster Termin noch aussteht, ohne
Datenblatt; jambase nennt Acts doppelt, die an zwei Tagen spielen; festivism
kennt Konzerte in Minecraft; festivalnetworks liefert alles in einer Datei.
Jede dieser Eigenheiten stand einmal falsch in den Daten.
"""

import gzip
import json
from pathlib import Path

import pytest
import quellen
from quellen import datum_iso, fb_lesen, fn_datum, fn_feed, fv_lesen, jb_website
from quellen import zahl_oder_nichts

SEITEN = Path(__file__).parent / "seiten"


class TestDatumUndZahlen:
    @pytest.mark.parametrize("roh,erwartet", [
        ("2026-07-03", "03.07.2026"),
        ("2026-07-03T18:00:00", "03.07.2026"),
        ("", ""), (None, ""), ("morgen", ""),
    ])
    def test_datum_aus_dem_datenblatt(self, roh, erwartet):
        assert datum_iso(roh) == erwartet

    @pytest.mark.parametrize("roh,erwartet", [
        ("27-Aug-26", "27.08.2026"), ("1-Jan-27", "01.01.2027"),
        ("", ""), ("27.08.2026", ""), ("32-Xyz-26", ""),
    ])
    def test_datum_der_sammeldatei(self, roh, erwartet):
        assert fn_datum(roh) == erwartet

    @pytest.mark.parametrize("roh,erwartet", [
        (51.05, 51.05), ("51.05", 51.05), ("", None), (None, None), ("Nord", None),
    ])
    def test_koordinate_mal_zahl_mal_zeichenkette(self, roh, erwartet):
        assert zahl_oder_nichts(roh) == erwartet


class TestFestivalabroad:
    def seite(self, nr):
        return gzip.decompress(
            (SEITEN / f"festivalabroad_{nr}.html.gz").read_bytes()).decode("utf-8")

    def test_datenblatt_wird_vollstaendig_gelesen(self):
        rec = fb_lesen("https://www.festivalabroad.com/festivals/jazztage-dresden",
                       self.seite(1))
        assert rec["name"] == "Jazztage Dresden"
        assert (rec["date_from"], rec["date_to"]) == ("16.01.2026", "17.10.2026")
        assert (rec["city"], rec["country"]) == ("Dresden", "DE")
        assert rec["venue"] == "Weingut Zimmerling"
        assert (round(rec["lat"], 3), round(rec["lon"], 3)) == (51.049, 13.856)
        assert rec["website"] == "https://www.jazztage-dresden.de"
        assert rec["visitors"] == "18000"
        assert "Jazz" in rec["genre"]

    def test_ohne_datenblatt_zaehlt_der_titel(self):
        # "2000trees – Gloucestershire, United Kingdom 2027": Der Termin steht
        # noch nicht fest, alles andere schon.
        html = ("<html><head><title>2000trees – Gloucestershire, United Kingdom"
                " 2027</title></head><body>TBA – last edition: 8 Jul 2026</body></html>")
        rec = fb_lesen("https://www.festivalabroad.com/festivals/2000trees", html)
        assert rec["name"] == "2000trees"
        assert (rec["city"], rec["country"]) == ("Gloucestershire", "GB")
        assert rec["date_from"] == ""

    def test_abgeschnittener_titel_erfindet_kein_land(self):
        html = ("<html><head><title>Songwriters – Santa Rosa Beach, United State…"
                "</title></head><body></body></html>")
        rec = fb_lesen("https://www.festivalabroad.com/festivals/x", html)
        assert rec["city"] == "Santa Rosa Beach"
        assert rec["country"] == ""

    def test_ohne_titel_kein_datensatz(self):
        assert fb_lesen("https://www.festivalabroad.com/festivals/x",
                        "<html><body>nichts</body></html>") is None


class TestJambase:
    def test_offizielle_seite_statt_karten_und_netzwerke(self):
        html = """<html><body>
          <a href="https://www.facebook.com/adk">Facebook</a>
          <a href="https://theticketing.co/e/adk">Tickets</a>
          <a href="https://www.jambase.com/band/moe">moe.</a>
          <a href="https://adkmusicfest.com/">Official</a>
        </body></html>"""
        assert jb_website(html) == "https://adkmusicfest.com/"

    def test_ohne_fremde_seite_bleibt_es_leer(self):
        assert jb_website('<html><body><a href="/intern">hier</a></body></html>') == ""

    def test_lineup_ohne_wiederholungen(self):
        html = gzip.decompress((SEITEN / "jambase_1.html.gz").read_bytes()).decode("utf-8")
        rec = quellen.jb_lesen(
            "https://www.jambase.com/festival/adirondack-independence-music-festival-2026",
            html)
        assert rec["country"] == "US"
        assert len(rec["lineup"]) == len(set(rec["lineup"]))
        assert "moe." in rec["lineup"]


class TestFestivism:
    def test_ort_und_land_ohne_termin(self):
        html = gzip.decompress((SEITEN / "festivism_1.html.gz").read_bytes()).decode("utf-8")
        rec = fv_lesen("https://www.festivism.com/festivals/x", html)
        assert rec["city"] == "Dresden" and rec["country"] == "DE"
        assert rec["date_from"] == ""

    def test_konzerte_in_spielwelten_bleiben_draussen(self):
        html = """<html><body><script type="application/ld+json">
        {"@type": "MusicEvent", "name": "ROBLOX Glastonbury Festival",
         "location": {"@type": "Place",
                      "address": {"addressLocality": "Roblox", "addressCountry": "XW"}}}
        </script></body></html>"""
        assert fv_lesen("https://www.festivism.com/festivals/roblox", html) is None

    def test_online_veranstaltungen_bleiben_draussen(self):
        html = """<html><body><script type="application/ld+json">
        {"@type": "MusicEvent", "name": "Stream Fest",
         "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
         "location": {"@type": "Place",
                      "address": {"addressLocality": "Netz", "addressCountry": "DE"}}}
        </script></body></html>"""
        assert fv_lesen("https://www.festivism.com/festivals/stream", html) is None


class TestFestivalnetworks:
    def feed(self, monkeypatch, inhalt):
        monkeypatch.setattr(quellen, "fetch", lambda _url: inhalt)
        return fn_feed(2026)

    def test_die_ganze_datei_wird_gelesen(self, monkeypatch):
        roh = gzip.decompress(
            (SEITEN / "festivalnetworks_feed.json.gz").read_bytes()).decode("utf-8")
        funde = self.feed(monkeypatch, roh)
        assert len(funde) > 500
        reading = next(f for f in funde if f["name"] == "Reading Festival")
        assert reading["country"] == "GB"
        assert reading["date_from"] == "27.08.2026"
        assert reading["lat"] and reading["lon"]
        assert reading["visitors"] == "105000"
        assert "280" in reading["price"]

    def test_vergangene_jahrgaenge_bleiben_draussen(self, monkeypatch):
        inhalt = json.dumps([{"Festival Name": "Altfest", "Start Date": "01-Jul-18",
                              "Country": "DE", "City/Region": "Kiel"}])
        assert self.feed(monkeypatch, inhalt) == []

    def test_kaputte_datei_kostet_nicht_den_lauf(self, monkeypatch):
        assert self.feed(monkeypatch, "{kein json") == []
        assert self.feed(monkeypatch, None) == []

    def test_eintrag_ohne_namen_wird_uebergangen(self, monkeypatch):
        inhalt = json.dumps([{"Festival Name": "", "Start Date": "01-Jul-26"}])
        assert self.feed(monkeypatch, inhalt) == []
