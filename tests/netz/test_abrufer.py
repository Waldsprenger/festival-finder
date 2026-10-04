"""Wie der Lauf mit Antworten umgeht, die keine Seite sind.

Drei Fälle, drei verschiedene Antworten darauf:

* **403** — eine Absage. Kein zweiter Anlauf, und nach fünf Absagen bleibt
  der Rechner für den Rest des Laufs in Ruhe.
* **429** — „zu viele Anfragen", also unsere eigene Ungeduld. Der erste
  weltweite Lauf hat jambase 2.348 Seiten abverlangt und dafür 1.575-mal ein
  429 bekommen; nur 766 Seiten kamen an. Die richtige Antwort ist warten.
* **Netzfehler** — noch einmal versuchen, dann aufgeben und melden.

Und einer, der gar keine Antwort braucht: der Mindestabstand je Rechner.
festivalticker hat nie um Ruhe gebeten, sondern gleich die Adresse gesperrt.

Jeder Test bekommt seinen eigenen Abrufer. Vorher stand der Zustand im Modul,
und jeder Test musste ihn von Hand leeren.
"""

import time

import pytest
import requests

from festivalfinder.netz import (ABSTAND, ABSTAND_JE_HAUS, GEDULD_429,
                                 SPERRE_AB, Abrufer)


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

    def test_der_abstand_waechst_je_bitte_um_eine_sekunde(self, abrufer):
        dienst(abrufer, Antwort(429), Antwort(429), Antwort(200))
        abrufer.fetch("https://jambase.test/a")
        assert abrufer.abstand("https://jambase.test/") == ABSTAND + 2.0

    def test_retry_after_gilt_einmal(self, tmp_path, uhr):
        """Ein „Retry-After" ist eine Pause, kein Takt. Als Takt genommen,
        brauchten bei jambase 2.160 Seiten 3,6 Stunden statt einer."""
        abrufer = Abrufer(cache=tmp_path)
        zeiten = []

        class Mitschrift(Dienst):
            def get(self, url, **k):
                zeiten.append(uhr.jetzt)
                return super().get(url, **k)

        abrufer.session = lambda d=Mitschrift(
            Antwort(429, kopf={"Retry-After": "6"})): d
        abrufer.fetch("https://jambase.test/a")
        abrufer.fetch("https://jambase.test/b")
        pause, danach = zeiten[1] - zeiten[0], zeiten[2] - zeiten[1]
        assert pause >= 6.0
        assert danach == abrufer.abstand("https://jambase.test/") == ABSTAND + 1.0

    def test_ein_schub_von_absagen_ist_eine_bitte(self, abrufer):
        """Vier Fäden fragen, alle vier werden abgewiesen: eine Bitte, nicht
        vier — sonst stünde der Abstand gleich bei vier Sekunden."""
        url = "https://jambase.test/a"
        abgeschickt = time.monotonic() - 1.0      # alle vor der ersten Absage los
        abrufer.langsamer_werden(url, Antwort(429), abgeschickt)
        for _ in range(3):
            abrufer.langsamer_werden(url, Antwort(429), abgeschickt)
        assert abrufer.abstand(url) == ABSTAND + 1.0

    def test_die_wartezeit_gilt_fuer_den_ganzen_rechner(self, abrufer):
        dienst(abrufer, Antwort(429), Antwort(200), Antwort(200))
        abrufer.fetch("https://jambase.test/a")
        assert abrufer.abstand("https://jambase.test/andere-seite") == ABSTAND + 1.0
        assert abrufer.abstand("https://woanders.test/seite") == ABSTAND

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


FT = "https://www.festivalticker.de"


class Uhr:
    """Eine Uhr, die nur weitergeht, wenn jemand wartet."""

    def __init__(self):
        self.jetzt = 1000.0
        self.gewartet: list[float] = []

    def monotonic(self):
        return self.jetzt

    def sleep(self, s):
        self.gewartet.append(s)
        self.jetzt += s


@pytest.fixture
def uhr(monkeypatch):
    u = Uhr()
    monkeypatch.setattr("festivalfinder.netz.abrufer.time.monotonic", u.monotonic)
    monkeypatch.setattr("festivalfinder.netz.abrufer.time.sleep", u.sleep)
    return u


