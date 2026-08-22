"""Festivalorte über Nominatim (OpenStreetMap) — nur die Reste.

Gefragt wird ausschließlich, was das mitgebaute Ortsverzeichnis nicht hergibt:
Orte, für die weder eine Postleitzahl noch ein Eintrag ab 1.000 Einwohnern
vorliegt. Nominatim erlaubt eine Anfrage je Sekunde und verlangt eine
Kontaktangabe im User-Agent; jede vermiedene Anfrage ist deshalb eine Sekunde
Laufzeit und ein Stück Last weniger auf einem Gratisdienst.

Ergebnis: `data/geo.json` — {"stadt|land": {"lat":.., "lon":.., "display":..}}.
Die Datei ist zugleich Cache: Einmal aufgelöste Orte werden nie erneut gefragt.
"""

import sys
import time

import requests

from ..kern.festival import Festival
from ..kern.orte import land_code
from ..kern.text import fold
from ..pfade import DATA, lies_json, schreib_json

GEO = DATA / "geo.json"

#: Nominatim verlangt eine Kontaktangabe im User-Agent (Nutzungsrichtlinie)
UA = "FestivalFinder/1.0 (privates Projekt; Kontakt: waldsprenger@gmail.com)"
ENDPUNKT = "https://nominatim.openstreetmap.org/search"


def cc(country: str) -> str:
    """Ländercode klein geschrieben, wie Nominatim ihn erwartet.

    Bei mehrdeutigen Namen liefert Nominatim den weltweit bekanntesten Ort:
    „Newark" wurde New Jersey statt England, „Hille" wurde Hilla im Irak.
    Dagegen hilft das Land aus der Quelle — es steht bei fast jedem Festival
    und ist die genauere Angabe.
    """
    code = land_code(country)
    return code.lower() if len(code) == 2 else ""


def schluessel(stadt: str, land: str) -> str:
    return f"{stadt.strip()}|{land.strip()}"


def nachschlagen(sitzung: requests.Session, stadt: str,
                 land: str) -> tuple[dict | None, bool]:
    """Koordinaten — und ob der Dienst überhaupt geantwortet hat.

    Beides auseinanderzuhalten ist wichtig: „kennt den Ort nicht" darf in den
    Cache, „war gerade nicht erreichbar" nicht. Sonst schreibt ein einziger
    Ausfall hunderte Orte auf Dauer als unauffindbar fest.
    """
    code = cc(land)
    versuche = []
    if code:
        versuche.append({"city": stadt, "countrycodes": code})
        versuche.append({"q": f"{stadt}, {code.upper()}"})
    versuche.append({"city": stadt})
    versuche.append({"q": stadt})

    geantwortet = False
    for params in versuche:
        params |= {"format": "jsonv2", "limit": 1, "accept-language": "de"}
        try:
            r = sitzung.get(ENDPUNKT, params=params, timeout=30)
            time.sleep(1.1)
            if r.status_code != 200:
                continue
            geantwortet = True
            if (hits := r.json()):
                h = hits[0]
                return {"lat": float(h["lat"]), "lon": float(h["lon"]),
                        "display": h.get("display_name", "")}, True
        except Exception:
            time.sleep(2.0)
    return None, geantwortet


def offene_orte(festivals: list[Festival], geo: dict) -> tuple[list, int]:
    """Was weder im Cache noch im Ortsverzeichnis steht."""
    verortung = lies_json(DATA / "verortung.json", {}) or {}
    bekannte_plz = {(c, cc_) for c, _la, _lo, cc_ in verortung.get("plz", [])}
    bekannte_orte = {(fold(n), cc_) for n, _la, _lo, cc_ in verortung.get("orte", [])}

    offen: dict[str, tuple[str, str, str]] = {}
    lokal = 0
    for f in festivals:
        stadt = (f.stadt or "").strip()
        if not stadt:
            continue
        k = schluessel(stadt, f.land)
        if k in geo:
            continue
        land = land_code(f.land)
        code = (f.plz or "").strip().replace(" ", "")
        if (code and (code, land) in bekannte_plz) or (fold(stadt), land) in bekannte_orte:
            lokal += 1
            continue
        offen.setdefault(k, (k, stadt, f.land))
    return list(offen.values()), lokal


def auffuellen(festivals: list[Festival]) -> dict:
    """Die offenen Orte erfragen und in `data/geo.json` nachtragen."""
    geo = lies_json(GEO, {}) or {}
    todo, lokal = offene_orte(festivals, geo)
    print(f"{len(geo)} im Cache, {lokal} aus dem Ortsverzeichnis, {len(todo)} offen "
          f"(~{len(todo) * 1.2 / 60:.0f} min)", flush=True)

    sitzung = requests.Session()
    sitzung.headers.update({"User-Agent": UA, "Accept-Language": "de"})

    treffer = leer = stumm = 0
    for i, (k, stadt, land) in enumerate(todo, 1):
        res, geantwortet = nachschlagen(sitzung, stadt, land)
        if res:
            geo[k], treffer = res, treffer + 1
        elif geantwortet:
            geo[k], leer = {}, leer + 1      # kennt den Ort wirklich nicht
        else:
            stumm += 1                       # nicht merken, morgen wieder fragen
        if i % 50 == 0 or i == len(todo):
            schreib_json(GEO, geo)
            print(f"  {i}/{len(todo)}  gefunden {treffer}, ohne Treffer {leer}"
                  + (f", ohne Antwort {stumm}" if stumm else ""), flush=True)

    schreib_json(GEO, geo)
    if stumm:
        print(f"  ! {stumm} Orte blieben ohne Antwort - beim nächsten Lauf erneut",
              file=sys.stderr)
    return {"im_cache": len(geo), "aus_verzeichnis": lokal, "gefragt": len(todo),
            "gefunden": treffer, "ohne_treffer": leer, "ohne_antwort": stumm,
            "mit_koordinaten": sum(1 for v in geo.values() if v)}
