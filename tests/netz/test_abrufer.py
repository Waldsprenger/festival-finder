"""Wie der Lauf mit Antworten umgeht, die keine Seite sind.

Drei Fälle, drei verschiedene Antworten darauf:

* **403** — eine Entscheidung des Betreibers. Kein zweiter Anlauf, und nach
  fünf Absagen bleibt der Rechner für den Rest des Laufs in Ruhe.
* **429** — „zu viele Anfragen", also unsere eigene Ungeduld. Der erste
  weltweite Lauf hat jambase 2.348 Seiten abverlangt und dafür 1.575-mal ein
  429 bekommen; nur 766 Seiten kamen an. Die richtige Antwort ist warten.
* **Netzfehler** — noch einmal versuchen, dann aufgeben und melden.

Jeder Test bekommt seinen eigenen Abrufer. Vorher stand der Zustand im Modul,
und jeder Test musste ihn von Hand leeren.
"""

import pytest
import requests

from festivalfinder.netz import GEDULD_429, SPERRE_AB, Abrufer


class Antwort:
    def __init__(self, status=200, text="<html>ok</html>", kopf=None):
        self.status_code = status
        self.text = text
        self.headers = kopf or {}
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        """Wie requests es tut — der Klassenname landet im Bericht."""
        if self.status_code >= 400:
            fehler = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            fehler.response = self
            raise fehler


class Dienst:
    """Ein Server, der der Reihe nach antwortet — und mitzählt."""

    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.gefragt = 0

    def get(self, _url, **_kwargs):
        self.gefragt += 1
        return self.antworten.pop(0) if self.antworten else Antwort()


@pytest.fixture
def abrufer(tmp_path, monkeypatch):
    """Ein Abrufer mit eigenem Speicher und ohne echtes Warten."""
    monkeypatch.setattr("festivalfinder.netz.abrufer.time.sleep", lambda _s: None)
    return Abrufer(cache=tmp_path, max_age_h=24.0)


def dienst(abrufer, *antworten):
    d = Dienst(*antworten)
    abrufer.session = lambda: d
    return d


class TestZuVieleAnfragen:
    def test_nach_dem_warten_kommt_die_seite(self, abrufer):
        d = dienst(abrufer, Antwort(429), Antwort(429), Antwort(200, "<p>da</p>"))
        assert abrufer.fetch("https://jambase.test/a") == "<p>da</p>"
        assert d.gefragt == 3
        assert abrufer.fehlgeschlagen == []

    def test_die_wartezeit_waechst(self, abrufer):
        dienst(abrufer, Antwort(429), Antwort(429), Antwort(200))
        abrufer.fetch("https://jambase.test/a")
        assert abrufer.verzoegerung["jambase.test"] == 2.0

    def test_retry_after_wird_beachtet(self, abrufer):
        dienst(abrufer, Antwort(429, kopf={"Retry-After": "5"}), Antwort(200))
        abrufer.fetch("https://jambase.test/a")
        assert abrufer.verzoegerung["jambase.test"] == 5.0

    def test_die_wartezeit_gilt_fuer_den_ganzen_rechner(self, abrufer):
        dienst(abrufer, Antwort(429), Antwort(200), Antwort(200))
        abrufer.fetch("https://jambase.test/a")
        assert abrufer._wartezeit("https://jambase.test/andere-seite") == 1.0
        assert abrufer._wartezeit("https://woanders.test/seite") == 0.0

    def test_irgendwann_bleibt_die_seite_liegen(self, abrufer):
        d = dienst(abrufer, *[Antwort(429)] * 12)
        assert abrufer.fetch("https://jambase.test/a") is None
        assert d.gefragt == GEDULD_429 + 1
        assert abrufer.fehlgeschlagen == ["https://jambase.test/a (HTTPError 429)"]

    def test_die_bitte_steht_einmal_im_bericht(self, abrufer):
        dienst(abrufer, Antwort(429), Antwort(429), Antwort(200))
        abrufer.fetch("https://jambase.test/a")
        assert len(abrufer.meldungen) == 1
        assert "bittet um Ruhe" in abrufer.meldungen[0]


