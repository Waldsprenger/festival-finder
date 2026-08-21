"""Der mitgebrachte Stand: Was ihn füllt, was ihn liest, was ihn schützt.

Die Quelle festivalticker antwortet dem Lauf auf fremden Servern mit 403.
Der abgelegte Stand schließt diese Lücke — er darf dabei weder von einem
Lauf ohne Funde geleert noch von einem Lauf mit Funde übergangen werden.
"""

import gzip
import json

import festival_scraper as lauf
import pytest
import schnappschuss


@pytest.fixture(autouse=True)
def eigener_ordner(tmp_path, monkeypatch):
    monkeypatch.setattr(schnappschuss, "ORDNER", tmp_path / "schnappschuss")
    return tmp_path


def satz(name="Testival"):
    return {"source": "festivalticker", "name": name, "date_from": "01.06.2026"}


class TestAblegen:
    def test_stand_geht_hin_und_zurueck(self):
        assert schnappschuss.schreiben("festivalticker", [satz()]) is True
        records, datum = schnappschuss.lesen("festivalticker")
        assert records == [satz()]
        assert datum

    def test_ohne_funde_wird_nichts_geschrieben(self):
        # Sonst löschte ein Lauf, der die Quelle nicht erreicht, genau das,
        # was der Lauf zu Hause mitgebracht hat.
        schnappschuss.schreiben("festivalticker", [satz()])
        assert schnappschuss.schreiben("festivalticker", []) is False
        records, _ = schnappschuss.lesen("festivalticker")
        assert records == [satz()]

    def test_nur_vorgesehene_quellen(self):
        assert schnappschuss.schreiben("festivalsunited", [satz()]) is False
        assert schnappschuss.lesen("festivalsunited") == ([], "")

    def test_ohne_datei_leeres_ergebnis(self):
        assert schnappschuss.lesen("festivalticker") == ([], "")

    def test_gleicher_inhalt_gleiche_datei(self):
        # Sonst stünde nach jedem Lauf eine neue Fassung in der Versions-
        # geschichte, obwohl sich kein einziges Festival geändert hat.
        schnappschuss.schreiben("festivalticker", [satz()])
        erste = schnappschuss.datei("festivalticker").read_bytes()
        schnappschuss.schreiben("festivalticker", [satz()])
        assert schnappschuss.datei("festivalticker").read_bytes() == erste

    def test_reihenfolge_der_funde_aendert_nichts(self):
        # Die Seiten kommen aus vier Faeden zurueck, also in wechselnder
        # Reihenfolge. Ohne Sortieren gaebe es taeglich einen Commit, in dem
        # kein einziges Festival anders ist.
        a, b = satz("Alpha"), satz("Beta")
        a["source_url"], b["source_url"] = "https://x/a", "https://x/b"
        schnappschuss.schreiben("festivalticker", [a, b])
        erste = schnappschuss.datei("festivalticker").read_bytes()
        schnappschuss.schreiben("festivalticker", [b, a])
        assert schnappschuss.datei("festivalticker").read_bytes() == erste
        records, _ = schnappschuss.lesen("festivalticker")
        assert [r["name"] for r in records] == ["Alpha", "Beta"]

    def test_datei_ist_lesbares_json(self):
        schnappschuss.schreiben("festivalticker", [satz()])
        roh = gzip.decompress(schnappschuss.datei("festivalticker").read_bytes())
        assert json.loads(roh)["quelle"] == "festivalticker"


class TestAlter:
    def test_frischer_stand_ist_null_tage_alt(self):
        schnappschuss.schreiben("festivalticker", [satz()])
        _, datum = schnappschuss.lesen("festivalticker")
        assert schnappschuss.alter_in_tagen(datum) == 0

    def test_alter_stand_wird_gezaehlt(self):
        assert schnappschuss.alter_in_tagen("2026-01-01") > 200

    def test_unlesbares_datum_gibt_nichts_vor(self):
        assert schnappschuss.alter_in_tagen("neulich") is None


class TestWaechterMitStand:
    def stand(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lauf, "DATA", tmp_path)

    def test_mitgebrachte_quelle_gilt_nicht_als_ausfall(self, tmp_path, monkeypatch):
        self.stand(tmp_path, monkeypatch)
        heute = __import__("datetime").date.today().isoformat()
        assert lauf.pruefe_ausbeute({"festivalticker": 0}, 5000,
                                    {"festivalticker": heute}) == []

    def test_alter_stand_wird_gemeldet(self, tmp_path, monkeypatch):
        self.stand(tmp_path, monkeypatch)
        warnungen = lauf.pruefe_ausbeute({"festivalticker": 0}, 5000,
                                         {"festivalticker": "2026-01-01"})
        assert warnungen and "Tage alt" in warnungen[0]

    def test_der_massstab_wird_trotzdem_geschrieben(self, tmp_path, monkeypatch):
        # Die Variable für die Datei hieß einmal wie die für das Datum -
        # dann landete der Maßstab in einer Datei namens "2026-01-01".
        self.stand(tmp_path, monkeypatch)
        lauf.pruefe_ausbeute({"festivalticker": 0}, 5000,
                             {"festivalticker": "2026-01-01"})
        assert (tmp_path / "quellen_stand.json").exists()
        assert not (tmp_path / "2026-01-01").exists()
