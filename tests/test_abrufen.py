"""Wie der Lauf mit Antworten umgeht, die keine Seite sind.

Drei Fälle, drei verschiedene Antworten darauf:

* **403** — eine Entscheidung des Betreibers. Kein zweiter Anlauf, und nach
  fünf Absagen bleibt der Rechner für den Rest des Laufs in Ruhe.
* **429** — „zu viele Anfragen", also unsere eigene Ungeduld. Der erste
  weltweite Serverlauf hat jambase 2.348 Seiten abverlangt und dafür 1.575-mal
  ein 429 bekommen; nur 766 Seiten kamen an. Die richtige Antwort ist warten.
* **Netzfehler** — noch einmal versuchen, dann aufgeben und melden.
"""

import pytest
import requests

import netz


class Antwort:
    def __init__(self, status=200, text="<html>ok</html>", kopf=None):
        self.status_code = status
        self.text = text
        self.headers = kopf or {}
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        """Wie requests es tut - der Klassenname landet im Bericht."""
        if self.status_code >= 400:
            fehler = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            fehler.response = self
            raise fehler


class Dienst:
    """Ein Server, der der Reihe nach antwortet - und mitzählt."""

    def __init__(self, *antworten):
        self.antworten = list(antworten)
        self.gefragt = 0

    def get(self, _url, **_kwargs):
        self.gefragt += 1
        return self.antworten.pop(0) if self.antworten else Antwort()


@pytest.fixture(autouse=True)
def sauber(monkeypatch, tmp_path):
    """Jeder Test mit leerem Speicher, ohne echtes Warten und ohne Netz."""
    monkeypatch.setattr(netz, "CACHE", tmp_path)
    monkeypatch.setattr(netz, "MAX_AGE_H", 24.0)
    monkeypatch.setattr(netz, "FRISCH", False)
    monkeypatch.setattr(netz.time, "sleep", lambda _s: None)
    netz.FEHLGESCHLAGEN.clear()
    netz.MELDUNGEN.clear()
    netz.ABGEWIESEN.clear()
    netz.VERZOEGERUNG.clear()


def dienst(monkeypatch, *antworten):
    d = Dienst(*antworten)
    monkeypatch.setattr(netz, "session", lambda: d)
    return d


class TestZuVieleAnfragen:
    def test_nach_dem_warten_kommt_die_seite(self, monkeypatch):
        d = dienst(monkeypatch, Antwort(429), Antwort(429), Antwort(200, "<p>da</p>"))
        assert netz.fetch("https://jambase.test/a") == "<p>da</p>"
        assert d.gefragt == 3
        assert netz.FEHLGESCHLAGEN == []

    def test_die_wartezeit_waechst(self, monkeypatch):
        dienst(monkeypatch, Antwort(429), Antwort(429), Antwort(200))
        netz.fetch("https://jambase.test/a")
        assert netz.VERZOEGERUNG["jambase.test"] == 2.0

    def test_retry_after_wird_beachtet(self, monkeypatch):
        dienst(monkeypatch, Antwort(429, kopf={"Retry-After": "5"}), Antwort(200))
        netz.fetch("https://jambase.test/a")
        assert netz.VERZOEGERUNG["jambase.test"] == 5.0

    def test_die_wartezeit_gilt_fuer_den_ganzen_rechner(self, monkeypatch):
        dienst(monkeypatch, Antwort(429), Antwort(200), Antwort(200))
        netz.fetch("https://jambase.test/a")
        assert netz._wartezeit("https://jambase.test/andere-seite") == 1.0
        assert netz._wartezeit("https://woanders.test/seite") == 0.0

    def test_irgendwann_bleibt_die_seite_liegen(self, monkeypatch):
        d = dienst(monkeypatch, *[Antwort(429)] * 12)
        assert netz.fetch("https://jambase.test/a") is None
        assert d.gefragt == netz.GEDULD_429 + 1
        assert netz.FEHLGESCHLAGEN == ["https://jambase.test/a (HTTPError 429)"]

    def test_die_bitte_steht_einmal_im_bericht(self, monkeypatch):
        dienst(monkeypatch, Antwort(429), Antwort(429), Antwort(200))
        netz.fetch("https://jambase.test/a")
        assert len(netz.MELDUNGEN) == 1
        assert "bittet um Ruhe" in netz.MELDUNGEN[0]


class TestAbgewiesen:
    def test_403_wird_nicht_wiederholt(self, monkeypatch):
        d = dienst(monkeypatch, *[Antwort(403)] * 5)
        assert netz.fetch("https://ft.test/a") is None
        assert d.gefragt == 1
        assert netz.FEHLGESCHLAGEN == ["https://ft.test/a (HTTPError 403)"]

    def test_nach_fuenf_absagen_ist_ruhe(self, monkeypatch):
        d = dienst(monkeypatch, *[Antwort(403)] * 20)
        for i in range(8):
            netz.fetch(f"https://ft.test/{i}")
        assert d.gefragt == netz.SPERRE_AB
        assert netz.weist_ab("https://ft.test/noch-eine")


class TestNetzfehler:
    def test_zweiter_anlauf_hilft(self, monkeypatch):
        class Wackelig(Dienst):
            def get(self, url, **k):
                self.gefragt += 1
                if self.gefragt == 1:
                    raise ConnectionError("weg")
                return Antwort(200, "<p>doch</p>")

        d = Wackelig()
        monkeypatch.setattr(netz, "session", lambda: d)
        assert netz.fetch("https://x.test/a") == "<p>doch</p>"
        assert netz.FEHLGESCHLAGEN == []

    def test_nach_drei_versuchen_gemeldet(self, monkeypatch):
        class Tot(Dienst):
            def get(self, url, **k):
                self.gefragt += 1
                raise ConnectionError("weg")

        d = Tot()
        monkeypatch.setattr(netz, "session", lambda: d)
        assert netz.fetch("https://x.test/a") is None
        assert d.gefragt == 3
        assert netz.FEHLGESCHLAGEN == ["https://x.test/a (ConnectionError)"]

    def test_vierhundertvier_ist_kein_fehler(self, monkeypatch):
        d = dienst(monkeypatch, Antwort(404))
        assert netz.fetch("https://x.test/weg") is None
        assert d.gefragt == 1
        assert netz.FEHLGESCHLAGEN == []
