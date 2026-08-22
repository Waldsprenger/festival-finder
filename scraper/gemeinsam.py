"""Pfade, Länderwissen und Dateihilfen — die Grundlage aller Skripte.

Bewusst ohne Fremdpakete: Auch die reinen Bauskripte (build_pwa, build_map)
binden dieses Modul ein, und sie sollen dafür weder requests noch bs4 brauchen.
Was das Netz betrifft, steht in `netz.py`, was Namen betrifft, in `text.py`.
"""

from __future__ import annotations

import json
import os
import re
import sys
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
    """JSON lesen; fehlt die Datei oder ist sie zerrissen, kommt der Standard.

    Eine halb geschriebene Datei brachte bisher jeden Lauf zum Stehen, bis
    jemand sie von Hand löschte. Sie wird stattdessen beiseitegelegt — was
    darin steht, ist vielleicht noch zu retten.
    """
    if not pfad.exists():
        return standard
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        beiseite = pfad.with_name(pfad.name + ".kaputt")
        pfad.replace(beiseite)
        print(f"  ! {pfad.name} war nicht lesbar ({exc.__class__.__name__}); "
              f"liegt jetzt als {beiseite.name} daneben", file=sys.stderr)
        return standard


def schreib_json(pfad: Path, inhalt, *, kompakt: bool = False) -> None:
    """JSON schreiben: erst vollständig daneben, dann an seinen Platz rücken.

    Bricht ein Lauf mitten im Schreiben ab, blieb sonst eine halbe Datei
    zurück. Bei `preis_verlauf.json` hiesse das: die ganze beobachtete
    Preisgeschichte weg — sie steht nirgends sonst.
    """
    text = json.dumps(inhalt, ensure_ascii=False,
                      **({"separators": (",", ":")} if kompakt else {"indent": 2}))
    daneben = pfad.with_name(pfad.name + ".neu")
    daneben.write_text(text + ("" if kompakt else "\n"), encoding="utf-8")
    os.replace(daneben, pfad)


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

# Deutsche Namen für die Welt jenseits Europas. Die Quellen schreiben deutsch;
# die englischen Namen aller 252 Staaten kommen aus data/laender.json dazu.
WELT_DEUTSCH = {
    "usa": "US", "vereinigte staaten": "US", "vereinigte staaten von amerika": "US",
    "kanada": "CA", "mexiko": "MX", "brasilien": "BR", "argentinien": "AR",
    "kolumbien": "CO", "peru": "PE", "chile": "CL", "uruguay": "UY",
    "paraguay": "PY", "ecuador": "EC", "bolivien": "BO", "venezuela": "VE",
    "kuba": "CU", "jamaika": "JM", "dominikanische republik": "DO",
    "australien": "AU", "neuseeland": "NZ", "japan": "JP", "china": "CN",
    "indien": "IN", "indonesien": "ID", "thailand": "TH", "vietnam": "VN",
    "philippinen": "PH", "singapur": "SG", "malaysia": "MY", "suedkorea": "KR",
    "südkorea": "KR", "nordkorea": "KP", "taiwan": "TW", "kasachstan": "KZ",
    "usbekistan": "UZ", "georgien": "GE", "armenien": "AM", "aserbaidschan": "AZ",
    "suedafrika": "ZA", "südafrika": "ZA", "aegypten": "EG", "ägypten": "EG",
    "marokko": "MA", "tunesien": "TN", "algerien": "DZ", "libyen": "LY",
    "kenia": "KE", "tansania": "TZ", "uganda": "UG", "ghana": "GH",
    "nigeria": "NG", "senegal": "SN", "aethiopien": "ET", "äthiopien": "ET",
    "israel": "IL", "katar": "QA", "vereinigte arabische emirate": "AE",
    "saudi-arabien": "SA", "libanon": "LB", "jordanien": "JO", "iran": "IR",
    "irak": "IQ", "pakistan": "PK", "bangladesch": "BD", "nepal": "NP",
    "sri lanka": "LK", "mongolei": "MN", "kambodscha": "KH", "laos": "LA",
    "myanmar": "MM", "costa rica": "CR", "panama": "PA", "guatemala": "GT",
    "honduras": "HN", "nicaragua": "NI", "el salvador": "SV", "belize": "BZ",
    "fidschi": "FJ", "papua-neuguinea": "PG",
}