class TestAbstand:
    """Nicht jeder Rechner sagt, dass es ihm zu schnell geht.

    festivalticker sperrte im August 2026 die Adresse des eigenen Rechners —
    zu viele Anfragen in zu kurzer Zeit, gemeldet mit 403 statt 429. Vier
    Arbeitsfäden mit je 0,3 Sekunden Pause hatten die Seite mehrmals je
    Sekunde gefragt, rund 2.000 Seiten lang.
    """

    def test_festivalticker_wird_nie_dichter_gefragt_als_erlaubt(self, tmp_path, uhr):
        abrufer = Abrufer(cache=tmp_path)
        zeiten = []

        class Mitschrift(Dienst):
            def get(self, url, **k):
                zeiten.append(uhr.jetzt)
                return super().get(url, **k)

        abrufer.session = lambda d=Mitschrift(): d
        for i in range(5):
            abrufer.fetch(f"{FT}/festival/{i}/")
        abstaende = [b - a for a, b in zip(zeiten, zeiten[1:])]
        assert abstaende and min(abstaende) >= ABSTAND_JE_HAUS["www.festivalticker.de"]

    def test_vier_faeden_machen_einen_rechner_nicht_schneller(self, tmp_path, monkeypatch):
        """Vier Fäden kommen im selben Augenblick an — jeder wartet auf
        seinen eigenen Zeitpunkt, keiner fragt gleichzeitig mit einem anderen."""
        abrufer = Abrufer(cache=tmp_path)
        gewartet = []
        monkeypatch.setattr("festivalfinder.netz.abrufer.time.monotonic", lambda: 1000.0)
        monkeypatch.setattr("festivalfinder.netz.abrufer.time.sleep", gewartet.append)
        for i in range(4):
            abrufer._anstellen(f"{FT}/festival/{i}/")
        schritt = ABSTAND_JE_HAUS["www.festivalticker.de"]
        assert gewartet == [schritt, 2 * schritt, 3 * schritt]

    def test_andere_rechner_warten_nicht_mit(self, tmp_path, uhr):
        abrufer = Abrufer(cache=tmp_path)
        abrufer._anstellen(f"{FT}/a/")
        abrufer._anstellen("https://jambase.test/a")
        assert uhr.gewartet == []

    def test_auch_die_weiterleitung_steht_an(self, tmp_path, uhr):
        """Je Festival fragt der Lauf festivalticker zweimal: nach der Seite
        und nach dem Ziel ihres Website-Links."""

        class Kopf(Dienst):
            def head(self, url, **k):
                self.gefragt += 1
                antwort = Antwort()
                antwort.url = "https://festival.test/"
                return antwort

        abrufer = Abrufer(cache=tmp_path)
        abrufer.session = lambda d=Kopf(): d
        abrufer.fetch(f"{FT}/festival/1/")
        assert abrufer.endziel(f"{FT}/link/1", "festivalticker.de") == "https://festival.test/"
        assert uhr.gewartet == [ABSTAND_JE_HAUS["www.festivalticker.de"]]

    def test_eine_bitte_um_ruhe_zaehlt_vom_festen_abstand_aus(self, abrufer):
        """jambase bat bei einer Sekunde um Ruhe. „Eine Sekunde Wartezeit"
        änderte dort nichts — so viel Abstand hatte es schon."""
        dienst(abrufer, Antwort(429), Antwort(200))
        abrufer.fetch(f"{FT}/a/")
        assert abrufer.abstand(f"{FT}/b/") == ABSTAND_JE_HAUS["www.festivalticker.de"] + 1.0


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

    def test_er_weiss_was_wirklich_ueber_das_netz_kam(self, tmp_path, monkeypatch):
        """Ein Lauf aus dem Zwischenspeicher liefert dieselben Seiten und sieht
        von außen aus wie ein frischer. Wer daraus einen „Stand von heute"
        macht, datiert alte Daten neu — und die Alterswarnung verstummt."""
        monkeypatch.setattr("festivalfinder.netz.abrufer.time.sleep", lambda _s: None)
        erst = Abrufer(cache=tmp_path)
        dienst(erst, Antwort(200, "<p>a</p>"))
        erst.fetch("https://x.test/a")
        assert erst.hat_geholt(["https://x.test/a"]) is True

        # Zweiter Lauf, alles von der Platte: nichts kam über das Netz
        wieder = Abrufer(cache=tmp_path, max_age_h=0)
        d = dienst(wieder, Antwort(200, "<p>a</p>"))
        assert wieder.fetch("https://x.test/a") == "<p>a</p>"
        assert d.gefragt == 0
        assert wieder.hat_geholt(["https://x.test/a"]) is False

    def test_zwei_abrufer_teilen_sich_nichts(self, tmp_path, monkeypatch):
        """Der Kern des Umbaus: kein Zustand im Modul."""
        monkeypatch.setattr("festivalfinder.netz.abrufer.time.sleep", lambda _s: None)
        a, b = Abrufer(cache=tmp_path), Abrufer(cache=tmp_path)
        dienst(a, Antwort(403))
        a.fetch("https://x.test/a")
        assert a.fehlgeschlagen and not b.fehlgeschlagen
