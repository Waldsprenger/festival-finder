"""Namen und Daten vereinheitlichen.

Die Quellen schreiben dieselbe Band und dasselbe Festival auf ein Dutzend
Arten. Hier stehen die Schlüssel, über die sie zusammenfinden — und die
Prüfungen, die Beschreibungsreste von echten Bandnamen trennen.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date

from gemeinsam import DATA


def clean(text: str | None) -> str:
    """Mehrfache Leerzeichen und Zeilenumbrüche zu einem Leerzeichen."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Schlüssel
# --------------------------------------------------------------------------

_ERSATZ = {
    "&": " and ", "+": " and ", "’": "'", "´": "'", "`": "'",
    "–": "-", "—": "-", "…": "",
}

# Buchstaben, die NFKD nicht zerlegt - sonst fielen sie ersatzlos weg und
# "Aħna" würde zu "Ana"
_SONDERZEICHEN = (("ß", "ss"), ("ø", "o"), ("æ", "ae"), ("œ", "oe"), ("đ", "d"),
                  ("ħ", "h"), ("ł", "l"), ("ı", "i"), ("þ", "th"), ("ð", "d"))


def fold(value: str) -> str:
    """Aggressiver Schlüssel für den Namensvergleich."""
    v = unicodedata.normalize("NFKD", value.lower())
    v = "".join(c for c in v if not unicodedata.combining(c))
    for a, b in _SONDERZEICHEN:
        v = v.replace(a, b)
    for a, b in _ERSATZ.items():
        v = v.replace(a, b)
    v = re.sub(r"\b(feat|ft|featuring|vs|with|und|and)\b", " and ", v)
    v = re.sub(r"[^a-z0-9]+", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    v = re.sub(r"^(the|die|der|das|los|las|les)\s+", "", v)
    v = re.sub(r"\s+(band|live|dj ?set|djset|acoustic)$", "", v)
    return v.strip()


def _zusammen(gefaltet: str) -> str:
    """Getrennt- und Zusammenschreibung meinen dieselbe Band.

    "1000 Mods" und "1000mods" gehören zusammen. Bei kurzen Namen bleibt die
    Trennung erhalten, weil dort verschiedene Acts zusammenfielen ("B-One"
    und "Bone").
    """
    eng = gefaltet.replace(" ", "")
    return eng if len(eng) >= 5 else gefaltet


def _lade_aliase() -> tuple[dict[str, str], dict[str, str]]:
    """Kürzel aus data/band_aliase.json: Schlüssel → Name, Schlüssel → Zielname.

    Der Zielname muss unter demselben Schlüssel stehen, den `band_key` später
    bildet — sonst gewinnt bei "Linkin Park" wieder die Mehrheitsschreibweise
    statt der hinterlegten.
    """
    roh = {}
    pfad = DATA / "band_aliase.json"
    if pfad.exists():
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    return ({fold(k): v for k, v in roh.items()},
            {_zusammen(fold(v)): v for v in roh.values()})


# ALIAS_KEY wird von zusammenfuehren.alias_kollisionen bereinigt, bevor die
# Bandnamen vereinheitlicht werden.
ALIAS_KEY, ALIAS_NAME = _lade_aliase()


def band_key(name: str) -> str:
    """Schlüssel einer Band; hinterlegte Kürzel lösen sich dabei auf."""
    k = fold(name)
    ziel = ALIAS_KEY.get(k)
    return _zusammen(fold(ziel) if ziel else k)


def festival_key(name: str) -> str:
    """Schlüssel eines Festivals: ohne Artikel, Jahr und die Wörter Festival/Open Air."""
    v = fold(name)
    v = re.sub(r"\b(19|20)\d{2}\b", " ", v)
    v = re.sub(r"\b(festival|fest|open air|openair|open|air)\b", " ", v)
    # Angehängt und zusammengeschrieben meint dasselbe: "Reloadfestival" stand
    # als eigener Eintrag neben "Reload Festival", weil nur das freistehende
    # Wort wegfiel. Der Rumpf muss dabei vier Zeichen behalten, sonst würde
    # aus "Festa" ein leerer Schlüssel.
    v = re.sub(r"(?<=\w{4})(festival|openair|fest)\b", " ", v)
    v = re.sub(r"\b(festival|openair)(?=\w{4})", " ", v)
    return re.sub(r"\s+", " ", v).strip() or fold(name)


def city_key(value: str) -> str:
    """Ortsschlüssel ohne Postleitzahl."""
    return fold(re.sub(r"\b\d{4,6}\b", " ", value or ""))


# --------------------------------------------------------------------------
# Bandnamen
# --------------------------------------------------------------------------

_BAND_FUELLWORT = re.compile(
    r"^(uvm|u\.v\.m\.|und viele mehr|alle artists|t\.b\.a\.?|tba|mehr|close|"
    r"line ?-?up|weitere|special guest[s]?|support|n/a|-{1,3})$", re.I)

# "26. 7.2026" oder "04.07.2026 Auch der zweite Festivaltag"
_BAND_DATUM = re.compile(r"^\d{1,2}\.\s?\d{1,2}\.\d{2,4}\b")

# Reste aus Beschreibungs- und Preisfeldern. Die Beschriftungen brauchen ihren
# Doppelpunkt: "\bKategorie:\b" traf nie, weil dahinter ein Leerzeichen steht
# und zwischen zwei Satzzeichen keine Wortgrenze liegt.
_BAND_FELD = re.compile(r"\b(?:VVK|AK|Camping|Rahmenprogramm|"
                        r"zum kompletten Programm)\b"
                        r"|\b(?:Kategorie|Preis|Besucher|Stil|Location)\s*:", re.I)
_BAND_SATZ = re.compile(r"\b(?:ist|sind|wird|werden|findet|treffen|startet|sorgen|"
                        r"bestätigt|außerdem)\b", re.I)


def valid_band(name: str) -> bool:
    """Ist das ein Bandname — oder ein Bruchstück aus dem Fließtext?"""
    n = clean(name)
    if len(n) < 2 or len(n) > 90:
        return False
    if _BAND_FUELLWORT.match(n) or _BAND_DATUM.match(n) or _BAND_FELD.search(n):
        return False
    if not re.search(r"[A-Za-zÀ-ÿ0-9]", n):
        return False
    # Satzwörter erst ab einer Länge prüfen, die kein Bandname mehr hat -
    # "Werden Wir Uns Wiedersehen" soll nicht durchfallen.
    return not (len(n.split()) >= 6 and _BAND_SATZ.search(n))


def canonical_band(variants: list[str]) -> str:
    """Wählt die häufigste, bei Gleichstand die längste/sauberste Schreibweise."""
    counts: dict[str, int] = {}
    for v in variants:
        counts[v] = counts.get(v, 0) + 1

    def score(item):
        name, cnt = item
        # Großbuchstabe am Anfang zuerst: sonst gewänne bei Akronymen wie
        # B.O.S.C.H. die durchgehend kleingeschriebene Variante.
        return (cnt, name[:1].isupper(),
                name != name.lower() and name != name.upper(),
                -name.count("."), len(name))

    return max(counts.items(), key=score)[0]


def betrag(roh: str) -> float | None:
    """Zahl aus einem Datenblatt-Preis; None, wenn sie keine ist.

    Die Quellen schreiben Tausender mal mit Punkt, mal gar nicht: "1690.00",
    aber auch "8.900.00". Der letzte Punkt trennt die Nachkommastellen, alle
    übrigen sind Tausenderpunkte. Ohne diese Unterscheidung warf float() eine
    Ausnahme - und der Aufrufer verwarf das ganze Festival.
    """
    text = re.sub(r"[^\d.,]", "", roh or "").replace(",", ".")
    if not text:
        return None
    if text.count(".") > 1:
        kopf, _, schwanz = text.rpartition(".")
        text = kopf.replace(".", "") + "." + schwanz
    try:
        return float(text)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Genretexte
# --------------------------------------------------------------------------

def genres_vereinen(*werte: str) -> str:
    """Genres mehrerer Quellen sammeln; doppelte Angaben fallen weg.

    Früher gewann die erste gefüllte Quelle und die übrigen verfielen. Bei
    "Rock im Park" blieb so das festivalsunited-Wort "genreübergreifendes"
    stehen, während festival-alarm acht konkrete Richtungen nennt. Die
    Vereinigung ist näher an der Wahrheit als jede Quelle allein - und der
    Abgleich ohne Groß-/Kleinschreibung räumt die Wiederholungen weg, die
    einzelne Quellseiten in ihrer eigenen Aufzählung haben.
    """
    gesehen: dict[str, str] = {}
    for wert in werte:
        for teil in (wert or "").split(","):
            teil = clean(teil)
            if teil:
                gesehen.setdefault(teil.casefold(), teil)
    return ", ".join(gesehen.values())


# --------------------------------------------------------------------------
# Datum
# --------------------------------------------------------------------------

MONATE = ["januar", "februar", "maerz", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "dezember"]

_MONAT_EN = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}


