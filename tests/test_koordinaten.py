"""Die Koordinate muss zum Land passen — und Stufe 8 nutzt sie als Beweis.

Solange nur Europa gesammelt wurde, hielt der europäische Rahmen die groben
Verwechslungen ab: Buenos Aires für Lugano, Chicago für Berlin. Weltweit gibt
es diese Grenze nicht mehr; an ihre Stelle tritt der Kasten des Landes, das
die Quelle selbst nennt.
"""

import pytest
from gemeinsam import koordinate_passt_zum_land
from quellen import datensatz, koordinate_plausibel
from zusammenfuehren import band_registry, namen_verwandt, zusammenfuehren


class TestKoordinatePlausibel:
    @pytest.mark.parametrize("lat,lon,gut", [
        (52.5, 13.4, True), (-33.9, 151.2, True), (0.5, 0.5, True),
        (0.0, 0.0, False),          # Golf von Guinea heisst "Feld leer"
        (91.0, 0.0, False), (0.0, 181.0, False),
        (None, 13.4, False), (52.5, None, False),
    ])
    def test_auf_der_erde(self, lat, lon, gut):
        assert koordinate_plausibel(lat, lon) is gut


class TestKoordinateZumLand:
    @pytest.mark.parametrize("lat,lon,land,passt", [
        (46.00, 8.95, "CH", True),        # Lugano
        (-34.69, -58.50, "CH", False),    # Buenos Aires für Lugano
        (52.50, 13.40, "DE", True),       # Berlin
        (41.87, -87.62, "DE", False),     # Chicago für Berlin
        (28.10, -15.46, "ES", True),      # Las Palmas gehört zu Spanien
        (32.64, -16.91, "PT", True),      # Funchal gehört zu Portugal
        (35.65, 139.70, "JP", True),
        (52.51, 13.45, "HU", False),      # Berlin für Budapest
        (41.87, -87.62, "", True),        # ohne Land wird nicht geraten
        (41.87, -87.62, "Bayern", True),  # ohne Kasten auch nicht
    ])
    def test_kasten_des_landes(self, lat, lon, land, passt):
        assert koordinate_passt_zum_land(lat, lon, land) is passt

    def test_datensatz_verwirft_die_falsche_koordinate(self):
        rec = datensatz("festivalsunited", "u", "Budapest Park",
                        city="Budapest", country="HU", lat=52.51, lon=13.45)
        assert (rec["lat"], rec["lon"]) == (None, None)

    def test_datensatz_behaelt_die_richtige(self):
        rec = datensatz("festivalsunited", "u", "Budapest Park",
                        city="Budapest", country="HU", lat=47.47, lon=19.09)
        assert (rec["lat"], rec["lon"]) == (47.47, 19.09)


class TestNamenVerwandt:
    @pytest.mark.parametrize("a,b,verwandt", [
        ("Hard Summer", "HARD Summer Music Festival", True),
        ("BitterSweet Festival", "BitterSweet Music Festival", True),
        ("Summer Sonic Festival", "Summer Sonic Tokyo", True),
        ("Lollapalooza Argentina", "Lollapalooza Festival Argentinien", True),
        ("Annie Mac Presents", "Freedom Street Europe", False),
        ("ESNS", "Eurosonic Noorderslag", False),      # dafür gibt es die Aliasliste
        ("Das Fest", "Waldfest", False),
    ])
    def test_steckt_einer_im_anderen(self, a, b, verwandt):
        assert namen_verwandt(a, b) is verwandt


class TestStufe8:
    def fund(self, quelle, name, lat, lon, von="01.08.2026", stadt="Irgendwo"):
        return datensatz(quelle, f"https://{quelle}.example/{name}", name,
                         date_from=von, city=stadt, lat=lat, lon=lon)

    def zusammen(self, *funde):
        liste = list(funde)
        return zusammenfuehren(liste, band_registry(liste)[0])

    def test_gleicher_punkt_gleicher_tag_verwandter_name(self):
        a = self.fund("festivalsunited", "HARD Summer Music Festival", 33.95, -118.34)
        b = self.fund("jambase", "Hard Summer", 33.95, -118.34)
        assert len(self.zusammen(a, b)) == 1

    def test_gleicher_punkt_aber_anderes_fest(self):
        # In Attard auf Malta liegen zwei Veranstaltungen auf demselben Punkt
        a = self.fund("festivalabroad", "Annie Mac Presents", 35.89, 14.42)
        b = self.fund("jambase", "Freedom Street Europe", 35.89, 14.42)
        assert len(self.zusammen(a, b)) == 2

    def test_gleicher_name_aber_anderer_tag(self):
        a = self.fund("festivalsunited", "HARD Summer Music Festival", 33.95, -118.34)
        b = self.fund("jambase", "Hard Summer", 33.95, -118.34, von="01.09.2026")
        assert len(self.zusammen(a, b)) == 2

    def test_dieselbe_quelle_zweimal_bleibt_zweimal(self):
        a = self.fund("jambase", "Sommerfest Nord", 52.5, 13.4)
        b = self.fund("jambase", "Sommerfest", 52.5, 13.4)
        assert len(self.zusammen(a, b)) == 2

    def test_ohne_koordinate_bleibt_es_bei_den_namensstufen(self):
        # Verschiedene Orte, keine Koordinate: Dann gibt es keinen Beweis, und
        # die Namensähnlichkeit allein genügt den früheren Stufen nicht.
        a = self.fund("festivalsunited", "HARD Summer Music Festival", None, None,
                      stadt="Los Angeles")
        b = self.fund("jambase", "Hard Summer", None, None, stadt="Inglewood")
        assert len(self.zusammen(a, b)) == 2

    def test_mit_koordinate_findet_es_zusammen(self):
        # Dieselben zwei, diesmal mit demselben Punkt
        a = self.fund("festivalsunited", "HARD Summer Music Festival", 33.95, -118.34,
                      stadt="Los Angeles")
        b = self.fund("jambase", "Hard Summer", 33.95, -118.34, stadt="Inglewood")
        assert len(self.zusammen(a, b)) == 1

class TestNachDemVerschmelzen:
    """Land und Koordinate koennen aus verschiedenen Quellen stammen."""

    def test_koordinate_der_einen_gegen_land_der_anderen(self):
        # Eine Quelle nennt Berlin ohne Land, eine andere Deutschland ohne
        # Koordinate. Zusammen ergaebe das Lollapalooza Berlin in Chicago.
        a = datensatz("jambase", "https://jambase.example/lolla", "Lollapalooza",
                      date_from="12.09.2026", city="Berlin",
                      lat=41.872, lon=-87.619)
        b = datensatz("festivalticker", "https://ft.example/lolla", "Lollapalooza",
                      date_from="12.09.2026", city="Berlin", country="Deutschland")
        [ergebnis] = zusammenfuehren([a, b], band_registry([a, b])[0])
        assert ergebnis["country"] == "DE"
        assert ergebnis["lat"] is None

    def test_passende_koordinate_bleibt(self):
        a = datensatz("jambase", "https://jambase.example/x", "Lollapalooza",
                      date_from="12.09.2026", city="Berlin", lat=52.51, lon=13.45)
        b = datensatz("festivalticker", "https://ft.example/x", "Lollapalooza",
                      date_from="12.09.2026", city="Berlin", country="Deutschland")
        [ergebnis] = zusammenfuehren([a, b], band_registry([a, b])[0])
        assert (ergebnis["lat"], ergebnis["lon"]) == (52.51, 13.45)
