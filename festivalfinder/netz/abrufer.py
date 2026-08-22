"""Seiten holen, zwischenspeichern und dabei höflich bleiben.

Jede abgerufene Seite landet unter `cache/`, benannt nach dem SHA-1 ihrer
Adresse und gepackt. Ein zweiter Lauf am selben Tag kommt damit ohne einen
einzigen Abruf bei den Quellen aus.

Der Abrufer ist ein Objekt und kein Modul voller Variablen. Vorher standen
`FEHLGESCHLAGEN`, `MELDUNGEN`, `ABGEWIESEN` und `VERZOEGERUNG` im Modul; jeder
Test musste sie von Hand leeren, sonst hing sein Ergebnis davon ab, welcher
Test vorher gelaufen war. Jetzt bekommt jeder Lauf und jeder Test einen
eigenen.

Zwei Antworten bekommen eine eigene Behandlung, weil sie Verschiedenes meinen:

* **403** — eine Entscheidung des Betreibers. Sie wird geachtet: kein zweiter
  Anlauf, und nach fünf Absagen bleibt der Rechner für den Rest des Laufs in
  Ruhe. Umgangen wird nichts.
* **429** — „zu viele Anfragen", also unsere eigene Ungeduld. Der erste
  weltweite Lauf verlangte jambase 2.348 Seiten ab und bekam 1.575-mal ein
  429; nur 766 Seiten kamen an. Die richtige Antwort darauf ist warten.
"""

import gzip
import hashlib
import re
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from ..pfade import CACHE, schreib_bytes

#: Ohne Browserkennung antworten mehrere Quellen mit 403.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}

#: So oft wird eine Ablehnung hingenommen, dann bleibt der Rechner in Ruhe
SPERRE_AB = 5
#: Weiter als so wird nicht gebremst; darüber lohnt der Lauf nicht mehr
VERZOEGERUNG_MAX = 8.0
#: So oft wird eine Bitte um Ruhe erfüllt, bevor die Seite liegen bleibt
GEDULD_429 = 4


def code_von(exc: Exception) -> int | None:
    """Der Statuscode hinter einem Fehler, falls es einen gibt."""
    return getattr(getattr(exc, "response", None), "status_code", None)


