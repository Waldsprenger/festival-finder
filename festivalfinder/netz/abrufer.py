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

* **403** — eine Absage. Sie wird geachtet: kein zweiter Anlauf, und nach
  fünf Absagen bleibt der Rechner für den Rest des Laufs in Ruhe. Umgangen
  wird nichts.
* **429** — „zu viele Anfragen", also unsere eigene Ungeduld. Der erste
  weltweite Lauf verlangte jambase 2.348 Seiten ab und bekam 1.575-mal ein
  429; nur 766 Seiten kamen an. Die richtige Antwort darauf ist warten.

Auf ein 429 zu warten genügt aber nicht: Nicht jeder Rechner sagt, dass es
ihm zu schnell geht. festivalticker sperrte im August 2026 die Adresse des
eigenen Rechners wegen zu vieler Anfragen in zu kurzer Zeit — und meldete das
mit 403, ohne Vorwarnung. Deshalb hält der Abrufer zu jedem Rechner einen
Mindestabstand ein, bevor überhaupt etwas zurückkommt.
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
#: Länger hält ein „Retry-After" den Rechner nicht am Stück an
PAUSE_MAX = 120.0
#: So oft wird eine Bitte um Ruhe erfüllt, bevor die Seite liegen bleibt
GEDULD_429 = 4
#: Mindestabstand in Sekunden zwischen zwei Anfragen an denselben Rechner,
#: von Beginn zu Beginn gezählt — gleich, wie viele Arbeitsfäden gerade fragen.
#: Höchstens vier Anfragen je Sekunde, etwa so viel wie bisher, nur ohne Spitzen.
ABSTAND = 0.25
#: Rechner, die mehr Abstand brauchen, als ihre Antworten verraten.
#: festivalticker sperrt bei zu dichter Folge die Adresse, statt um Ruhe zu
#: bitten. Ein voller Durchgang mit rund 2.000 Seiten dauert so gut 100
#: Minuten — die Alternative ist, gar nichts mehr zu bekommen.
#: jambase bat im Lauf vom 4. Oktober 2026 nach hundert Seiten in knapp
#: 0,4 Sekunden Abstand um Ruhe. Eine Sekunde kostet nichts: Die Quellen
#: sammeln zugleich, und festivalticker braucht ohnehin länger.
ABSTAND_JE_HAUS = {"www.festivalticker.de": 3.0, "www.jambase.com": 1.0}


def code_von(exc: Exception) -> int | None:
    """Der Statuscode hinter einem Fehler, falls es einen gibt."""
    return getattr(getattr(exc, "response", None), "status_code", None)