def _welttabelle() -> tuple[dict[str, dict], dict[str, str]]:
    """data/laender.json: alle Staaten mit Kontinent, dazu ihre Namen.

    Die Datei entsteht in build_gazetteer.py aus der Länderliste von GeoNames.
    Fehlt sie (frischer Klon vor dem ersten Lauf), bleibt es bei den
    handgeschriebenen Namen — der Lauf soll daran nicht scheitern.
    """
    roh = {}
    pfad = DATA / "laender.json"
    if pfad.exists():
        try:
            roh = json.loads(pfad.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            roh = {}
    namen = {}
    for code, eintrag in roh.items():
        namen[code.lower()] = code
        name = (eintrag.get("name") or "").lower()
        if name:
            namen[name] = code
    return roh, namen


WELT, _WELT_NAMEN = _welttabelle()

#: Alle gültigen Länderkürzel. Ohne die Datei zählt, was hier steht.
ISO_CODES = set(WELT) | set(LAENDER.values()) | set(WELT_DEUTSCH.values())

#: Kürzel → Kontinent (EU, NA, SA, AS, AF, OC, AN)
KONTINENT = {code: e.get("kontinent", "") for code, e in WELT.items()}

# Reihenfolge: handgeschriebene Namen zuerst, dann die Welt. So bleibt
# "england" bei GB, obwohl GeoNames "United Kingdom" führt.
LAENDER = {**_WELT_NAMEN, **WELT_DEUTSCH, **LAENDER}


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


def ist_land(country: str) -> bool:
    """Ist das ein Staat, den es gibt?

    Früher hiess die Frage "liegt das in Europa?" und entschied darüber, was in
    den Bestand kam. Jetzt zählt nur noch, ob hinter der Angabe ein Land steht:
    "Bayern" und "Region Hannover" sind keine, "Japan" und "BR" schon.
    """
    return land_code(country) in ISO_CODES


def kontinent(country: str) -> str:
    """Erdteil eines Landes, leer wenn unbekannt."""
    return KONTINENT.get(land_code(country), "")


def _laender_rahmen() -> dict[str, tuple[float, float, float, float]]:
    """Der Kasten je Land: lat0, lat1, lon0, lon1, aus dem Ortsverzeichnis."""
    roh = lies_json(DATA / "laender_rahmen.json", {}) or {}
    return {cc: tuple(werte) for cc, werte in roh.items() if len(werte) == 4}


LAENDER_RAHMEN = _laender_rahmen()

#: Zuschlag auf jeden Kasten. Ein Festival kann dicht hinter der Grenze
#: liegen, und das Ortsverzeichnis kennt nicht jede Insel.
RAHMEN_ZUSCHLAG = 2.0


def koordinate_passt_zum_land(lat: float | None, lon: float | None,
                              country: str) -> bool:
    """Liegt der Punkt in dem Land, das die Quelle nennt?

    Ohne Land oder ohne Kasten gilt der Punkt als in Ordnung - geraten wird
    nicht. Bekannt ist der Kasten für die Länder aus dem Ortsverzeichnis;
    er stammt aus 116.653 Orten und ist bewusst weit.
    """
    if lat is None or lon is None:
        return False
    kasten = LAENDER_RAHMEN.get(land_code(country))
    if not kasten:
        return True
    lat0, lat1, lon0, lon1 = kasten
    return (lat0 - RAHMEN_ZUSCHLAG <= lat <= lat1 + RAHMEN_ZUSCHLAG
            and lon0 - RAHMEN_ZUSCHLAG <= lon <= lon1 + RAHMEN_ZUSCHLAG)

