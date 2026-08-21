"""Seiten abrufen, zwischenspeichern und lesbar machen.

Jede abgerufene Seite landet unter `cache/`, benannt nach dem SHA-1 ihrer
Adresse. Ein zweiter Lauf am selben Tag kommt damit ohne einen einzigen Abruf
bei den Quellen aus — und die Quellen tragen nur die Last, die nötig ist.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from gemeinsam import CACHE

# Ohne Browserkennung antworten mehrere Quellen mit 403.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}

MAX_AGE_H = 24.0     # per --max-age gesetzt; älterer Cache wird neu geladen
FRISCH = False       # per --frisch: Cache beim Lesen übergehen

# Vier gleichzeitige Verbindungen, quellenübergreifend gedeckelt
BREMSE = threading.Semaphore(4)
_lokal = threading.local()

#: Adressen, die auch nach drei Versuchen nicht antworteten
FEHLGESCHLAGEN: list[str] = []
#: Hinweise der Leser, etwa auf eine Listenseite ohne Inhalt
MELDUNGEN: list[str] = []
#: Rechner, die den Lauf mit 403 abweisen, und wie oft
ABGEWIESEN: dict[str, int] = {}
#: So oft wird eine Ablehnung hingenommen, dann bleibt der Rechner in Ruhe
SPERRE_AB = 5


def einstellen(max_age_h: float, frisch: bool) -> None:
    """Cachealter und Frischlauf setzen (aus den Aufrufparametern)."""
    global MAX_AGE_H, FRISCH
    MAX_AGE_H, FRISCH = max_age_h, frisch


def session() -> requests.Session:
    """Je Arbeitsfaden eine Verbindung, damit sie offen bleiben kann."""
    s = getattr(_lokal, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        _lokal.s = s
    return s


def _cachedatei(url: str):
    return CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html")


def code_von(exc: Exception) -> int | None:
    """Der Statuscode hinter einem Fehler, falls es einen gibt."""
    return getattr(getattr(exc, "response", None), "status_code", None)


def weist_ab(url: str) -> bool:
    """Hat dieser Rechner den Lauf schon oft genug abgewiesen?"""
    return ABGEWIESEN.get(urlparse(url).netloc, 0) >= SPERRE_AB


def abweisung_vermerken(url: str, code: int | None) -> bool:
    """Eine Ablehnung zählen; True, sobald der Rechner als abweisend gilt.

    Ein 403 ist eine Entscheidung des Betreibers. Sie wird nicht umgangen -
    aber auch nicht 213-mal je Lauf erneut ausprobiert: festivalticker weist
    den Lauf auf fremden Servern bei jeder einzelnen Seite ab.
    """
    if code != 403:
        return False
    haus = urlparse(url).netloc
    ABGEWIESEN[haus] = ABGEWIESEN.get(haus, 0) + 1
    if ABGEWIESEN[haus] == SPERRE_AB:
        melde(f"{haus} weist den Lauf ab (403) - keine weiteren Anfragen dorthin")
    return ABGEWIESEN[haus] >= SPERRE_AB


def fetch(url: str, retries: int = 3) -> str | None:
    """GET mit Plattencache; None, wenn die Seite nicht ladbar ist."""
    path = _cachedatei(url)
    if not FRISCH and path.exists() and path.stat().st_size > 0:
        alter_h = (time.time() - path.stat().st_mtime) / 3600
        if MAX_AGE_H <= 0 or alter_h < MAX_AGE_H:
            return path.read_text(encoding="utf-8", errors="replace")
    # Gespeicherte Seiten kommen weiter aus dem Cache; nur neu gefragt wird
    # dort nicht mehr, wo der Lauf ohnehin abgewiesen wird.
    if weist_ab(url):
        return None
    for versuch in range(retries):
        try:
            with BREMSE:
                r = session().get(url, timeout=45)
                time.sleep(0.3)
            if r.status_code in (404, 410):
                return None
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            path.write_text(r.text, encoding="utf-8", errors="replace")
            return r.text
        except Exception as exc:
            # Mit dem Statuscode: 403 ist eine Entscheidung des Betreibers,
            # 429 oder 503 heißt "zu schnell" - das eine ist zu achten, das
            # andere abzustellen. Gegen ein 403 hilft auch kein zweiter Anlauf.
            code = code_von(exc)
            if versuch == retries - 1 or code == 403:
                art = exc.__class__.__name__ + (f" {code}" if code else "")
                FEHLGESCHLAGEN.append(f"{url} ({art})")
                abweisung_vermerken(url, code)
                return None
            time.sleep(2.0 * (versuch + 1))
    return None


def endziel(link: str, eigene_domain: str) -> str:
    """Wohin führt eine Weiterleitung? Leer, wenn sie im Haus bleibt.

    festivalticker verlinkt jede offizielle Festivalseite über eine eigene
    Weiterleitung. Das Ziel ändert sich so gut wie nie, die Anfrage danach
    kostete aber jeden Lauf hunderte Verbindungen - deshalb wird es gemerkt.
    """
    merker = CACHE / (hashlib.sha1(("HEAD " + link).encode()).hexdigest() + ".txt")
    if not FRISCH and merker.exists():
        return merker.read_text(encoding="utf-8")
    try:
        with BREMSE:
            r = session().head(link, allow_redirects=True, timeout=20)
        ziel = r.url if eigene_domain not in r.url else ""
    except Exception:
        return ""                      # Fehlschläge nicht festschreiben
    merker.write_text(ziel, encoding="utf-8")
    return ziel


def datei_holen(url: str, ziel, was: str = "") -> bytes:
    """Große Datei einmal herunterladen und auf Platte behalten.

    Ortsverzeichnis und Kartengrenzen ändern sich praktisch nie; ohne diesen
    Zwischenspeicher lüde jeder Lauf 200 MB GeoNames-Daten erneut.
    """
    if ziel.exists() and ziel.stat().st_size > 0:
        return ziel.read_bytes()
    print(f"  lade {was or ziel.name} …", flush=True)
    r = requests.get(url, headers=HEADERS, timeout=300)
    r.raise_for_status()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    # Erst daneben, dann an den Platz: Ein Abbruch mitten im Schreiben liesse
    # sonst ein halbes ZIP zurück - und weil es Inhalt hat, gälte es beim
    # nächsten Lauf als fertig heruntergeladen.
    daneben = ziel.with_name(ziel.name + ".neu")
    daneben.write_bytes(r.content)
    os.replace(daneben, ziel)
    return r.content


def cache_aufraeumen(seit: float) -> tuple[int, float]:
    """Cachedateien löschen, die seit "seit" niemand angefasst hat.

    Nach einem frischen Lauf ist jede noch verlinkte Seite gerade neu
    geschrieben worden. Was deutlich älter ist, gehört zu Festivals, die es in
    den Quellen nicht mehr gibt — der Speicher wüchse sonst mit jedem Jahrgang.
    Die Frist von einer Woche ist Absicht: Eine Seite, die heute nicht
    antwortet, behält ihren alten Stand und fällt nicht gleich heraus.
    """
    weg, bytes_frei = 0, 0.0
    for datei in list(CACHE.glob("*.html")) + list(CACHE.glob("*.txt")):
        if datei.stat().st_mtime < seit:
            bytes_frei += datei.stat().st_size
            datei.unlink()
            weg += 1
    return weg, bytes_frei / 1e6


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def sitemap_adressen(xml: str | None) -> list[str]:
    """Alle <loc>-Einträge einer Sitemap."""
    return re.findall(r"<loc>([^<]+)</loc>", xml or "")


def json_ld_events(html: str) -> list[dict]:
    """Alle Veranstaltungsblöcke aus dem Datenblatt einer Seite (schema.org)."""
    treffer = []
    for m in re.finditer(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>",
                         html, re.S):
        try:
            daten = json.loads(m.group(1).strip())
        except Exception:
            continue
        stapel = daten if isinstance(daten, list) else [daten]
        while stapel:
            d = stapel.pop()
            if not isinstance(d, dict):
                continue
            if isinstance(d.get("@graph"), list):
                stapel.extend(d["@graph"])
            if str(d.get("@type", "")).lower() in ("event", "festival", "musicevent",
                                                   "musicfestival"):
                treffer.append(d)
    return treffer


def melde(text: str) -> None:
    """Hinweis auf die Fehlerausgabe — Listenseiten, die nicht antworten.

    Gesammelt wird er außerdem: Beim Lauf auf fremden Servern liest niemand
    die Fehlerausgabe, wohl aber den Bericht, der mitveröffentlicht wird.

    Von einem Rechner, der den Lauf ohnehin abweist, kommt keine Seite mehr -
    das einmal zu sagen genügt, es vierzigmal zu wiederholen verdeckt nur die
    übrigen Hinweise.
    """
    adresse = re.search(r"https?://\S+", text)
    if adresse and weist_ab(adresse.group()):
        return
    MELDUNGEN.append(text)
    print(f"  ! {text}", file=sys.stderr)
