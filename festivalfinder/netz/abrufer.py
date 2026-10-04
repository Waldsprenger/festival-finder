"""Seiten holen, zwischenspeichern und dabei höflich bleiben.

Jede abgerufene Seite landet unter `cache/`, benannt nach dem SHA-1 ihrer
Adresse und gepackt. Ein zweiter Lauf am selben Tag kommt damit ohne einen
einzigen Abruf aus; ein Lauf mit `offline=True` stellt gar keine Anfrage und
nimmt jede gespeicherte Seite, gleich wie alt.

Rücksicht in drei Stufen:

* **Mindestabstand** je Rechner, von Beginn zu Beginn gezählt, gleich wie
  viele Fäden fragen. festivalticker sperrte im August 2026 die Adresse des
  eigenen Rechners — zu viele Anfragen in zu kurzer Zeit, gemeldet mit 403
  ohne Vorwarnung. Dagegen hilft nur, vorher langsam genug zu sein.
* **429** heißt „zu schnell": einmal pausieren (so lange, wie `Retry-After`
  sagt), dann eine Sekunde mehr Abstand. Eine Bitte um Ruhe ist kein
  Fehlversuch und bekommt eigene Anläufe.
* **403** ist eine Absage. Kein zweiter Anlauf, und nach fünf Absagen bleibt
  der Rechner für den Rest des Laufs in Ruhe. Umgangen wird nichts.
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
#: Weiter als so wächst der Abstand nach Bitten um Ruhe nicht
VERZOEGERUNG_MAX = 8.0
#: Länger hält ein „Retry-After" den Rechner nicht am Stück an
PAUSE_MAX = 120.0
#: So oft wird eine Bitte um Ruhe erfüllt, bevor die Seite liegen bleibt
GEDULD_429 = 4
#: Mindestabstand in Sekunden zwischen zwei Anfragen an denselben Rechner:
#: höchstens vier je Sekunde.
ABSTAND = 0.25
#: Rechner, die mehr Abstand brauchen, als ihre Antworten verraten.
#: festivalticker sperrt bei zu dichter Folge die Adresse, statt um Ruhe zu
#: bitten; jambase bat im Lauf vom 4. Oktober 2026 nach hundert Seiten in
#: 0,4 Sekunden Abstand um Ruhe. Beides kostet nichts, weil alle Quellen
#: zugleich sammeln und festivalticker ohnehin am längsten braucht.
ABSTAND_JE_HAUS = {"www.festivalticker.de": 3.0, "www.jambase.com": 1.0}


def code_von(exc: Exception) -> int | None:
    """Der Statuscode hinter einem Fehler, falls es einen gibt."""
    return getattr(getattr(exc, "response", None), "status_code", None)


def haus(url: str) -> str:
    return urlparse(url).netloc


class Abrufer:
    """Holt Seiten und merkt sich, was dabei schiefging."""

    def __init__(self, *, cache: Path = CACHE, max_age_h: float = 24.0,
                 frisch: bool = False, offline: bool = False, gleichzeitig: int = 8):
        self.cache = cache
        self.max_age_h = max_age_h
        self.frisch = frisch
        self.offline = offline
        #: Gleichzeitige Verbindungen über alle Quellen. Die Rücksicht auf den
        #: einzelnen Rechner regelt der Abstand; das hier schont die eigene Leitung.
        self.bremse = threading.Semaphore(gleichzeitig)
        self._lokal = threading.local()
        self._takt = threading.Lock()

        #: Adressen, die nicht ladbar waren, mit Fehlerart
        self.fehlgeschlagen: list[str] = []
        #: Hinweise für den Bericht, etwa auf eine Listenseite ohne Inhalt
        self.meldungen: list[str] = []
        #: Rechner → Absagen (403)
        self.abgewiesen: dict[str, int] = {}
        #: Rechner → Seiten, die dieser Lauf wirklich über das Netz bekam
        self.geholt: dict[str, int] = {}
        #: Rechner → Abstand nach Bitten um Ruhe, in Sekunden
        self.verzoegerung: dict[str, float] = {}
        #: Rechner → frühester Zeitpunkt (time.monotonic) der nächsten Anfrage
        self._naechste: dict[str, float] = {}
        #: Rechner → wann zuletzt nach einem 429 der Abstand wuchs
        self._gebremst: dict[str, float] = {}

    def session(self) -> requests.Session:
        """Je Arbeitsfaden eine Verbindung, damit sie offen bleiben kann."""
        if (s := getattr(self._lokal, "s", None)) is None:
            s = self._lokal.s = requests.Session()
            s.headers.update(HEADERS)
        return s

    # ---------------- Speicher ----------------

    def _datei(self, url: str) -> Path:
        return self.cache / (hashlib.sha1(url.encode()).hexdigest() + ".html.gz")

    def _lies(self, pfad: Path) -> str | None:
        try:
            return gzip.decompress(pfad.read_bytes()).decode("utf-8", "replace") or None
        except (OSError, EOFError):
            return None

    def _schreib(self, pfad: Path, text: str) -> None:
        # mtime 0: sonst unterschiede sich die gepackte Datei bei jedem Lauf
        schreib_bytes(pfad, gzip.compress(text.encode("utf-8"), 6, mtime=0))

    def _frisch_genug(self, pfad: Path) -> bool:
        if self.offline:
            return True
        if self.frisch:
            return False
        try:
            alter_h = (time.time() - pfad.stat().st_mtime) / 3600
        except OSError:
            return False
        return self.max_age_h <= 0 or alter_h < self.max_age_h

    # ---------------- Rücksicht ----------------

    def weist_ab(self, url: str) -> bool:
        """Hat dieser Rechner den Lauf schon oft genug abgewiesen?"""
        return self.abgewiesen.get(haus(url), 0) >= SPERRE_AB

    def hat_geholt(self, urls) -> bool:
        """Kam für diese Adressen in diesem Lauf wirklich etwas über das Netz?

        Ein Lauf aus dem Zwischenspeicher sieht von außen aus wie ein frischer.
        Wer daraus einen „Stand von heute" macht, datiert alte Daten neu.
        """
        return any(self.geholt.get(haus(u)) for u in set(urls))

    def abstand(self, url: str) -> float:
        """So viele Sekunden liegen mindestens zwischen zwei Anfragen dorthin."""
        h = haus(url)
        return max(ABSTAND_JE_HAUS.get(h, ABSTAND), self.verzoegerung.get(h, 0.0))

    def _anstellen(self, url: str) -> None:
        """Warten, bis dieser Rechner wieder gefragt werden darf.

        Jeder Faden reserviert sich den nächsten freien Zeitpunkt: Vier Fäden
        bei einem Rechner werden so nicht viermal so schnell wie erlaubt.
        """
        h = haus(url)
        with self._takt:
            jetzt = time.monotonic()
            dran = max(jetzt, self._naechste.get(h, 0.0))
            self._naechste[h] = dran + self.abstand(url)
        if dran > jetzt:
            time.sleep(dran - jetzt)

    def langsamer_werden(self, url: str, antwort=None,
                         gefragt_um: float | None = None) -> float:
        """Nach einem „zu viele Anfragen": eine Pause, dann mehr Abstand.

        Ein „Retry-After" gilt einmal, für den ganzen Rechner. Als Takt für den
        Rest des Laufs genommen, kamen bei jambase 2.160 Seiten im Abstand von
        sechs Sekunden — 3,6 Stunden, obwohl jambase in 0,6 Sekunden antwortet.

        Der Abstand wächst um eine Sekunde, gezählt vom Abstand, der gerade
        gilt, und nur einmal je Schub: Vier zugleich abgewiesene Fäden haben
        eine Bitte gehört. Erst eine Anfrage, die nach der letzten Bremsung
        losging (`gefragt_um`), zählt als neue.
        """
        h = haus(url)
        try:
            gewuenscht = float(antwort.headers.get("Retry-After", "") or 0)
        except (ValueError, AttributeError):
            gewuenscht = 0.0
        with self._takt:
            jetzt = time.monotonic()
            bisher = self.verzoegerung.get(h, 0.0)
            if gefragt_um is None or gefragt_um >= self._gebremst.get(h, float("-inf")):
                self.verzoegerung[h] = min(VERZOEGERUNG_MAX, self.abstand(url) + 1.0)
                self._gebremst[h] = jetzt
            pause = min(PAUSE_MAX, max(gewuenscht, self.abstand(url)))
            self._naechste[h] = max(self._naechste.get(h, 0.0), jetzt + pause)
        if not bisher:
            self.melde(f"{h} bittet um Ruhe (429) - ab jetzt "
                       f"{self.verzoegerung[h]:g}s zwischen den Anfragen")
        return pause

    def abweisung_vermerken(self, url: str, code: int | None) -> bool:
        """Eine Ablehnung zählen; True, sobald der Rechner als abweisend gilt."""
        if code != 403:
            return False
        h = haus(url)
        with self._takt:
            self.abgewiesen[h] = absagen = self.abgewiesen.get(h, 0) + 1
        if absagen == SPERRE_AB:
            self.melde(f"{h} weist den Lauf ab (403) - keine weiteren Anfragen dorthin")
        return absagen >= SPERRE_AB

    def melde(self, text: str) -> None:
        """Hinweis in den Bericht und auf die Fehlerausgabe — in einem Stück,
        damit kein anderer Faden dazwischenschreibt. Von einem Rechner, der
        den Lauf abweist, genügt die eine Meldung über die Abweisung."""
        adresse = re.search(r"https?://\S+", text)
        if adresse and self.weist_ab(adresse.group()):
            return
        self.meldungen.append(text)
        sys.stderr.write(f"  ! {text}\n")
        sys.stderr.flush()

    # ---------------- Abruf ----------------

    def fetch(self, url: str, retries: int = 3) -> str | None:
        """GET mit Plattencache; None, wenn die Seite nicht ladbar ist."""
        pfad = self._datei(url)
        if self._frisch_genug(pfad) and (gespeichert := self._lies(pfad)) is not None:
            return gespeichert
        # Gespeicherte Seiten kommen weiter aus dem Cache; neu gefragt wird nur,
        # wo der Lauf nicht abgewiesen wird — und offline nirgends.
        if self.offline or self.weist_ab(url):
            return None

        versuch = gebeten = 0
        while versuch < retries:
            try:
                self._anstellen(url)
                with self.bremse:
                    gefragt_um = time.monotonic()
                    r = self.session().get(url, timeout=45)
                if r.status_code in (404, 410):
                    return None
                if r.status_code == 429:
                    gebeten += 1
                    # Gewartet wird beim nächsten Anstellen — für alle Fäden
                    self.langsamer_werden(url, r, gefragt_um)
                    if gebeten <= GEDULD_429:
                        continue
                    self.fehlgeschlagen.append(f"{url} (HTTPError 429)")
                    return None
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                self._schreib(pfad, r.text)
                with self._takt:
                    self.geholt[haus(url)] = self.geholt.get(haus(url), 0) + 1
                return r.text
            except Exception as exc:
                # 403 ist zu achten, 503 abzuwarten — gegen ein 403 hilft auch
                # kein zweiter Anlauf.
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

        festivalticker verlinkt jede offizielle Seite über eine eigene
        Weiterleitung. Das Ziel ändert sich so gut wie nie, deshalb wird es
        gemerkt; die Abfrage steht beim Abstand an wie jede Seite.
        """
        merker = self.cache / (hashlib.sha1(("HEAD " + link).encode()).hexdigest() + ".txt")
        if (self.offline or not self.frisch) and merker.exists():
            return merker.read_text(encoding="utf-8")
        if self.offline:
            return ""
        try:
            self._anstellen(link)
            with self.bremse:
                r = self.session().head(link, allow_redirects=True, timeout=20)
            ziel = r.url if eigene_domain not in r.url else ""
        except Exception:
            return ""                     # Fehlschläge nicht festschreiben
        merker.write_text(ziel, encoding="utf-8")
        return ziel

    def datei_holen(self, url: str, ziel: Path, was: str = "") -> bytes:
        """Große Datei einmal herunterladen und auf Platte behalten.

        Erst daneben, dann an den Platz: Ein Abbruch ließe sonst ein halbes ZIP
        zurück, das beim nächsten Lauf als fertig gälte.
        """
        if ziel.exists() and ziel.stat().st_size > 0:
            return ziel.read_bytes()
        if self.offline:
            raise FileNotFoundError(f"{ziel.name} fehlt, und offline wird nichts geladen")
        print(f"  lade {was or ziel.name} …", flush=True)
        r = requests.get(url, headers=HEADERS, timeout=300)
        r.raise_for_status()
        ziel.parent.mkdir(parents=True, exist_ok=True)
        schreib_bytes(ziel, r.content)
        return r.content

    def aufraeumen(self, seit: float) -> tuple[int, float]:
        """Cachedateien löschen, die seit „seit" niemand angefasst hat.

        Nach einem frischen Lauf ist jede noch verlinkte Seite gerade neu
        geschrieben; was älter als die Frist ist, gehört zu Festivals, die es
        in den Quellen nicht mehr gibt. Eine Seite, die heute nicht antwortet,
        behält dank der Frist von einer Woche ihren Stand.
        """
        weg, frei = 0, 0
        for datei in [*self.cache.glob("*.html.gz"), *self.cache.glob("*.txt")]:
            info = datei.stat()
            if info.st_mtime < seit:
                frei += info.st_size
                datei.unlink()
                weg += 1
        return weg, frei / 1e6
