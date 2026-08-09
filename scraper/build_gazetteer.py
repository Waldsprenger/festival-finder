"""Baut ein Ortsverzeichnis fuer die Umkreissuche ohne Netzzugriff.

Die veroeffentlichte Seite darf keine externen Requests absetzen, deshalb muss
die Wohnort-Suche vollstaendig lokal funktionieren. Quelle: GeoNames (CC BY 4.0).

  * DE/AT/CH        - alle Orte (auch kleine Gemeinden)
  * uebriges Europa - Orte ab 15.000 Einwohnern

Ergebnis: data/gazetteer.json  -> [[Name, lat, lon, Laendercode, Einwohner], ...]
"""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
CACHE = BASE / "cache" / "geonames"
CACHE.mkdir(parents=True, exist_ok=True)
OUT = DATA / "gazetteer.json"

UA = {"User-Agent": "FestivalFinder/1.0 (privates Projekt)"}
DUMP = "https://download.geonames.org/export/dump/"

FULL = ["DE", "AT", "CH"]          # feine Aufloesung
EUROPE = {
    "AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CY", "CZ", "DK", "EE", "FO",
    "FI", "FR", "DE", "GI", "GR", "GG", "HU", "IS", "IE", "IM", "IT", "JE", "LV",
    "LI", "LT", "LU", "MT", "MD", "MC", "ME", "NL", "MK", "NO", "PL", "PT", "RO",
    "SM", "RS", "SK", "SI", "ES", "SE", "CH", "UA", "GB", "VA", "XK",
}

# GeoNames-Spalten
NAME, ASCII, ALT, LAT, LON, FCLASS, FCODE, CC, POP = 1, 2, 3, 4, 5, 6, 7, 8, 14

# Nur bewohnte Orte, keine Ortsteile/Farmen
PLACE_CODES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG", "PPLS"}


def grab(filename: str) -> bytes:
    local = CACHE / filename
    if local.exists() and local.stat().st_size > 0:
        return local.read_bytes()
    print(f"  lade {filename} …", flush=True)
    r = requests.get(DUMP + filename, headers=UA, timeout=300)
    r.raise_for_status()
    local.write_bytes(r.content)
    return r.content


def rows(filename: str):
    """Zeilen der Datendatei im ZIP - nicht der beiliegenden readme.txt."""
    with zipfile.ZipFile(io.BytesIO(grab(filename))) as z:
        want = filename[:-4] + ".txt"
        names = z.namelist()
        inner = want if want in names else next(
            n for n in names if n.endswith(".txt") and "readme" not in n.lower())
        with z.open(inner) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8", newline="")
            for row in csv.reader(text, delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(row) > POP:
                    yield row


def main() -> None:
    entries: dict[tuple[str, str], list] = {}

    def add(name: str, lat: str, lon: str, cc: str, pop: str) -> None:
        name = name.strip()
        if not name or len(name) > 60:
            return
        key = (name.casefold(), cc)
        pop_i = int(pop or 0)
        cur = entries.get(key)
        if cur is None or pop_i > cur[4]:
            entries[key] = [name, round(float(lat), 4), round(float(lon), 4), cc, pop_i]

    for cc in FULL:
        print(f"{cc}: alle Orte", flush=True)
        for r in rows(f"{cc}.zip"):
            if r[FCLASS] == "P" and r[FCODE] in PLACE_CODES:
                add(r[NAME], r[LAT], r[LON], r[CC], r[POP])

    print("Europa: Orte ab 15.000 Einwohnern", flush=True)
    for r in rows("cities15000.zip"):
        if r[CC] in EUROPE and r[CC] not in FULL:
            add(r[NAME], r[LAT], r[LON], r[CC], r[POP])
            if r[ASCII] and r[ASCII] != r[NAME]:
                add(r[ASCII], r[LAT], r[LON], r[CC], r[POP])

    # Groesste Orte zuerst: bei mehrdeutigen Namen gewinnt der bekanntere.
    # Die Einwohnerzahl dient nur der Sortierung und wird nicht mit ausgeliefert.
    out = [e[:4] for e in sorted(entries.values(), key=lambda e: -e[4])]
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"{OUT}  ({OUT.stat().st_size / 1e6:.1f} MB, {len(out)} Orte)")


if __name__ == "__main__":
    main()
