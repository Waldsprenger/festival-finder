"""Gemeinsame Grundlagen aller Bauskripte.

Pfade, Browserkennung und das Länderwissen lagen vorher in drei Modulen
nebeneinander und drohten auseinanderzulaufen. Hier stehen sie einmal.
"""

from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "cache"
DATA = BASE / "data"
SITE = BASE / "site"
for _ordner in (CACHE, DATA, SITE):
    _ordner.mkdir(exist_ok=True)

# Ohne Browserkennung antworten mehrere Quellen mit 403.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}


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
}

# Alle in LAENDER vorkommenden Codes plus Inselgebiete ohne eigene Schreibweise
EUROPA_CODES = sorted(set(LAENDER.values()) | {"GG", "JE", "IM"})

# Kleingeschrieben fuer Nominatim
EU_CODES = ",".join(c.lower() for c in EUROPA_CODES)

# festival-alarm fuehrt auch Ueberseefestivals. Gesammelt wird Europa, und die
# Geokodierung ist ohnehin auf europaeische Laender begrenzt.
NICHT_EUROPA = {
    "usa", "vereinigte staaten", "united states", "kanada", "canada", "mexiko",
    "brasilien", "argentinien", "chile", "kolumbien", "peru", "uruguay",
    "australien", "neuseeland", "japan", "china", "indien", "indonesien",
    "thailand", "vietnam", "philippinen", "singapur", "suedafrika", "südafrika",
    "aegypten", "ägypten", "marokko", "tunesien", "israel", "katar",
    "vereinigte arabische emirate", "us", "ca", "au", "nz", "jp", "br", "mx",
}


def land_code(country: str) -> str:
    """Laenderkuerzel; unbekannte Angaben bleiben unveraendert."""
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
    return (country or "").strip().lower() in NICHT_EUROPA
