"""Erzeugt site/data.js aus data/festivals.json und data/geo.json.

Die Seite laeuft auch per Doppelklick (file://). Dort blockiert der Browser
fetch() auf lokale Dateien, deshalb werden die Daten als JS-Datei ausgeliefert
und nicht als JSON nachgeladen.
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemeinsam import DATA, SITE, land_code  # noqa: E402  (Pfad muss vorher stehen)
from genres import OBERBEGRIFFE, oberbegriffe  # noqa: E402


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
    plz_path = DATA / "plz.json"
    plz = json.loads(plz_path.read_text(encoding="utf-8")) if plz_path.exists() else []

    # Oberbegriffe als Spaltennummern - die Namen stehen auf der Seite in
    # der jeweiligen Sprache, in den Daten steht nur der Index.
    genre_keys = list(OBERBEGRIFFE)
    genre_ix = {k: n for n, k in enumerate(genre_keys)}

    band_ix: dict[str, int] = {}
    bands: list[str] = []

    def bid(name: str) -> int:
        if name not in band_ix:
            band_ix[name] = len(bands)
            bands.append(name)
        return band_ix[name]

    # Postleitzahl -> Koordinaten. Eine PLZ trifft den Zustellbereich, waehrend
    # der Ortsname nur den Mittelpunkt der Gemeinde liefert - bei Flaechen-
    # gemeinden sind das schnell zehn Kilometer Unterschied.
    plz_index: dict[tuple[str, str], list] = {}
    for code, ort, lat, lon, cc in plz:
        plz_index.setdefault((code, cc), [lat, lon])

    # Der Geo-Cache ist unter der urspruenglichen Landesschreibweise abgelegt
    # ("Wacken|Deutschland"), die Festivals tragen inzwischen das Kuerzel.
    # Ein normalisierter Index erspart das erneute Geokodieren aller Orte.
    geo_index: dict[tuple[str, str], dict] = {}
    geo_ort: dict[str, tuple[dict, str]] = {}
    for schluessel, wert in geo.items():
        if not wert:
            continue
        ort, _, land = schluessel.partition("|")
        code = land_code(land)
        geo_index.setdefault((ort.strip().casefold(), code), wert)
        # Fehlt in der Quelle die Landesangabe, liefert sie der Geokodierer
        # als letztes Glied seiner Adresse mit ("..., Deutschland").
        if not code:
            code = land_code((wert.get("display") or "").rsplit(",", 1)[-1])
        geo_ort.setdefault(ort.strip().casefold(), (wert, code))

    rows = []
    with_geo = aus_plz = 0
    for f in festivals:
        city, country = f["city"].strip(), f["country"].strip()
        code = (f.get("plz") or "").strip()
        treffer = plz_index.get((code, country)) if code else None
        if treffer is None and code:
            # Land unbekannt oder abweichend notiert: eindeutige PLZ genuegt
            kandidaten = [v for (c, _), v in plz_index.items() if c == code]
            treffer = kandidaten[0] if len(kandidaten) == 1 else None

        if treffer:
            lat, lon = treffer
            aus_plz += 1
            if not country:
                passend = [cc for (c, cc) in plz_index if c == code]
                if len(set(passend)) == 1:
                    country = passend[0]
        else:
            # Fehlt die Landesangabe, zaehlt der Ortstreffer samt nachgetragenem
            # Kuerzel; sonst zuerst der genaue Treffer aus Ort und Land.
            g = None if not country else geo_index.get((city.casefold(), country))
            if g is None and city:
                treffer_ort = geo_ort.get(city.casefold())
                if treffer_ort:
                    g, ergaenzt = treffer_ort
                    country = country or ergaenzt
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
            [genre_ix[k] for k in oberbegriffe(f["genre"])],   # 15
        ])

    # Ortsverzeichnis fuer die Wohnortsuche. Die veroeffentlichte Fassung darf
    # keine externen Dienste aufrufen, deshalb wird es mit ausgeliefert.
    gaz_path = DATA / "gazetteer.json"
    if gaz_path.exists():
        places = json.loads(gaz_path.read_text(encoding="utf-8"))
    else:                                  # Rueckfall: die Festivalorte selbst
        places = [[k.split("|")[0], v["lat"], v["lon"], ""]
                  for k, v in geo.items() if v and v.get("lat") is not None]

    def lade(name: str) -> list:
        p = DATA / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    welt_grob = lade("welt_grob.json")
    welt_fein = lade("welt_fein.json")

    payload = {
        # mit Uhrzeit, damit auf der Seite steht, wie frisch die Daten sind
        "generated": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M%z"),
        "bands": bands,
        "genres": genre_keys,
        "festivals": rows,
        "places": places,
        "plz": plz,
        "world": welt_grob,
        "worldFine": welt_fein,
        # Ausschnitt, für den feine Umrisse vorliegen: lon0, lon1, lat0, lat1
        "fineBox": [-32.0, 46.0, 27.0, 72.0],
        "maxDistanceKm": max_distance_km(rows, plz),
        "maxPriceEur": max_price_eur(rows),
        "minDate": earliest_month(rows),
    }
    out = SITE / "data.js"
    out.write_text("window.DATA = " + json.dumps(payload, ensure_ascii=False,
                                                 separators=(",", ":")) + ";\n",
                   encoding="utf-8")

    priced = sum(1 for r in rows if r[6] is not None)
    mit_genre = sum(1 for r in rows if r[15])
    print(f"{out}  ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"  Koordinaten aus Postleitzahl: {aus_plz}, aus Ortsname: {with_geo - aus_plz}")
    print(f"  Festivals {len(rows)} | mit Koordinaten {with_geo} | "
          f"mit Preis in EUR {priced} | Acts {len(bands)} | Orte {len(places)} | "
          f"PLZ {len(plz)}")
    print(f"  Genre-Oberbegriffe {len(genre_keys)} | Festivals zugeordnet {mit_genre}")
    print(f"  Reglergrenzen: Umkreis bis {payload['maxDistanceKm']} km "
          f"(ab {REF_PLZ}), Preis bis {payload['maxPriceEur']} EUR, "
          f"Kalender ab {payload['minDate'] or 'unbegrenzt'}")


if __name__ == "__main__":
    main()
