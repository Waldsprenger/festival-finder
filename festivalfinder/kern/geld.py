"""Preise: lesen, prüfen, umrechnen — an einer Stelle.

Drei Fragen, drei Funktionen:

* `ist_preis(text)` — steht da überhaupt ein Preis? Auf einer Seite stand
  „Preis: Pop Punk"; das Genre war ins Preisfeld gerutscht.
* `betrag(text)` — welche Zahl steht da? „8.900.00" ist 8900,00.
* `in_euro(text)` — was kostet der günstigste Einstieg in Euro? Danach wird
  auf der Seite gefiltert und sortiert.
"""

import re

from .text import clean

#: Näherungswerte, nur für Filter und Sortierung — genauer als die
#: Preisangaben der Quellen muss das nicht sein.
KURSE = {"EUR": 1.0, "€": 1.0, "CHF": 1.06, "GBP": 1.17, "USD": 0.92,
         "DKK": 0.134, "SEK": 0.088, "NOK": 0.086, "PLN": 0.235,
         "CZK": 0.040, "HUF": 0.0025}

#: Welche Währung in welchem Land gilt — nur die mit Kurs. Eine Grenze in einer
#: Währung, die niemand umrechnen kann, wäre eine Zahl ohne Bedeutung.
WAEHRUNG_LAND = {
    "CH": "CHF", "LI": "CHF",
    "GB": "GBP", "GG": "GBP", "JE": "GBP", "IM": "GBP", "GI": "GBP",
    "US": "USD", "EC": "USD", "SV": "USD", "PA": "USD",
    "DK": "DKK", "GL": "DKK", "FO": "DKK",
    "SE": "SEK", "NO": "NOK", "SJ": "NOK",
    "PL": "PLN", "CZ": "CZK", "HU": "HUF",
}

#: Die Währungen als Muster, abgeleitet aus der Kurstabelle
WAEHRUNG = "|".join(re.escape(w) for w in sorted(KURSE, key=len, reverse=True))

#: „1.234,56", „1234.56", „49"
ZAHL = r"\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:\.\d{1,2})?"

# Spannen zuerst, damit „19,80 - 27,50 €" den unteren Wert liefert
_SPANNE = re.compile(rf"({ZAHL})\s*(?:-|–|bis)\s*(?:{ZAHL})\s*({WAEHRUNG})", re.I)
_ZAHL_WAEHRUNG = re.compile(rf"({ZAHL})\s*({WAEHRUNG})", re.I)
_WAEHRUNG_ZAHL = re.compile(rf"({WAEHRUNG})\s*({ZAHL})", re.I)
_ERSTER_PREIS = re.compile(rf"({ZAHL})\s*(?:{WAEHRUNG})|(?:{WAEHRUNG})\s*({ZAHL})", re.I)
_IRGENDEINE = re.compile(WAEHRUNG, re.I)
_NACKTE_ZAHL = re.compile(ZAHL)
_ZIFFER_AB_EINS = re.compile(r"[1-9]")
_KEIN_BETRAGSZEICHEN = re.compile(r"[^\d.,]")

#: Freier Eintritt ist eine Preisangabe, auch ohne Zahl — „Spende" und „zahl
#: was du willst" eingeschlossen.
KOSTENLOS = re.compile(r"kostenlos|gratis|freier eintritt|umsonst|frei\b|spende|"
                       r"zahl[,]?\s*was|pay what", re.I)

#: Über diesem Betrag ist es kein Festivalticket mehr, sondern eine Zahl aus
#: einem anderen Feld.
OBERGRENZE = 5000


def ist_preis(roh: str) -> str:
    """Der Preistext, sofern es überhaupt einer ist; sonst leer.

    Eine Ziffer allein genügt nicht: „ab EUR ,00" ist ein leer gebliebenes
    Feld, keine Preisangabe.
    """
    text = clean(roh)
    return text if text and (_ZIFFER_AB_EINS.search(text) or KOSTENLOS.search(text)) else ""


def betrag(roh: str) -> float | None:
    """Die Zahl aus einer Preisangabe; None, wenn es keine ist.

    Der letzte Punkt trennt die Nachkommastellen, alle übrigen sind
    Tausenderpunkte: „1690.00", aber auch „8.900.00".
    """
    text = _KEIN_BETRAGSZEICHEN.sub("", roh or "").replace(",", ".")
    if not text:
        return None
    if text.count(".") > 1:
        kopf, _, schwanz = text.rpartition(".")
        text = kopf.replace(".", "") + "." + schwanz
    try:
        return float(text)
    except ValueError:
        return None


def _zahl(roh: str) -> float | None:
    """Eine Zahl im Fließtext — deutsches („1.234,56") oder englisches Format."""
    roh = roh.strip()
    if "," in roh:
        roh = roh.replace(".", "").replace(",", ".")
    try:
        return float(roh)
    except ValueError:
        return None


def _kurs(waehrung: str) -> float:
    return KURSE.get(waehrung if waehrung == "€" else waehrung.upper(), 1.0)


def in_euro(text: str) -> float | None:
    """Günstigster Einstiegspreis in Euro; None, wenn nicht ermittelbar.

    Nur Zahlen, die unmittelbar an einer Währung hängen, gelten als Preis —
    sonst würde „VVK 199 EUR (Stufe 2)" als 2 EUR gelesen.
    """
    if not text:
        return None

    kandidaten: list[float] = []
    for m in _SPANNE.finditer(text):                     # „19,80 - 27,50 €"
        if (v := _zahl(m[1])) is not None:
            kandidaten.append(v * _kurs(m[2]))
    for muster, zahl, waehrung in ((_ZAHL_WAEHRUNG, 1, 2), (_WAEHRUNG_ZAHL, 2, 1)):
        for m in muster.finditer(text):                  # „351 €" / „EUR 49,50"
            if (v := _zahl(m[zahl])) is not None:
                kandidaten.append(v * _kurs(m[waehrung]))
    kandidaten = [c for c in kandidaten if 0 < c <= OBERGRENZE]

    # Ein Gratis-Hinweis zählt nur vor der ersten Preisangabe: „Kostenlos bis
    # 39 EUR je Event" ist freier Eintritt, bei „VVK 45-172 EUR (Pay what you
    # can)" hebt der Nachsatz den Preis nicht auf.
    if (frei := KOSTENLOS.search(text)):
        stelle = _ERSTER_PREIS.search(text)
        if not kandidaten or (stelle and frei.start() < stelle.start()):
            return 0.0

    if not kandidaten and not _IRGENDEINE.search(text):
        # Währungslos („VVK 42,95 (Stufe 2)"): die erste Zahl, nicht die
        # kleinste — die Nachsätze nennen Preisstufen.
        for m in _NACKTE_ZAHL.finditer(text):
            v = _zahl(m[0])
            if v is not None and 0 < v <= OBERGRENZE:
                return round(v, 2)
        return None

    return round(min(kandidaten), 2) if kandidaten else None
