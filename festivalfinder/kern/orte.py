"""Länder: Schreibweisen vereinheitlichen, Koordinaten plausibilisieren.

Die Quellen schreiben Länder aus, kürzen sie ab oder nennen sie
umgangssprachlich — „Deutschland", „DE", „BRD", „Germany". Ausgeliefert wird
einheitlich der ISO-Code.

Dazu die Prüfung, die zwei Arten von Unsinn abfängt: einen Punkt, den es auf
der Erde nicht gibt, und einen, der nicht zu dem Land passt, das die Quelle
nennt. Ohne sie stand Lollapalooza Berlin in Chicago und das LongLake Festival
Lugano in Buenos Aires.
"""

import re
from functools import lru_cache

from ..pfade import DATA, lies_json

# Umgangssprachliche und deutsche Namen. Die englischen Namen aller Staaten
# kommen aus data/laender.json dazu; hier steht, was eine Länderliste nicht
# hergibt: „BRD", „England", „Holland", deutsche Schreibweisen.
NAMEN_HAND = {
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
    # Die Welt jenseits Europas, soweit die Quellen sie deutsch schreiben
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
    # Deutsche Namen, die von der englischen Länderliste zu weit abweichen —
    # Nominatim antwortet auf Deutsch, und ohne sie ließe sich ein Treffer
    # nicht gegen das gesuchte Land prüfen.
    "russland": "RU", "moldau": "MD", "republik moldau": "MD",
    "surinam": "SR", "madagaskar": "MG", "gazastreifen": "PS",
    "palaestina": "PS", "palästina": "PS", "westjordanland": "PS",
    "saint vincent und die grenadinen": "VC", "hongkong": "HK",
}

#: Gebiete mit eigenem Kürzel, deren Postanschrift auf den Mutterstaat lautet:
#: Nominatim schreibt bei Chek Lap Kok „Hongkong, China", bei Saint-Martin
#: „Frankreich". Das ist kein Widerspruch.
GEHOERT_ZU = {
    "HK": "CN", "MO": "CN",
    "MF": "FR", "GP": "FR", "MQ": "FR", "RE": "FR", "YT": "FR", "GF": "FR",
    "PM": "FR", "BL": "FR", "NC": "FR", "PF": "FR", "WF": "FR", "TF": "FR",
    "AW": "NL", "CW": "NL", "SX": "NL", "BQ": "NL",
    "FO": "DK", "GL": "DK", "AX": "FI", "SJ": "NO", "BV": "NO",
    "GI": "GB", "IM": "GB", "JE": "GB", "GG": "GB", "FK": "GB", "BM": "GB",
    "KY": "GB", "VG": "GB", "AI": "GB", "MS": "GB", "TC": "GB", "SH": "GB",
    "PR": "US", "VI": "US", "GU": "US", "AS": "US", "MP": "US",
}

#: data/laender.json (aus GeoNames, siehe werkzeug/gazetteer.py). Fehlt sie —
#: frischer Klon vor dem ersten Lauf —, bleibt es bei den Namen von Hand.
_WELT = lies_json(DATA / "laender.json", {}) or {}

#: Alle gültigen Länderkürzel
ISO_CODES = set(_WELT) | set(NAMEN_HAND.values())

# Die handgeschriebenen Namen zuletzt und damit obenauf: „england" bleibt GB,
# obwohl GeoNames „United Kingdom" führt.
NAMEN = {**{c.lower(): c for c in _WELT},
         **{(e.get("name") or "").lower(): c for c, e in _WELT.items() if e.get("name")},
         **NAMEN_HAND}

_LEERRAUM = re.compile(r"\s+")


@lru_cache(maxsize=4096)
def land_code(country: str) -> str:
    """Länderkürzel; unbekannte Angaben bleiben unverändert."""
    roh = _LEERRAUM.sub(" ", country or "").strip()
    if not roh:
        return ""
    if (code := NAMEN.get(roh.lower())):
        return code
    return roh.upper() if len(roh) == 2 and roh.isalpha() else roh


def ist_land(country: str) -> bool:
    """Ist das ein Staat, den es gibt? „Bayern" nicht, „Japan" und „BR" schon."""
    return land_code(country) in ISO_CODES


# --------------------------------------------------------------------------
# Koordinaten
# --------------------------------------------------------------------------

#: Der Ausschnitt, für den feine Kartenumrisse vorliegen: lat0, lat1, lon0,
#: lon1 — von den Azoren bis zur Osttürkei, von Zypern bis Nordnorwegen.
#: `werkzeug/weltkarte.py` erzeugt `data/welt_fein.json` für genau diesen
#: Kasten; die Karte schaltet darin auf die feine Zeichnung um.
FEINRAHMEN = (27.0, 72.0, -32.0, 46.0)

#: Der Kasten je Land (lat0, lat1, lon0, lon1), aus dem Ortsverzeichnis
RAHMEN = {cc: tuple(werte) for cc, werte
          in (lies_json(DATA / "laender_rahmen.json", {}) or {}).items()
          if len(werte) == 4}

#: Zuschlag auf jeden Kasten: Ein Festival kann dicht hinter der Grenze liegen,
#: und das Ortsverzeichnis kennt nicht jede Insel.
ZUSCHLAG = 2.0


def punkt_plausibel(lat: float | None, lon: float | None) -> bool:
    """Ein Punkt auf der Erde — und nicht der Nullpunkt, der in Datenblättern
    für „kein Wert eingetragen" steht."""
    if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:
        return False
    return not (abs(lat) < 0.01 and abs(lon) < 0.01)


def punkt_passt_zum_land(lat: float | None, lon: float | None, country: str) -> bool:
    """Liegt der Punkt in dem Land, das die Quelle nennt?

    Ohne Land oder ohne Kasten gilt der Punkt als in Ordnung — geraten wird
    nicht.
    """
    if lat is None or lon is None:
        return False
    kasten = RAHMEN.get(land_code(country))
    if not kasten:
        return True
    lat0, lat1, lon0, lon1 = kasten
    return (lat0 - ZUSCHLAG <= lat <= lat1 + ZUSCHLAG
            and lon0 - ZUSCHLAG <= lon <= lon1 + ZUSCHLAG)


def zahl_oder_nichts(wert) -> float | None:
    """Koordinaten stehen mal als Zahl, mal als Zeichenkette im Datenblatt."""
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None
