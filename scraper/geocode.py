"""Geokodiert Festivalorte über Nominatim (OpenStreetMap) — nur die Reste.

Gefragt wird ausschließlich, was das mitgebaute Ortsverzeichnis nicht hergibt:
Orte, für die weder eine Postleitzahl noch ein Eintrag ab 1.000 Einwohnern
vorliegt. Nominatim erlaubt eine Anfrage je Sekunde und verlangt eine
Kontaktangabe im User-Agent; jede vermiedene Anfrage ist deshalb eine Sekunde
Laufzeit und ein Stück Last weniger auf einem Gratisdienst.

Ergebnis: data/geo.json  {"stadt|land": {"lat":.., "lon":.., "display":..}}
Die Datei ist zugleich Cache — einmal aufgelöste Orte werden nie erneut gefragt.
"""

from __future__ import annotations

import time

import requests

from gemeinsam import DATA, EU_CODES, land_code, lies_json, schreib_json
from text import fold

GEO = DATA / "geo.json"

# Nominatim verlangt eine Kontaktangabe im User-Agent (Nutzungsrichtlinie)
UA = "FestivalFinder/1.0 (privates Projekt; Kontakt: waldsprenger@gmail.com)"
ENDPOINT = "https://nominatim.openstreetmap.org/search"


# Ohne Laenderfilter liefert Nominatim bei mehrdeutigen Namen den weltweit
# bekanntesten Ort: "Newark" wurde New Jersey statt England, "Hille" wurde
# Hilla im Irak. Jede Suche bleibt deshalb auf Europa beschraenkt; die
# Laenderzuordnung und EU_CODES stehen in gemeinsam.py.
def cc(country: str) -> str:
    """Laendercode klein geschrieben, wie Nominatim ihn erwartet."""
    code = land_code(country)
    return code.lower() if len(code) == 2 else ""


def key(city: str, country: str) -> str:
    return f"{city.strip()}|{country.strip()}"


def lookup(session: requests.Session, city: str, country: str) -> dict | None:
    code = cc(country)
    attempts = []
    if code:
        attempts.append({"city": city, "countrycodes": code})
        # ebenfalls auf Europa begrenzt: bei falscher Landesangabe in der Quelle
        # (Belfast steht dort unter Irland) darf nicht weltweit gesucht werden
        attempts.append({"q": f"{city}, {code.upper()}", "countrycodes": EU_CODES})
    attempts.append({"city": city, "countrycodes": EU_CODES})
    attempts.append({"q": city, "countrycodes": EU_CODES})

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
    festivals = lies_json(DATA / "festivals.json", [])
    geo = lies_json(GEO, {})

    # Was das Ortsverzeichnis selbst beantwortet, muss niemand erfragen.
    verortung = lies_json(DATA / "verortung.json", {})
    bekannte_plz = {(c, cc) for c, _lat, _lon, cc in verortung.get("plz", [])}
    bekannte_orte = {(fold(n), cc) for n, _lat, _lon, cc in verortung.get("orte", [])}

    offen: dict[str, tuple[str, str, str]] = {}
    lokal = 0
    for f in festivals:
        city = (f.get("city") or "").strip()
        if not city:
            continue
        k = key(city, f.get("country", ""))
        if k in geo:
            continue
        land = land_code(f.get("country", ""))
        code = (f.get("plz") or "").strip().replace(" ", "")
        if (code and (code, land) in bekannte_plz) or (fold(city), land) in bekannte_orte:
            lokal += 1
            continue
        offen.setdefault(k, (k, city, f.get("country", "")))
    todo = list(offen.values())

    print(f"{len(geo)} im Cache, {lokal} aus dem Ortsverzeichnis, {len(todo)} offen "
          f"(~{len(todo) * 1.2 / 60:.0f} min)", flush=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "de"})

    hit = miss = 0
    for i, (k, city, country) in enumerate(todo, 1):
        res = lookup(session, city, country)
        geo[k] = res or {}
        hit, miss = (hit + 1, miss) if res else (hit, miss + 1)
        if i % 50 == 0 or i == len(todo):
            schreib_json(GEO, geo)
            print(f"  {i}/{len(todo)}  gefunden {hit}, ohne Treffer {miss}", flush=True)

    schreib_json(GEO, geo)
    found = sum(1 for v in geo.values() if v)
    print(f"fertig: {found}/{len(geo)} Orte mit Koordinaten -> {GEO}")


if __name__ == "__main__":
    main()
