"""Die Leser der acht Quellen — an gespeicherten Ausschnitten geprüft.

Die Ausschnitte sind auf das Nötige gekürzt; sie halten die Eigenheiten fest,
an denen die Leser sich einmal verschluckt haben.
"""

import pytest

from quellen import QUELLEN, RANG, datensatz, fa_lesen, fh_lesen, fp_lesen, ft_bands


class TestDatensatz:
    def test_grundform(self):
        rec = datensatz("festivalticker", "https://x/y", "Testival",
                        date_from="01.06.2026", city="Kiel", country="DE")
        assert rec["date_to"] == "01.06.2026"        # ein Tag heißt von = bis
        assert rec["year"] == "2026"
        assert rec["lineup"] == []

    def test_termin_schlaegt_jahresangabe(self):
        rec = datensatz("festivalhopper", "u", "Sommer im Park",
                        date_from="27.08.2026", year="2027")
        assert rec["year"] == "2026"

    def test_jahr_ohne_termin_bleibt(self):
        assert datensatz("festivalsunited", "u", "X", year="2027")["year"] == "2027"

    def test_besucherzahl_wird_zur_zahl(self):
        assert datensatz("festivalticker", "u", "X", visitors="ca. 18.000")["visitors"] \
            == "18000"

    def test_koordinate_ausserhalb_europas_faellt_weg(self):
        rec = datensatz("festivalsunited", "u", "X", lat=-34.6, lon=-58.4)
        assert (rec["lat"], rec["lon"]) == (None, None)

    def test_koordinate_in_europa_bleibt(self):
        rec = datensatz("festivalsunited", "u", "X", lat=46.0, lon=8.9)
        assert (rec["lat"], rec["lon"]) == (46.0, 8.9)


class TestFtBands:
    def test_kommaliste(self):
        assert ft_bands("Powerwolf, Kreator, Sabaton") == ["Powerwolf", "Kreator", "Sabaton"]

    def test_klammern_als_trenner(self):
        assert ft_bands("Powerwolf (Power Metal) Kreator (Thrash)") == ["Powerwolf", "Kreator"]

    def test_uhrzeiten_als_trenner(self):
        assert ft_bands("17:30 Powerwolf 19:45 Kreator") == ["Powerwolf", "Kreator"]

    def test_ohne_trenner_wird_nicht_geraten(self):
        # "Deep Purple Manfred Mann's Earth Band" sind zwei Acts - lieber keins
        assert ft_bands("Deep Purple Manfred Mann's Earth Band Uriah Heep") == []

    def test_einzelner_kurzer_name_gilt(self):
        assert ft_bands("Powerwolf") == ["Powerwolf"]

    def test_anhaengsel_faellt_weg(self):
        assert ft_bands("Powerwolf, Kreator Kommentare zu: Wacken") == ["Powerwolf", "Kreator"]


class TestFestivalalarm:
    SEITE = """<html><body>
      <h1>Baltic Open Air 19.08. - 21.08.2026</h1>
      <p>Festivalticket (ab): 89,00 € Tagesticket 45 €
         Stadt: 24837 Schleswig Land: Deutschland
         Veranstaltungsplatz Örtlichkeit: Wikinger Museum Camping ja
         Genres: Rock, Metal Gründung 1999
         Besucher: 8.000 Sonstiges nichts
         Künstler: Powerwolf, Kreator Anreise mit dem Auto</p>
      <li>Webseite <a href="https://baltic-open-air.de">Zur Seite</a></li>
    </body></html>"""

    def test_liest_die_kopfzeile(self):
        rec = fa_lesen("https://festival-alarm.com/x", self.SEITE)
        assert rec["name"] == "Baltic Open Air"
        assert (rec["date_from"], rec["date_to"]) == ("19.08.2026", "21.08.2026")

    def test_liest_die_felder(self):
        rec = fa_lesen("https://festival-alarm.com/x", self.SEITE)
        assert rec["city"] == "Schleswig"
        assert rec["plz"] == "24837"
        assert rec["venue"] == "Wikinger Museum"
        assert rec["visitors"] == "8000"
        assert rec["genre"] == "Rock, Metal"
        assert rec["price"].startswith("ab ")
        assert rec["lineup"] == ["Powerwolf", "Kreator"]
        assert rec["website"] == "https://baltic-open-air.de"

    def test_ohne_ueberschrift_kein_datensatz(self):
        assert fa_lesen("u", "<html><body>nichts</body></html>") is None