def datum_de(wert) -> str:
    """ISO-Datum als TT.MM.JJJJ; führende Nullen dürfen fehlen ("2026-8-19")."""
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(wert or ""))
    return f"{int(m.group(3)):02d}.{int(m.group(2)):02d}.{m.group(1)}" if m else ""


def datum_englisch(wert: str) -> str:
    """"August 19, 2026" oder "19 Aug 2026" als TT.MM.JJJJ."""
    text = (wert or "").strip()
    m = re.match(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s*(\d{4})", text)
    if m:
        monat = _MONAT_EN.get(m.group(1).lower()) or _monat_kurz(m.group(1))
        return f"{int(m.group(2)):02d}.{monat:02d}.{m.group(3)}" if monat else ""
    m = re.match(r"(\d{1,2})\.?\s+([A-Za-z]{3,9})\.?\s+(\d{4})", text)
    if m:
        monat = _MONAT_EN.get(m.group(2).lower()) or _monat_kurz(m.group(2))
        return f"{int(m.group(1)):02d}.{monat:02d}.{m.group(3)}" if monat else ""
    return ""


def _monat_kurz(name: str) -> int:
    kurz = name.lower()[:3]
    for voll, nr in _MONAT_EN.items():
        if voll.startswith(kurz):
            return nr
    return 0


def tag_zahl(datum: str) -> int:
    """TT.MM.JJJJ als vergleichbare Zahl; 0, wenn nichts dasteht."""
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", datum or "")
    return int(m.group(3) + m.group(2) + m.group(1)) if m else 0


def tage_abstand(a: str, b: str) -> int | None:
    """Abstand zweier Termine in Tagen; None, wenn einer fehlt oder unlesbar ist."""
    try:
        erst = date(int(a[6:10]), int(a[3:5]), int(a[0:2]))
        zweit = date(int(b[6:10]), int(b[3:5]), int(b[0:2]))
    except (ValueError, IndexError, TypeError):
        return None
    return abs((erst - zweit).days)
