"""Was alle zwölf Verzeichnisse gemeinsam haben.

Eine Quelle beantwortet zwei Fragen: Wie komme ich an ihre Detailseiten, und
wie lese ich eine davon? Was sie unterscheidet, steht in ihrer eigenen Datei;
was mehrere gleich tun, steht hier.
"""

import re

from ..kern.fund import Fund
from ..kern.text import PLZ_VORN, clean
from ..netz import Abrufer


class Quelle:
    """Ein Verzeichnis: wo seine Seiten stehen und wie man sie liest."""

    #: Kurzname, wie er in den Daten und im Bericht auftaucht
    name: str = ""
    #: Startseite — steht in der Fußnote der Webseite
    startseite: str = ""
    #: Ein Satz dazu, wofür diese Quelle gut ist
    zweck: str = ""
    #: Warum diese Quelle gerade nicht gefragt wird — leer, solange sie
    #: mitläuft. Eine ruhende Quelle bekommt bis auf eine Prüfung im Monat
    #: (`wieder_offen`) keine Anfrage, gilt aber auch nicht als ausgefallen.
    ruht: str = ""

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Die Detailseiten ab Jahrgang `seit`."""
        return []

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        """Eine Detailseite auswerten; None, wenn nichts Brauchbares dasteht."""
        raise NotImplementedError

    def sammeldatei(self, netz: Abrufer, seit: int) -> list[Fund] | None:
        """Quellen, die alles in einer Datei liefern, überschreiben das."""
        return None

    def wieder_offen(self, netz: Abrufer, seit: int) -> bool | None:
        """Gibt eine ruhende Quelle wieder heraus, was sie gesperrt hat?
        Mit so wenigen Anfragen wie möglich; None heißt: nicht prüfbar."""
        return None


# --------------------------------------------------------------------------
# Hilfen, die mehrere Leser brauchen
# --------------------------------------------------------------------------

_JAHR = re.compile(r"\b(20\d{2})\b")
#: „Wacken Open Air 2026", „Veerplas Festival - 2026"
_JAHR_HINTEN = re.compile(r"\s*(?:[-–|]\s*)?\b20\d{2}\b\s*$")


def jahr_aus(text: str) -> str:
    """Das erste Jahr 20xx im Text, sonst leer."""
    return m.group(1) if (m := _JAHR.search(text or "")) else ""


def ohne_jahr(name: str) -> str:
    """Der Name ohne angehängtes Jahr — bleibt nichts übrig, der ganze Name."""
    return _JAHR_HINTEN.sub("", name).strip() or name


def felder(flach: str, muster: dict[str, str],
           leer: re.Pattern | None = None) -> dict[str, str]:
    """Beschriftete Felder aus dem geglätteten Seitentext.

    Bei festival-alarm und festivalhopper stehen die Werte über mehrere Zeilen
    verteilt. Gelesen wird deshalb jedes Feld von seiner Beschriftung bis zur
    nächsten bekannten; leer gilt, was `leer` trifft.
    """
    raus: dict[str, str] = {}
    for schluessel, regel in muster.items():
        m = re.search(regel, flach, re.S)
        wert = clean(m.group(1)) if m else ""
        if wert and not (leer and leer.match(wert)):
            raus[schluessel] = wert
    return raus


#: Plus-Code vor dem Ort („9CMG+84 Warrington"), Postleitzahl oder
#: Provinzkürzel dahinter („Clitheroe BB7 4LH", „Jakarta 14430", „Segrate MI")
_PLUSCODE = re.compile(r"^[23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3}\s+")
_PLZ_HINTEN = re.compile(r"\s+(?:[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}|\d{4,6}|[A-Z]{2})$")
#: Was nur Kürzel und Ziffern ist, ist kein Ort: „QC H2X 2S6", „NJ", „B.C.S.",
#: „74080-330"
_KUERZEL = re.compile(r"^[A-Z.\d\s-]+$")


def ort_aus_anschrift(anschrift: str) -> str:
    """Der Ort aus einer einzeiligen Anschrift: „Straße 5, 2000 Maribor, Slovenia".

    Er steht vor dem Land, mit der Postleitzahl davor oder dahinter. Steht
    dort nur ein Kürzel („Montréal, QC H2X 2S6, Canada", „Frankford, NJ
    07826, USA"), ist es der Teil davor.
    """
    teile = [t.strip() for t in (anschrift or "").split(",") if t.strip()]
    for teil in reversed(teile[-3:-1]):
        ort = _PLUSCODE.sub("", teil)
        if (m := PLZ_VORN.match(ort)):
            ort = ort[m.end():]
        if (ort := _PLZ_HINTEN.sub("", ort).strip()) and not _KUERZEL.match(ort):
            return ort
    return ""


def erster_link(s, *, ausser: str = "", text: str = "", titel: str = "",
                ziel_im_text: bool = False, weg: str = "") -> str:
    """Der erste externe Verweis einer Seite, der zu den Bedingungen passt.

    `ausser`: Teil der Adresse, der den Verweis ausschließt (die Quelle
    selbst). `text`/`titel`: Muster, die Beschriftung oder Titel treffen
    müssen. `ziel_im_text`: Die Beschriftung nennt die Adresse selbst
    („www.wacken.com"). `weg`: Adressen, die keine Festivalseite sind.
    """
    for a in s.find_all("a", href=True):
        ziel = a["href"].strip()
        if not ziel.startswith("http") or (ausser and ausser in ziel):
            continue
        if weg and re.search(weg, ziel, re.I):
            continue
        beschriftung = clean(a.get_text()).lower()
        if text and not (re.search(text, beschriftung, re.I)
                         or (titel and re.search(titel, clean(a.get("title", "")), re.I))):
            continue
        if ziel_im_text and beschriftung.replace("www.", "") not in ziel.lower():
            continue
        return ziel
    return ""
