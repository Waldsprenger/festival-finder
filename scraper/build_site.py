"""Erzeugt site/data.js aus data/festivals.json und data/geo.json.

Die Seite laeuft auch per Doppelklick (file://). Dort blockiert der Browser
fetch() auf lokale Dateien, deshalb werden die Daten als JS-Datei ausgeliefert
und nicht als JSON nachgeladen.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
SITE = BASE / "site"
SITE.mkdir(exist_ok=True)

# Naeherungswerte, nur fuer Filter und Sortierung - keine Tagesaktualitaet noetig.
RATES = {"EUR": 1.0, "€": 1.0, "CHF": 1.06, "GBP": 1.17, "USD": 0.92,
         "DKK": 0.134, "SEK": 0.088, "NOK": 0.086, "PLN": 0.235,
         "CZK": 0.040, "HUF": 0.0025}

# "Spende" und "Zahl was du willst" sind kein fehlender Preis, sondern
# freier Eintritt mit Spendenbitte - fuer den Filter zaehlen sie als 0 EUR.
FREE = re.compile(r"kostenlos|gratis|freier eintritt|umsonst|frei\b|spende|"
                  r"zahl[,]?\s*was|pay what", re.I)

_N = r"\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:\.\d{1,2})?"
_C = r"€|EUR|CHF|GBP|USD|DKK|SEK|NOK|PLN|CZK|HUF"

# Reihenfolge ist Absicht: Spannen zuerst, damit "19,80 - 27,50 €" den
# unteren Wert liefert und nicht den oberen.
RANGE = re.compile(rf"({_N})\s*(?:-|–|bis)\s*(?:{_N})\s*({_C})", re.I)
NUM_CUR = re.compile(rf"({_N})\s*({_C})", re.I)
CUR_NUM = re.compile(rf"({_C})\s*({_N})", re.I)
ANY_CUR = re.compile(_C, re.I)
BARE = re.compile(_N)


def to_float(raw: str) -> float | None:
    raw = raw.strip()
    if "," in raw:                      # deutsches Format: 1.234,56
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def rate(cur: str) -> float:
    return RATES.get(cur if cur == "€" else cur.upper(), 1.0)


def price_eur(text: str) -> float | None:
    """Guenstigster Einstiegspreis in Euro; None wenn nicht ermittelbar.

    Nur Zahlen, die unmittelbar an einer Waehrung haengen, gelten als Preis.
    Sonst wuerde "VVK 199 EUR (Stufe 2)" als 2 EUR gelesen.
    """
    if not text:
        return None

    candidates: list[float] = []
    for m in RANGE.finditer(text):              # "19,80 - 27,50 €"
        v = to_float(m.group(1))
        if v is not None:
            candidates.append(v * rate(m.group(2)))
    for pattern, num_g, cur_g in ((NUM_CUR, 1, 2), (CUR_NUM, 2, 1)):
        for m in pattern.finditer(text):        # "351 €" / "EUR 49,50"
            v = to_float(m.group(num_g))
            if v is not None:
                candidates.append(v * rate(m.group(cur_g)))

    candidates = [c for c in candidates if 0 < c <= 5000]

    # Ein Gratis-Hinweis zaehlt nur, wenn er vor der ersten Preisangabe steht.
    # "Kostenlos bis 39 EUR je Event" ist freier Eintritt, waehrend bei
    # "VVK 45-172 EUR (Pay what you can)" der Nachsatz den Preis nicht aufhebt.
    frei = FREE.search(text)
    if frei:
        betrag = re.search(rf"({_N})\s*(?:{_C})|(?:{_C})\s*({_N})", text, re.I)
        if not candidates or (betrag and frei.start() < betrag.start()):
            return 0.0

    if not candidates and not ANY_CUR.search(text):
        # Waehrungslose Angabe wie "VVK 42,95 (Stufe 2)": hier zaehlt die erste
        # Zahl, nicht die kleinste - die Nachsaetze nennen Preisstufen, keine Preise.
        for m in BARE.finditer(text):
            v = to_float(m.group(0))
            if v is not None and 0 < v <= 5000:
                return round(v, 2)
        return None

    return round(min(candidates), 2) if candidates else None


# Bezugspunkt für die Obergrenze des Umkreisreglers
REF_PLZ = "97209"

LAT, LON, EURO = 9, 10, 6


def nice_ceil(value: float) -> int:
    """Auf die nächste runde Zahl aufrunden."""
    step = 100 if value >= 1000 else 50 if value >= 200 else 10
    return int(math.ceil(value / step) * step)


def haversine(a_lat, a_lon, b_lat, b_lon) -> float:
    r, rad = 6371.0, math.pi / 180
    d_lat, d_lon = (b_lat - a_lat) * rad, (b_lon - a_lon) * rad
    h = (math.sin(d_lat / 2) ** 2 +
         math.cos(a_lat * rad) * math.cos(b_lat * rad) * math.sin(d_lon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def max_distance_km(rows: list, plz: list) -> int:
    """Entfernung zum entferntesten Festival ab REF_PLZ, aufgerundet."""
    ref = next((p for p in plz if p[0] == REF_PLZ), None)
    if not ref:
        return 3300
    far = max((haversine(ref[2], ref[3], r[LAT], r[LON])
               for r in rows if r[LAT] is not None), default=0)
    return nice_ceil(far)


def earliest_month(rows: list) -> str:
    """Erster Tag des Monats, in dem das früheste Festival beginnt.

    Damit lässt sich im Kalender nichts einstellen, wofür es ohnehin keine
    Daten gibt: Startet das früheste Festival am 16.05.2018, ist der
    01.05.2018 die Untergrenze.
    """
    termine = [r[1] for r in rows if r[1]]
    if not termine:
        return ""
    return min(termine)[:8] + "01"


def max_price_eur(rows: list) -> int:
    """Teuerstes ausgelesenes Ticket, aufgerundet."""
    top = max((r[EURO] for r in rows if r[EURO] is not None), default=0)
    return nice_ceil(top)


def iso(d: str) -> str:
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", d or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def main() -> None:
    festivals = json.loads((DATA / "festivals.json").read_text(encoding="utf-8"))
    geo_path = DATA / "geo.json"
    geo = json.loads(geo_path.read_text(encoding="utf-8")) if geo_path.exists() else {}

    band_ix: dict[str, int] = {}
    bands: list[str] = []

    def bid(name: str) -> int:
        if name not in band_ix:
            band_ix[name] = len(bands)
            bands.append(name)
        return band_ix[name]

    rows = []
    with_geo = 0
    for f in festivals:
        city, country = f["city"].strip(), f["country"].strip()
        g = geo.get(f"{city}|{country}") or {}
        lat, lon = (g.get("lat"), g.get("lon")) if g else (None, None)
        if lat is not None:
            with_geo += 1
        rows.append([
            f["name"],                                   # 0
            iso(f["date_from"]),                         # 1
            iso(f["date_to"]),                           # 2
            city,                                        # 3
            country,                                     # 4
            f["venue"],                                  # 5
            price_eur(f["price"]),                       # 6
            f["price"],                                  # 7 Originaltext
            f["website"],                                # 8
            lat, lon,                                    # 9, 10
            sorted(bid(b) for b in f["lineup"]),         # 11
            f["genre"][:70],                             # 12
            f.get("note", ""),                           # 13
            1 if f.get("cancelled") else 0,              # 14
        ])

    # Ortsverzeichnis fuer die Wohnortsuche. Die veroeffentlichte Fassung darf
    # keine externen Dienste aufrufen, deshalb wird es mit ausgeliefert.
    gaz_path = DATA / "gazetteer.json"
    if gaz_path.exists():
        places = json.loads(gaz_path.read_text(encoding="utf-8"))
    else:                                  # Rueckfall: die Festivalorte selbst
        places = [[k.split("|")[0], v["lat"], v["lon"], ""]
                  for k, v in geo.items() if v and v.get("lat") is not None]

    plz_path = DATA / "plz.json"
    plz = json.loads(plz_path.read_text(encoding="utf-8")) if plz_path.exists() else []

    europe_path = DATA / "europe.json"
    europe = json.loads(europe_path.read_text(encoding="utf-8")) if europe_path.exists() else []

    payload = {
        "generated": date.today().isoformat(),
        "bands": bands,
        "festivals": rows,
        "places": places,
        "plz": plz,
        "europe": europe,
        "maxDistanceKm": max_distance_km(rows, plz),
        "maxPriceEur": max_price_eur(rows),
        "minDate": earliest_month(rows),
    }
    out = SITE / "data.js"
    out.write_text("window.DATA = " + json.dumps(payload, ensure_ascii=False,
                                                 separators=(",", ":")) + ";\n",
                   encoding="utf-8")

    priced = sum(1 for r in rows if r[6] is not None)
    print(f"{out}  ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"  Festivals {len(rows)} | mit Koordinaten {with_geo} | "
          f"mit Preis in EUR {priced} | Acts {len(bands)} | Orte {len(places)} | "
          f"PLZ {len(plz)}")
    print(f"  Reglergrenzen: Umkreis bis {payload['maxDistanceKm']} km "
          f"(ab {REF_PLZ}), Preis bis {payload['maxPriceEur']} EUR, "
          f"Kalender ab {payload['minDate'] or 'unbegrenzt'}")


if __name__ == "__main__":
    main()
