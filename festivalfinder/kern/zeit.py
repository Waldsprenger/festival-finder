"""Termine: von jeder Schreibweise der Quellen zu einem `date`.

Einmal gelesen, ist ein Termin ein `date` und verhält sich wie eines: `a < b`
stimmt, `a.year` ist das Jahr, kein Termin ist `None`. Die Quellen schreiben
Termine in vier Formen:

    2026-08-19, 2026-08-19T18:00      Datenblätter (schema.org)
    19.08.2026                        deutschsprachige Quellen
    August 19, 2026 / 19 Aug 2026     englischsprachige Quellen
    19-Aug-26                         festivalnetworks
"""

import re
from datetime import date

#: Monatsnamen deutsch und englisch, erkannt an den ersten drei Buchstaben:
#: „Aug", „Aug.", „August", „Mär", „March".
_MONATE = {
    1: ("januar", "january"), 2: ("februar", "february"),
    3: ("maerz", "märz", "march"), 4: ("april",), 5: ("mai", "may"),
    6: ("juni", "june"), 7: ("juli", "july"), 8: ("august",),
    9: ("september",), 10: ("oktober", "october"), 11: ("november",),
    12: ("dezember", "december"),
}

#: Deutsche Monatsnamen in Reihenfolge — festivalticker führt Monatsarchive
#: unter genau diesen Namen.
MONATE = [_MONATE[nr][0] for nr in range(1, 13)]

_NACH_ANFANG = {name[:3]: nr for nr, namen in _MONATE.items() for name in namen}

_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_DEUTSCH = re.compile(r"(\d{1,2})\.\s?(\d{1,2})\.(\d{4})")
_MONAT_ZUERST = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s*(\d{4})")   # Aug 19, 2026
_TAG_ZUERST = re.compile(r"(\d{1,2})\.?\s+([A-Za-z]{3,9})\.?\s+(\d{4})")    # 19 Aug 2026
_KURZ = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{2})$")                   # 27-Aug-26


def monat_nummer(name: str) -> int:
    """Monatsnummer aus einem Namen, ausgeschrieben oder abgekürzt; 0 wenn keiner."""
    return _NACH_ANFANG.get((name or "").lower().strip(". ")[:3], 0)


def _bauen(jahr: int, monat: int, tag: int) -> date | None:
    """Ein Datum, sofern es das wirklich gibt — die Quellen schreiben auch den
    31. Februar."""
    try:
        return date(jahr, monat, tag)
    except ValueError:
        return None


def aus_iso(wert) -> date | None:
    """„2026-08-19" oder „2026-08-19T18:00"; führende Nullen dürfen fehlen."""
    m = _ISO.match(str(wert or "").strip())
    return _bauen(int(m[1]), int(m[2]), int(m[3])) if m else None


def aus_deutsch(wert) -> date | None:
    """„19.08.2026", auch mit Leerzeichen („26. 7.2026")."""
    m = _DEUTSCH.match(str(wert or "").strip())
    return _bauen(int(m[3]), int(m[2]), int(m[1])) if m else None


def aus_englisch(wert) -> date | None:
    """„August 19, 2026" oder „19 Aug 2026"."""
    text = str(wert or "").strip()
    for muster, jahr, monat, tag in ((_MONAT_ZUERST, 3, 1, 2), (_TAG_ZUERST, 3, 2, 1)):
        if (m := muster.match(text)):
            nr = monat_nummer(m[monat])
            return _bauen(int(m[jahr]), nr, int(m[tag])) if nr else None
    return None


def aus_kurz(wert) -> date | None:
    """„27-Aug-26" — zweistelliges Jahr, wie festivalnetworks es liefert."""
    m = _KURZ.match(str(wert or "").strip())
    nr = monat_nummer(m[2]) if m else 0
    return _bauen(2000 + int(m[3]), nr, int(m[1])) if nr else None


def deutsch(tag: date | None) -> str:
    """„19.08.2026"; ohne Termin die leere Zeichenkette."""
    return f"{tag.day:02d}.{tag.month:02d}.{tag.year}" if tag else ""


def iso(tag: date | None) -> str:
    """„2026-08-19"; ohne Termin die leere Zeichenkette."""
    return tag.isoformat() if tag else ""


def ueberlappt(von_a: date | None, bis_a: date | None,
               von_b: date | None, bis_b: date | None) -> bool:
    """Überschneiden sich die beiden Termine?

    Die Quellen zählen Anreise- und Aufbautage verschieden (Neuborn Open Air:
    ab 27.08. bei der einen, ab 28.08. bei der anderen). Ein Überlapp erfasst
    das, ohne zwei Feste zu verschmelzen, die Wochen auseinanderliegen.
    """
    if not von_a or not von_b:
        return False
    return von_a <= (bis_b or von_b) and von_b <= (bis_a or von_a)


def abstand_tage(a: date | None, b: date | None) -> int | None:
    """Abstand zweier Termine in Tagen; None, wenn einer fehlt."""
    return abs((a - b).days) if a and b else None


def tage_her(stand: str, heute: str) -> int:
    """Tage zwischen zwei ISO-Daten; ohne lesbares Datum: unendlich lange her."""
    try:
        return (date.fromisoformat(heute) - date.fromisoformat(stand)).days
    except ValueError:
        return 10 ** 6
