"""Die Leser an echten Seiten, nicht an handgeschriebenen Schnipseln.

Die übrigen Tests halten fest, was gemeint ist. Diese hier halten fest, was
die Quellen tatsächlich schicken — dort sassen die letzten Fehler: eine
Bandliste, die Menüpunkte mitzählte, ein Preis mit zwei Punkten, eine
Spielstätte namens „Tickets Ticket".

In `tests/seiten/` liegen je Quelle zwei eingefrorene Seiten (gepackt, zusammen
0,5 MB). Sie ändern sich nicht mehr; ändert sich das Ergebnis, war es der Code.
"""

import gzip
import json
import re
from pathlib import Path

import pytest
from gemeinsam import ist_land
from quellen import QUELLEN
from text import KNOPFBESCHRIFTUNG, betrag, tag_zahl, valid_band

SEITEN = Path(__file__).parent / "seiten"
VERZEICHNIS = json.loads((SEITEN / "verzeichnis.json").read_text(encoding="utf-8"))
LESER = {q.name: q for q in QUELLEN}

#: Zeichen, die man nicht sieht und die trotzdem jeden Vergleich verderben
UNSICHTBAR = re.compile(r"[ ​-‏  ﻿\x00-\x08\x0b-\x1f]")
DATUM = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def lesen(datei: str) -> dict | None:
    eintrag = VERZEICHNIS[datei]
    quelle = LESER[eintrag["quelle"]]
    html = gzip.decompress((SEITEN / datei).read_bytes()).decode("utf-8", "replace")
    if quelle.mit_stammdaten:
        return quelle.lesen(eintrag["url"], html, None)
    return quelle.lesen(eintrag["url"], html)


@pytest.fixture(scope="module", params=sorted(VERZEICHNIS))
def fund(request):
    rec = lesen(request.param)
    assert rec is not None, f"{request.param}: keine Daten aus einer echten Seite"
    return rec


def test_jede_quelle_hat_eine_echte_probe():
    """Quellen mit Seiten liegen als HTML bei, Sammelquellen als ganze Datei."""
    abgedeckt = {e["quelle"] for e in VERZEICHNIS.values()}
    mit_feed = {name for name, q in LESER.items() if q.feed}
    assert abgedeckt | mit_feed == set(LESER),         f"ohne echte Probe: {set(LESER) - abgedeckt - mit_feed}"
    assert (SEITEN / "festivalnetworks_feed.json.gz").exists()


class TestJederFund:
    def test_name_ist_sauber(self, fund):
        name = fund["name"]
        assert name.strip() == name and name
        assert not re.match(r"^\d+\.\s", name), "Zählnummer im Namen"
        assert not re.search(r"\b(19|20)\d{2}$", name), "Jahr im Namen"
        assert not UNSICHTBAR.search(name), "unsichtbares Zeichen im Namen"

    def test_termine_sind_termine(self, fund):
        for feld in ("date_from", "date_to"):
            assert not fund[feld] or DATUM.match(fund[feld]), f"{feld}: {fund[feld]}"
        if fund["date_from"] and fund["date_to"]:
            assert tag_zahl(fund["date_to"]) >= tag_zahl(fund["date_from"])

    def test_jahr_passt_zum_termin(self, fund):
        if fund["date_from"]:
            assert fund["year"] == fund["date_from"][-4:]

    def test_ort_ist_ein_ort_auf_der_erde(self, fund):
        assert not fund["country"] or ist_land(fund["country"])
        assert fund["lat"] is None or (abs(fund["lat"]) <= 90
                                       and abs(fund["lon"]) <= 180)

    def test_postleitzahl_ist_eine(self, fund):
        assert not fund["plz"] or re.fullmatch(r"[A-Z0-9 \-]{3,8}", fund["plz"])

    def test_preis_laesst_sich_lesen(self, fund):
        if fund["price"]:
            assert betrag(fund["price"]) is not None, fund["price"]

    def test_besucherzahl_ist_eine_zahl(self, fund):
        assert not fund["visitors"] or fund["visitors"].isdigit()

    def test_spielstaette_ist_keine_knopfbeschriftung(self, fund):
        v = fund["venue"]
        assert not v or (len(v) <= 60 and not KNOPFBESCHRIFTUNG.match(v)), v

    def test_webseite_ist_eine_adresse(self, fund):
        assert not fund["website"] or fund["website"].startswith("http")

    def test_lineup_enthaelt_nur_bands(self, fund):
        for band in fund["lineup"]:
            assert valid_band(band), band
            assert "http" not in band and "\n" not in band
            assert not UNSICHTBAR.search(band)
            assert len(band) <= 80
        assert len(set(fund["lineup"])) == len(fund["lineup"]), "Band doppelt"
        assert fund["name"] not in fund["lineup"], "Festival steht im eigenen Lineup"

    def test_kein_feld_traegt_unsichtbare_zeichen(self, fund):
        for feld, wert in fund.items():
            if isinstance(wert, str):
                assert not UNSICHTBAR.search(wert), f"{feld}: {wert!r}"
                assert wert.strip() == wert, f"{feld} mit Leerraum am Rand: {wert!r}"


class TestErwartung:
    """Welches Fest hinter der Seite steckt — schlägt an, wenn ein Leser abdriftet."""

    @pytest.mark.parametrize("datei", sorted(VERZEICHNIS))
    def test_gelesenes_festival_bleibt_dasselbe(self, datei):
        rec = lesen(datei)
        assert rec, datei
        # Die Schreibweise darf sich unterscheiden (Alias), das Fest nicht.
        gemeint = VERZEICHNIS[datei]["festival"].casefold()
        gelesen = rec["name"].casefold()
        assert (gelesen in gemeint or gemeint in gelesen
                or gelesen.split()[0] == gemeint.split()[0]), \
            f"{datei}: {rec['name']!r} statt {VERZEICHNIS[datei]['festival']!r}"


class TestWennDieSeiteSichAendert:
    """Quellen bauen ihre Seiten um. Dann darf ein Leser nichts finden -
    aber er darf nicht abstürzen und schon gar nichts erfinden."""

    @pytest.mark.parametrize("datei", sorted(VERZEICHNIS))
    @pytest.mark.parametrize("art", ["leer", "abgeschnitten", "nur_text", "ohne_html"])
    def test_kein_absturz_bei_kaputter_seite(self, datei, art):
        eintrag = VERZEICHNIS[datei]
        quelle = LESER[eintrag["quelle"]]
        html = gzip.decompress((SEITEN / datei).read_bytes()).decode("utf-8", "replace")
        kaputt = {
            "leer": "",
            "abgeschnitten": html[:len(html) // 3],
            "nur_text": re.sub(r"<[^>]+>", " ", html),
            "ohne_html": "Nur ein Satz ohne jede Auszeichnung.",
        }[art]
        rec = (quelle.lesen(eintrag["url"], kaputt, None) if quelle.mit_stammdaten
               else quelle.lesen(eintrag["url"], kaputt))
        if rec is None:
            return
        # Was trotzdem herauskommt, muss dieselben Regeln erfüllen wie sonst
        assert isinstance(rec["name"], str)
        assert not rec["date_from"] or DATUM.match(rec["date_from"])
        assert not rec["visitors"] or rec["visitors"].isdigit()
        assert all(valid_band(b) for b in rec["lineup"])
