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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemeinsam import DATA, EU_CODES, LAENDER  # noqa: E402

GEO = DATA / "geo.json"

# Nominatim verlangt eine Kontaktangabe im User-Agent (Nutzungsrichtlinie)
UA = "FestivalFinder/1.0 (privates Projekt; Kontakt: waldsprenger@gmail.com)"
ENDPOINT = "https://nominatim.openstreetmap.org/search"


# Ohne Laenderfilter liefert Nominatim bei mehrdeutigen Namen den weltweit
# bekanntesten Ort: "Newark" wurde New Jersey statt England, "Hille" wurde
# Hilla im Irak. Jede Suche bleibt deshalb auf Europa beschraenkt; die
# Laenderzuordnung und EU_CODES stehen in gemeinsam.py.
def cc(country: str) -> str:
    return LAENDER.get((country or "").strip().lower(), "").lower()


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
    festivals = json.loads((DATA / "festivals.json").read_text(encoding="utf-8"))
    geo = json.loads(GEO.read_text(encoding="utf-8")) if GEO.exists() else {}

    offen: dict[str, tuple[str, str, str]] = {}
    for f in festivals:
        city = (f.get("city") or "").strip()
        if not city:
            continue
        k = key(city, f.get("country", ""))
        if k not in geo:
            offen.setdefault(k, (k, city, f.get("country", "")))
    todo = list(offen.values())

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