class TestAbgewiesen:
    def test_403_wird_nicht_wiederholt(self, abrufer):
        d = dienst(abrufer, *[Antwort(403)] * 5)
        assert abrufer.fetch("https://ft.test/a") is None
        assert d.gefragt == 1
        assert abrufer.fehlgeschlagen == ["https://ft.test/a (HTTPError 403)"]

    def test_nach_fuenf_absagen_ist_ruhe(self, abrufer):
        d = dienst(abrufer, *[Antwort(403)] * 20)
        for i in range(8):
            abrufer.fetch(f"https://ft.test/{i}")
        assert d.gefragt == SPERRE_AB
        assert abrufer.weist_ab("https://ft.test/noch-eine")

    def test_gespeicherte_seiten_kommen_weiter_aus_dem_speicher(self, abrufer):
        """Die Sperre gilt dem Fragen, nicht dem Lesen."""
        dienst(abrufer, Antwort(200, "<p>alt</p>"))
        abrufer.fetch("https://ft.test/a")
        for i in range(SPERRE_AB):
            abrufer.abweisung_vermerken(f"https://ft.test/{i}", 403)
        assert abrufer.weist_ab("https://ft.test/a")
        assert abrufer.fetch("https://ft.test/a") == "<p>alt</p>"


class TestNetzfehler:
    def test_zweiter_anlauf_hilft(self, abrufer):
        class Wackelig(Dienst):
            def get(self, url, **k):
                self.gefragt += 1
                if self.gefragt == 1:
                    raise ConnectionError("weg")
                return Antwort(200, "<p>doch</p>")

        abrufer.session = lambda d=Wackelig(): d
        assert abrufer.fetch("https://x.test/a") == "<p>doch</p>"
        assert abrufer.fehlgeschlagen == []

    def test_nach_drei_versuchen_gemeldet(self, abrufer):
        class Tot(Dienst):
            def get(self, url, **k):
                self.gefragt += 1
                raise ConnectionError("weg")

        d = Tot()
        abrufer.session = lambda: d
        assert abrufer.fetch("https://x.test/a") is None
        assert d.gefragt == 3
        assert abrufer.fehlgeschlagen == ["https://x.test/a (ConnectionError)"]

    def test_vierhundertvier_ist_kein_fehler(self, abrufer):
        d = dienst(abrufer, Antwort(404))
        assert abrufer.fetch("https://x.test/weg") is None
        assert d.gefragt == 1
        assert abrufer.fehlgeschlagen == []


class TestSpeicher:
    def test_eine_seite_wird_nur_einmal_geholt(self, abrufer):
        d = dienst(abrufer, Antwort(200, "<p>eins</p>"), Antwort(200, "<p>zwei</p>"))
        assert abrufer.fetch("https://x.test/a") == "<p>eins</p>"
        assert abrufer.fetch("https://x.test/a") == "<p>eins</p>"
        assert d.gefragt == 1

    def test_mit_frisch_wird_neu_geholt(self, tmp_path, monkeypatch):
        monkeypatch.setattr("festivalfinder.netz.abrufer.time.sleep", lambda _s: None)
        erst = Abrufer(cache=tmp_path)
        dienst(erst, Antwort(200, "<p>alt</p>"))
        erst.fetch("https://x.test/a")

        frisch = Abrufer(cache=tmp_path, frisch=True)
        dienst(frisch, Antwort(200, "<p>neu</p>"))
        assert frisch.fetch("https://x.test/a") == "<p>neu</p>"

    def test_zwei_abrufer_teilen_sich_nichts(self, tmp_path, monkeypatch):
        """Der Kern des Umbaus: kein Zustand im Modul."""
        monkeypatch.setattr("festivalfinder.netz.abrufer.time.sleep", lambda _s: None)
        a, b = Abrufer(cache=tmp_path), Abrufer(cache=tmp_path)
        dienst(a, Antwort(403))
        a.fetch("https://x.test/a")
        assert a.fehlgeschlagen and not b.fehlgeschlagen
