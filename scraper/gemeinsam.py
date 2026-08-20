"""Pfade, Länderwissen und Dateihilfen — die Grundlage aller Skripte.

Bewusst ohne Fremdpakete: Auch die reinen Bauskripte (build_pwa, build_map)
binden dieses Modul ein, und sie sollen dafür weder requests noch bs4 brauchen.
Was das Netz betrifft, steht in `netz.py`, was Namen betrifft, in `text.py`.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "cache"
DATA = BASE / "data"
SITE = BASE / "site"
for _ordner in (CACHE, DATA, SITE):
    _ordner.mkdir(exist_ok=True)

# Jahrgänge, die abgeklopft werden. Die Obergrenze wächst mit der Zeit mit,
# damit künftige Jahre (2029, 2030 …) ohne Codeänderung erfasst werden.
JAHR_HEUTE = date.today().year
JAHRE = range(2006, JAHR_HEUTE + 6)


# --------------------------------------------------------------------------
# Dateien
# --------------------------------------------------------------------------

def lies_json(pfad: Path, standard=None):
    """JSON lesen; fehlt die Datei, kommt der Standardwert zurück."""
    if not pfad.exists():
        return standard
    return json.loads(pfad.read_text(encoding="utf-8"))


def schreib_json(pfad: Path, inhalt, *, kompakt: bool = False) -> None:
    text = json.dumps(inhalt, ensure_ascii=False,
                      **({"separators": (",", ":")} if kompakt else {"indent": 2}))
    pfad.write_text(text + ("" if kompakt else "\n"), encoding="utf-8")


# --------------------------------------------------------------------------
# Länder
# --------------------------------------------------------------------------

# Die Quellen schreiben Länder mal aus, mal als Kürzel, mal umgangssprachlich.
# Ausgeliefert wird einheitlich der ISO-Code.
LAENDER = {
    "deutschland": "DE", "germany": "DE", "de": "DE", "brd": "DE",
    "oesterreich": "AT", "österreich": "AT", "austria": "AT", "at": "AT",
    "schweiz": "CH", "switzerland": "CH", "suisse": "CH", "ch": "CH",
    "niederlande": "NL", "holland": "NL", "netherlands": "NL", "nl": "NL",
    "belgien": "BE", "belgium": "BE", "be": "BE",
    "frankreich": "FR", "france": "FR", "fr": "FR",
    "italien": "IT", "italy": "IT", "it": "IT",
    "spanien": "ES", "spain": "ES", "es": "ES",
    "portugal": "PT", "pt": "PT",
    "england": "GB", "grossbritannien": "GB", "großbritannien": "GB",
    "schottland": "GB", "wales": "GB", "nordirland": "GB", "uk": "GB",
    "united kingdom": "GB", "great britain": "GB", "gb": "GB",
    "vereinigtes königreich": "GB", "vereinigtes koenigreich": "GB",
    "irland": "IE", "ireland": "IE", "ie": "IE",
    "daenemark": "DK", "dänemark": "DK", "denmark": "DK", "dk": "DK",
    "schweden": "SE", "sweden": "SE", "se": "SE",
    "norwegen": "NO", "norway": "NO", "no": "NO",
    "finnland": "FI", "finland": "FI", "fi": "FI",
    "island": "IS", "iceland": "IS", "is": "IS",
    "polen": "PL", "poland": "PL", "pl": "PL",
    "tschechien": "CZ", "tschechische republik": "CZ", "czechia": "CZ", "cz": "CZ",
    "slowakei": "SK", "sk": "SK", "slowenien": "SI", "si": "SI",
    "ungarn": "HU", "hungary": "HU", "hu": "HU",
    "kroatien": "HR", "croatia": "HR", "hr": "HR",
    "serbien": "RS", "rs": "RS", "montenegro": "ME", "me": "ME",
    "bosnien": "BA", "bosnien und herzegowina": "BA", "ba": "BA",
    "nordmazedonien": "MK", "mazedonien": "MK", "mk": "MK",
    "albanien": "AL", "al": "AL", "kosovo": "XK", "xk": "XK",
    "griechenland": "GR", "greece": "GR", "gr": "GR",
    "bulgarien": "BG", "bg": "BG", "rumaenien": "RO", "rumänien": "RO", "ro": "RO",
    "moldawien": "MD", "md": "MD", "ukraine": "UA", "ua": "UA",
    "estland": "EE", "ee": "EE", "lettland": "LV", "lv": "LV",
    "litauen": "LT", "lt": "LT", "weissrussland": "BY", "belarus": "BY", "by": "BY",
    "luxemburg": "LU", "luxembourg": "LU", "lu": "LU",
    "liechtenstein": "LI", "li": "LI", "monaco": "MC", "mc": "MC",
    "andorra": "AD", "ad": "AD", "san marino": "SM", "sm": "SM",
    "malta": "MT", "mt": "MT", "zypern": "CY", "cyprus": "CY", "cy": "CY",
    "tuerkei": "TR", "türkei": "TR", "turkey": "TR", "tr": "TR",
    "vatikan": "VA", "va": "VA", "gibraltar": "GI", "gi": "GI",
    "faeroeer": "FO", "färöer": "FO", "fo": "FO",
    # Schreibweisen aus den Länderlinks von festivalsunited
    "czech republic": "CZ", "romania": "RO", "slovakia": "SK", "serbia": "RS",
    "bulgaria": "BG", "slovenia": "SI", "albania": "AL", "estonia": "EE",
    "latvia": "LV", "lithuania": "LT", "faroe islands": "FO",
    "north macedonia": "MK", "bosnia and herzegovina": "BA",
}

# Rahmen um Europa: lat0, lat1, lon0, lon1. Reicht von den Azoren bis zur
# Osttuerkei und von Zypern bis Nordnorwegen; die Karte zeichnet denselben
# Ausschnitt fein.
EUROPA_RAHMEN = (27.0, 72.0, -32.0, 46.0)


def liegt_in_europa(lat: float | None, lon: float | None) -> bool:
    """Steckt der Punkt im europaeischen Rahmen?"""
    if lat is None or lon is None:
        return False
    lat0, lat1, lon0, lon1 = EUROPA_RAHMEN
    return lat0 <= lat <= lat1 and lon0 <= lon <= lon1


# Alle in LAENDER vorkommenden Codes plus Inselgebiete ohne eigene Schreibweise
EUROPA_CODES = sorted(set(LAENDER.values()) | {"GG", "JE", "IM"})

# Kleingeschrieben für Nominatim
EU_CODES = ",".join(c.lower() for c in EUROPA_CODES)

# Ausgeschriebene Namen außereuropäischer Länder. Kürzel stehen hier nicht:
# Die kennt `ausser_europa` schon daran, dass sie nicht zu Europa gehören.
NICHT_EUROPA = {
    "usa", "vereinigte staaten", "united states", "kanada", "canada", "mexiko",
    "mexico", "brasilien", "brazil", "argentinien", "argentina", "chile",
    "kolumbien", "colombia", "peru", "uruguay", "paraguay", "ecuador",
    "costa rica", "australien", "australia", "neuseeland", "new zealand",
    "japan", "china", "indien", "india", "indonesien", "indonesia", "thailand",
    "vietnam", "philippinen", "singapur", "suedafrika", "südafrika",
    "south africa", "south korea", "kazakhstan", "aegypten", "ägypten",
    "marokko", "tunesien", "israel", "katar", "vereinigte arabische emirate",
}


def land_code(country: str) -> str:
    """Länderkürzel; unbekannte Angaben bleiben unverändert."""
    roh = re.sub(r"\s+", " ", (country or "")).strip()
    if not roh:
        return ""
    code = LAENDER.get(roh.lower())
    if code:
        return code
    if len(roh) == 2 and roh.isalpha():
        return roh.upper()
    return roh


def ausser_europa(country: str) -> bool:
    """Liegt das Land außerhalb Europas?

    Die Namensliste allein genügte nicht: Sie kannte "usa", aber nicht die
    Kürzel IN, CL, PY, CO, ZA, ID, KR, KZ, CR, CN oder TH, die in den Quellen
    ebenso vorkommen. Deshalb zählt zusätzlich jedes gültige Zweibuchstaben-
    kürzel, das nicht zu Europa gehört. Längere unbekannte Angaben ("Bayern",
    "Region Hannover") bleiben ausdrücklich drin — sie sind keine Länder, und
    ein Rauswurf auf Verdacht kostet echte Festivals.
    """
    roh = (country or "").strip().lower()
    if not roh:
        return False
    if roh in NICHT_EUROPA:
        return True
    code = land_code(country)
    return len(code) == 2 and code.isalpha() and code.upper() not in EUROPA_CODES