class Abrufer:
    """Holt Seiten und merkt sich, was dabei schiefging."""

    def __init__(self, *, cache: Path = CACHE, max_age_h: float = 24.0,
                 frisch: bool = False, gleichzeitig: int = 4):
        self.cache = cache
        self.max_age_h = max_age_h
        self.frisch = frisch
        #: Vier gleichzeitige Verbindungen, quellenübergreifend gedeckelt
        self.bremse = threading.Semaphore(gleichzeitig)
        self._lokal = threading.local()

        #: Adressen, die auch nach drei Versuchen nicht antworteten
        self.fehlgeschlagen: list[str] = []
        #: Hinweise der Leser, etwa auf eine Listenseite ohne Inhalt
        self.meldungen: list[str] = []
        #: Rechner, die den Lauf mit 403 abweisen, und wie oft
        self.abgewiesen: dict[str, int] = {}
        #: Wartezeit je Rechner in Sekunden — wächst, wenn er „zu schnell" meldet
        self.verzoegerung: dict[str, float] = {}

    # ---------------- Verbindung ----------------

    def session(self) -> requests.Session:
        """Je Arbeitsfaden eine Verbindung, damit sie offen bleiben kann."""
        s = getattr(self._lokal, "s", None)
        if s is None:
            s = requests.Session()
            s.headers.update(HEADERS)
            self._lokal.s = s
        return s

    # ---------------- Speicher ----------------

    def _datei(self, url: str) -> Path:
        """Wohin eine Seite gespeichert wird: gepackt, benannt nach der Adresse."""
        return self.cache / (hashlib.sha1(url.encode()).hexdigest() + ".html.gz")

    def _lies(self, pfad: Path) -> str | None:
        if pfad.exists() and pfad.stat().st_size > 0:
            try:
                return gzip.decompress(pfad.read_bytes()).decode("utf-8", "replace")
            except (OSError, EOFError):
                return None
        return None

    def _schreib(self, pfad: Path, text: str) -> None:
        # mtime auf 0: Sonst unterscheidet sich die gepackte Datei bei jedem
        # Lauf, auch wenn die Seite dieselbe ist.
        schreib_bytes(pfad, gzip.compress(text.encode("utf-8"), 6, mtime=0))

    def _alter_h(self, pfad: Path) -> float | None:
        if pfad.exists() and pfad.stat().st_size > 0:
            return (time.time() - pfad.stat().st_mtime) / 3600
        return None

    # ---------------- Rücksicht ----------------

    def weist_ab(self, url: str) -> bool:
        """Hat dieser Rechner den Lauf schon oft genug abgewiesen?"""
        return self.abgewiesen.get(urlparse(url).netloc, 0) >= SPERRE_AB

    def _wartezeit(self, url: str) -> float:
        return self.verzoegerung.get(urlparse(url).netloc, 0.0)

    def langsamer_werden(self, url: str, antwort=None) -> float:
        """Nach einem „zu viele Anfragen" künftig warten, bevor gefragt wird.

        Die Wartezeit wächst mit jedem Mal und gilt für den Rest des Laufs.
        Nennt der Server ein „Retry-After", zählt seine Angabe.
        """
        haus = urlparse(url).netloc
        gewuenscht = 0.0
        if antwort is not None:
            try:
                gewuenscht = float(antwort.headers.get("Retry-After", "") or 0)
            except (ValueError, AttributeError):
                gewuenscht = 0.0
        neu = min(VERZOEGERUNG_MAX,
                  max(self.verzoegerung.get(haus, 0.0) + 1.0, gewuenscht))
        if not self.verzoegerung.get(haus):
            self.melde(f"{haus} bittet um Ruhe (429) - ab jetzt "
                       f"{neu:.0f}s zwischen den Anfragen")
        self.verzoegerung[haus] = neu
        return neu

    def abweisung_vermerken(self, url: str, code: int | None) -> bool:
        """Eine Ablehnung zählen; True, sobald der Rechner als abweisend gilt.

        Ein 403 ist eine Entscheidung des Betreibers. Sie wird nicht umgangen —
        aber auch nicht 213-mal je Lauf erneut ausprobiert.
        """
        if code != 403:
            return False
        haus = urlparse(url).netloc
        self.abgewiesen[haus] = self.abgewiesen.get(haus, 0) + 1
        if self.abgewiesen[haus] == SPERRE_AB:
            self.melde(f"{haus} weist den Lauf ab (403) - "
                       f"keine weiteren Anfragen dorthin")
        return self.abgewiesen[haus] >= SPERRE_AB

    def melde(self, text: str) -> None:
        """Hinweis auf die Fehlerausgabe — und in den Bericht.

        Beim Lauf auf fremden Servern liest niemand die Fehlerausgabe, wohl
        aber den Bericht, der mitveröffentlicht wird. Von einem Rechner, der
        den Lauf ohnehin abweist, kommt keine Seite mehr: Das einmal zu sagen
        genügt, es vierzigmal zu wiederholen verdeckt nur die übrigen Hinweise.
        """
        adresse = re.search(r"https?://\S+", text)
        if adresse and self.weist_ab(adresse.group()):
            return
        self.meldungen.append(text)
        print(f"  ! {text}", file=sys.stderr)

    # ---------------- Abruf ----------------

    def fetch(self, url: str, retries: int = 3) -> str | None:
        """GET mit Plattencache; None, wenn die Seite nicht ladbar ist."""
        pfad = self._datei(url)
        alter = None if self.frisch else self._alter_h(pfad)
        if alter is not None and (self.max_age_h <= 0 or alter < self.max_age_h):
            if (gespeichert := self._lies(pfad)) is not None:
                return gespeichert
        # Gespeicherte Seiten kommen weiter aus dem Cache; nur neu gefragt wird
        # dort nicht mehr, wo der Lauf ohnehin abgewiesen wird.
        if self.weist_ab(url):
            return None

        versuch = gebeten = 0
        while versuch < retries:
            try:
                with self.bremse:
                    if (warten := self._wartezeit(url)):
                        time.sleep(warten)
                    r = self.session().get(url, timeout=45)
                    time.sleep(0.3)
                if r.status_code in (404, 410):
                    return None
                if r.status_code == 429:
                    # Eine Bitte, kein Fehlschlag. Sie bekommt eigene Anläufe:
                    # Sonst wären nach drei Bitten die regulären Versuche
                    # aufgebraucht und die Seite fiele still heraus.
                    gebeten += 1
                    time.sleep(self.langsamer_werden(url, r))
                    if gebeten <= GEDULD_429:
                        continue
                    self.fehlgeschlagen.append(f"{url} (HTTPError 429)")
                    return None
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                self._schreib(pfad, r.text)
                return r.text
            except Exception as exc:
                # Mit dem Statuscode: 403 ist eine Entscheidung des Betreibers,
                # 503 heißt „gerade nicht" — das eine ist zu achten, das andere
                # abzuwarten. Gegen ein 403 hilft auch kein zweiter Anlauf.
                code = code_von(exc)
                versuch += 1
                if versuch >= retries or code == 403:
                    art = exc.__class__.__name__ + (f" {code}" if code else "")
                    self.fehlgeschlagen.append(f"{url} ({art})")
                    self.abweisung_vermerken(url, code)
                    return None
                time.sleep(2.0 * versuch)
        return None

    def endziel(self, link: str, eigene_domain: str) -> str:
        """Wohin führt eine Weiterleitung? Leer, wenn sie im Haus bleibt.

        festivalticker verlinkt jede offizielle Festivalseite über eine eigene
        Weiterleitung. Das Ziel ändert sich so gut wie nie, die Anfrage danach
        kostete aber jeden Lauf hunderte Verbindungen — deshalb wird es gemerkt.
        """
        merker = self.cache / (hashlib.sha1(("HEAD " + link).encode()).hexdigest()
                               + ".txt")
        if not self.frisch and merker.exists():
            return merker.read_text(encoding="utf-8")
        try:
            with self.bremse:
                r = self.session().head(link, allow_redirects=True, timeout=20)
            ziel = r.url if eigene_domain not in r.url else ""
        except Exception:
            return ""                     # Fehlschläge nicht festschreiben
        merker.write_text(ziel, encoding="utf-8")
        return ziel

    def datei_holen(self, url: str, ziel: Path, was: str = "") -> bytes:
        """Große Datei einmal herunterladen und auf Platte behalten.

        Ortsverzeichnis und Kartengrenzen ändern sich praktisch nie; ohne
        diesen Zwischenspeicher lüde jeder Lauf 200 MB GeoNames-Daten erneut.
        """
        if ziel.exists() and ziel.stat().st_size > 0:
            return ziel.read_bytes()
        print(f"  lade {was or ziel.name} …", flush=True)
        r = requests.get(url, headers=HEADERS, timeout=300)
        r.raise_for_status()
        ziel.parent.mkdir(parents=True, exist_ok=True)
        # Erst daneben, dann an den Platz: Ein Abbruch mitten im Schreiben
        # ließe sonst ein halbes ZIP zurück — und weil es Inhalt hat, gälte es
        # beim nächsten Lauf als fertig heruntergeladen.
        schreib_bytes(ziel, r.content)
        return r.content

    def aufraeumen(self, seit: float) -> tuple[int, float]:
        """Cachedateien löschen, die seit „seit" niemand angefasst hat.

        Nach einem frischen Lauf ist jede noch verlinkte Seite gerade neu
        geschrieben worden. Was deutlich älter ist, gehört zu Festivals, die es
        in den Quellen nicht mehr gibt. Die Frist von einer Woche ist Absicht:
        Eine Seite, die heute nicht antwortet, behält ihren Stand.
        """
        weg, frei = 0, 0.0
        for datei in list(self.cache.glob("*.html.gz")) + list(self.cache.glob("*.txt")):
            if datei.stat().st_mtime < seit:
                frei += datei.stat().st_size
                datei.unlink()
                weg += 1
        return weg, frei / 1e6