class Abrufer:
    """Holt Seiten und merkt sich, was dabei schiefging."""

    def __init__(self, *, cache: Path = CACHE, max_age_h: float = 24.0,
                 frisch: bool = False, gleichzeitig: int = 8):
        self.cache = cache
        self.max_age_h = max_age_h
        self.frisch = frisch
        #: Gleichzeitige Verbindungen über alle Quellen. Die Rücksicht auf den
        #: einzelnen Rechner regelt der Abstand; das hier schont die eigene
        #: Leitung, seit alle Quellen zugleich sammeln.
        self.bremse = threading.Semaphore(gleichzeitig)
        self._lokal = threading.local()

        #: Adressen, die auch nach drei Versuchen nicht antworteten
        self.fehlgeschlagen: list[str] = []
        #: Hinweise der Leser, etwa auf eine Listenseite ohne Inhalt
        self.meldungen: list[str] = []
        #: Rechner, die den Lauf mit 403 abweisen, und wie oft
        self.abgewiesen: dict[str, int] = {}
        #: Rechner → Seiten, die dieser Lauf wirklich über das Netz bekam
        self.geholt: dict[str, int] = {}
        #: Wartezeit je Rechner in Sekunden — wächst, wenn er „zu schnell" meldet
        self.verzoegerung: dict[str, float] = {}
        #: Rechner → frühester Zeitpunkt (time.monotonic) der nächsten Anfrage
        self._naechste: dict[str, float] = {}
        #: Rechner → wann zuletzt nach einem 429 der Abstand wuchs
        self._gebremst: dict[str, float] = {}
        self._takt = threading.Lock()
        #: Zählen ist Lesen und Schreiben — aus mehreren Fäden zugleich ginge
        #: dabei mal ein Schritt verloren
        self._zaehlen = threading.Lock()

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

    def hat_geholt(self, urls) -> bool:
        """Kam für diese Adressen in diesem Lauf wirklich etwas über das Netz?

        Ein Lauf aus dem Zwischenspeicher sieht von außen aus wie ein
        erfolgreicher — er liefert dieselben Seiten. Wer daraus einen
        „Stand von heute" macht, datiert alte Daten neu.
        """
        return any(self.geholt.get(urlparse(u).netloc) for u in set(urls))

    def abstand(self, url: str) -> float:
        """So viele Sekunden liegen mindestens zwischen zwei Anfragen dorthin.

        Der feste Abstand des Rechners — oder mehr, wenn er im Lauf schon um
        Ruhe gebeten hat.
        """
        haus = urlparse(url).netloc
        return max(ABSTAND_JE_HAUS.get(haus, ABSTAND),
                   self.verzoegerung.get(haus, 0.0))

    def _anstellen(self, url: str) -> None:
        """Warten, bis dieser Rechner wieder gefragt werden darf.

        Jeder Arbeitsfaden reserviert sich den nächsten freien Zeitpunkt. Vier
        Fäden bei vier verschiedenen Rechnern bleiben so schnell wie vorher,
        vier Fäden bei einem einzigen werden nicht viermal so schnell wie
        erlaubt. Genau das war bei festivalticker geschehen.
        """
        haus = urlparse(url).netloc
        with self._takt:
            jetzt = time.monotonic()
            dran = max(jetzt, self._naechste.get(haus, 0.0))
            self._naechste[haus] = dran + self.abstand(url)
        if dran > jetzt:
            time.sleep(dran - jetzt)

    def langsamer_werden(self, url: str, antwort=None,
                         gefragt_um: float | None = None) -> float:
        """Nach einem „zu viele Anfragen": eine Pause, dann mehr Abstand.

        Zweierlei, das früher eins war. Ein „Retry-After" sagt, wann wieder
        gefragt werden darf — einmal, und für den ganzen Rechner. Früher galt
        es als Abstand für den Rest des Laufs: jambase bat am 4. Oktober 2026
        nach hundert Seiten um Ruhe, und die übrigen 2.160 kamen deshalb im
        Takt von sechs Sekunden, 3,6 Stunden lang. Eine Einzelanfrage
        beantwortete jambase danach in 0,6 Sekunden.

        Der Abstand selbst wächst um eine Sekunde, aber einmal je Schub: Vier
        Fäden, die zugleich abgewiesen werden, haben eine Bitte gehört, nicht
        vier. Erst eine Anfrage, die nach der letzten Bremsung losging
        (`gefragt_um`), zählt als neue Bitte.

        Gibt die Pause zurück, die der Rechner jetzt bekommt.
        """
        haus = urlparse(url).netloc
        gewuenscht = 0.0
        if antwort is not None:
            try:
                gewuenscht = float(antwort.headers.get("Retry-After", "") or 0)
            except (ValueError, AttributeError):
                gewuenscht = 0.0
        with self._takt:
            jetzt = time.monotonic()
            bisher = self.verzoegerung.get(haus, 0.0)
            if gefragt_um is None or gefragt_um >= self._gebremst.get(haus, float("-inf")):
                # Vom Abstand aus, der gerade gilt: jambase bat bei einer
                # Sekunde um Ruhe, und „eine Sekunde Wartezeit" änderte dort
                # nichts — so viel Abstand hatte es schon.
                self.verzoegerung[haus] = min(VERZOEGERUNG_MAX, self.abstand(url) + 1.0)
                self._gebremst[haus] = jetzt
            pause = min(PAUSE_MAX, max(gewuenscht, self.abstand(url)))
            self._naechste[haus] = max(self._naechste.get(haus, 0.0), jetzt + pause)
        if not bisher:
            self.melde(f"{haus} bittet um Ruhe (429) - ab jetzt "
                       f"{self.verzoegerung[haus]:g}s zwischen den Anfragen")
        return pause

    def abweisung_vermerken(self, url: str, code: int | None) -> bool:
        """Eine Ablehnung zählen; True, sobald der Rechner als abweisend gilt.

        Ein 403 ist eine Entscheidung des Betreibers. Sie wird nicht umgangen —
        aber auch nicht 213-mal je Lauf erneut ausprobiert.
        """
        if code != 403:
            return False
        haus = urlparse(url).netloc
        with self._zaehlen:
            self.abgewiesen[haus] = absagen = self.abgewiesen.get(haus, 0) + 1
        if absagen == SPERRE_AB:
            self.melde(f"{haus} weist den Lauf ab (403) - "
                       f"keine weiteren Anfragen dorthin")
        return absagen >= SPERRE_AB

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
        # In einem Stück: `print` schriebe den Zeilenumbruch getrennt, und
        # dazwischen käme die Meldung eines anderen Fadens
        sys.stderr.write(f"  ! {text}\n")
        sys.stderr.flush()

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
                self._anstellen(url)
                with self.bremse:
                    gefragt_um = time.monotonic()
                    r = self.session().get(url, timeout=45)
                if r.status_code in (404, 410):
                    return None
                if r.status_code == 429:
                    # Eine Bitte, kein Fehlschlag. Sie bekommt eigene Anläufe:
                    # Sonst wären nach drei Bitten die regulären Versuche
                    # aufgebraucht und die Seite fiele still heraus. Gewartet
                    # wird beim nächsten Anstellen — die Pause gilt dem ganzen
                    # Rechner, nicht nur diesem Faden.
                    gebeten += 1
                    self.langsamer_werden(url, r, gefragt_um)
                    if gebeten <= GEDULD_429:
                        continue
                    self.fehlgeschlagen.append(f"{url} (HTTPError 429)")
                    return None
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                self._schreib(pfad, r.text)
                haus = urlparse(url).netloc
                with self._zaehlen:
                    self.geholt[haus] = self.geholt.get(haus, 0) + 1
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
            # Die Weiterleitung steht bei festivalticker selbst — sie zählt
            # beim Abstand genauso wie eine Seite.
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