class TestFestivalhopper:
    SEITE = """<html><body>
      <h1>28. Summer Breeze 2026</h1>
      <p>Musikart: Metal Region: Bayern , &#127465;&#127466; Deutschland
         Festivalort: 91550 Dinkelsbühl Besucher: 45.000 Tickets: ab 199 €
         Infos zum Festival</p>
      <p>18.08.2026 (Di) - 21.08.2026 (Fr)</p>
      <a href="/bands/karten/powerwolf.php">Powerwolf</a>
      <a href="/bands/mit/">Bands</a>
      <a href="/bands/headliner">Headliner</a>
    </body></html>"""

    def test_menuepunkte_sind_keine_bands(self):
        rec = fh_lesen("https://www.festivalhopper.de/festival/x-2026", self.SEITE)
        assert rec["lineup"] == ["Powerwolf"]

    def test_flagge_und_postleitzahl(self):
        rec = fh_lesen("https://www.festivalhopper.de/festival/x-2026", self.SEITE)
        assert rec["country"] == "DE"
        assert rec["plz"] == "91550"
        assert rec["city"] == "Dinkelsbühl"
        assert rec["visitors"] == "45000"

    def test_ausserhalb_europas_wird_verworfen(self):
        seite = self.SEITE.replace("Deutschland", "Japan")
        assert fh_lesen("https://www.festivalhopper.de/festival/x-2026", seite) is None


class TestFestapp:
    def datenblatt(self, preis):
        return ("""<html><body><script type="application/ld+json">
        {"@type": "MusicEvent", "name": "Beispielfest 2026",
         "startDate": "2026-07-03", "endDate": "2026-07-05",
         "location": {"name": "Sumiswald",
                      "address": {"addressLocality": "Dorfstrasse 22, 3457 Sumiswald, Switzerland",
                                  "postalCode": "3457"}},
         "offers": {"price": "%s", "priceCurrency": "CHF"},
         "performer": [{"name": "Powerwolf"}, {"name": "TBA"}]}
        </script></body></html>""" % preis)

    def test_datenblatt_wird_gelesen(self):
        rec = fp_lesen("https://festapp.io/festivals/x", self.datenblatt("120.00"))
        assert rec["name"] == "Beispielfest"
        assert (rec["date_from"], rec["date_to"]) == ("03.07.2026", "05.07.2026")
        assert rec["city"] == "Sumiswald"
        assert rec["country"] == "CH"
        assert rec["plz"] == "3457"
        assert rec["lineup"] == ["Powerwolf"]        # "TBA" ist kein Act
        assert rec["price"] == "ab CHF 120,00"

    def test_tausenderpunkt_im_preis(self):
        # "8.900.00" liess float() scheitern und kostete das ganze Festival
        rec = fp_lesen("https://festapp.io/festivals/x", self.datenblatt("8.900.00"))
        assert rec is not None
        assert rec["price"] == "ab CHF 8900,00"

    def test_ohne_datenblatt_kein_datensatz(self):
        assert fp_lesen("u", "<html><body>nichts</body></html>") is None


def test_quellenreihenfolge_bestimmt_den_rang():
    assert [q.name for q in QUELLEN][:3] == ["festivalticker", "festivalsunited",
                                             "festivalalarm"]
    assert RANG["festivalticker"] < RANG["festivalfinder"]
