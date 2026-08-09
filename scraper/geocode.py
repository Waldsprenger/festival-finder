"""Geokodiert die Festivalorte ueber Nominatim (OpenStreetMap).

Ergebnis: data/geo.json  {"stadt|land": {"lat":.., "lon":.., "display":..}}
Die Datei dient als Cache - bereits aufgeloeste Orte werden nicht erneut angefragt.
Nominatim erlaubt max. 1 Anfrage/Sekunde und verlangt eine Kontaktangabe im
User-Agent (Nutzungsrichtlinie), daher der bewusst langsame Lauf.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
GEO = DATA / "geo.json"

UA = "FestivalFinder/1.0 (privates Projekt; Kontakt: waldsprenger@gmail.com)"
ENDPOINT = "https://nominatim.openstreetmap.org/search"

# Laenderangaben der Quellen sind gemischt (deutsch, ISO2, umgangssprachlich)
COUNTRY = {
    "deutschland": "de", "de": "de", "germany": "de",
    "oesterreich": "at", "österreich": "at", "at": "at", "austria": "at",
    "schweiz": "ch", "ch": "ch", "switzerland": "ch",
    "holland": "nl", "niederlande": "nl", "nl": "nl", "netherlands": "nl",
    "frankreich": "fr", "fr": "fr", "france": "fr",
    "belgien": "be", "be": "be", "belgium": "be",
    "england": "gb", "gb": "gb", "uk": "gb", "grossbritannien": "gb",
    "schottland": "gb", "wales": "gb", "nordirland": "gb",
    "italien": "it", "it": "it", "italy": "it",
    "spanien": "es", "es": "es", "spain": "es",
    "portugal": "pt", "pt": "pt",
    "daenemark": "dk", "dänemark": "dk", "dk": "dk", "denmark": "dk",
    "schweden": "se", "se": "se", "sweden": "se",
    "norwegen": "no", "no": "no", "norway": "no",
    "finnland": "fi", "fi": "fi", "finland": "fi",
    "polen": "pl", "pl": "pl", "poland": "pl",
    "tschechien": "cz", "cz": "cz", "czechia": "cz",
    "ungarn": "hu", "hu": "hu", "hungary": "hu",
    "irland": "ie", "ie": "ie", "ireland": "ie",
    "luxemburg": "lu", "lu": "lu",
    "slowenien": "si", "si": "si", "slowakei": "sk", "sk": "sk",
    "kroatien": "hr", "hr": "hr", "serbien": "rs", "rs": "rs",
    "griechenland": "gr", "gr": "gr", "greece": "gr",
    "rumaenien": "ro", "rumänien": "ro", "ro": "ro",
    "bulgarien": "bg", "bg": "bg", "estland": "ee", "ee": "ee",
    "lettland": "lv", "lv": "lv", "litauen": "lt", "lt": "lt",
    "island": "is", "is": "is", "malta": "mt", "mt": "mt",
    "liechtenstein": "li", "li": "li", "bosnien": "ba", "ba": "ba",
}


def cc(country: str) -> str:
    return COUNTRY.get((country or "").strip().lower(), "")


def key(city: str, country: str) -> str:
    return f"{city.strip()}|{country.strip()}"


def lookup(session: requests.Session, city: str, country: str) -> dict | None:
    code = cc(country)
    attempts = []
    if code:
        attempts.append({"city": city, "countrycodes": code})
        attempts.append({"q": f"{city}, {code.upper()}"})
    attempts.append({"q": city})

    for params in attempts:
        params |= {"format": "jsonv2", "limit": 1, "accept-language": "de"}
        try:
            r = session.get(ENDPOINT, params=params, timeout=30)
            time.sleep(1.1)
            if r.status_code != 200:
                continue
            hits = r.json()
            if hits:
                h = hits[0]
                return {"lat": float(h["lat"]), "lon": float(h["lon"]),
                        "display": h.get("display_name", "")}
        except Exception:
            time.sleep(2.0)
    return None


def main() -> None:
    festivals = json.loads((DATA / "festivals.json").read_text(encoding="utf-8"))
    geo = json.loads(GEO.read_text(encoding="utf-8")) if GEO.exists() else {}

    todo = []
    for f in festivals:
        city = (f.get("city") or "").strip()
        if not city:
            continue
        k = key(city, f.get("country", ""))
        if k not in geo and k not in [t[0] for t in todo[-1:]]:
            todo.append((k, city, f.get("country", "")))
    todo = list({k: (k, c, l) for k, c, l in todo}.values())

    print(f"{len(geo)} im Cache, {len(todo)} offen "
          f"(~{len(todo) * 1.2 / 60:.0f} min)", flush=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "de"})

    hit = miss = 0
    for i, (k, city, country) in enumerate(todo, 1):
        res = lookup(session, city, country)
        geo[k] = res or {}
        hit, miss = (hit + 1, miss) if res else (hit, miss + 1)
        if i % 50 == 0 or i == len(todo):
            GEO.write_text(json.dumps(geo, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {i}/{len(todo)}  gefunden {hit}, ohne Treffer {miss}", flush=True)

    GEO.write_text(json.dumps(geo, ensure_ascii=False, indent=1), encoding="utf-8")
    found = sum(1 for v in geo.values() if v)
    print(f"fertig: {found}/{len(geo)} Orte mit Koordinaten -> {GEO}")


if __name__ == "__main__":
    main()
