"""Baut ein Ortsverzeichnis fuer die Umkreissuche ohne Netzzugriff.

Die veroeffentlichte Seite darf keine externen Requests absetzen, deshalb muss
die Wohnort-Suche vollstaendig lokal funktionieren. Quelle: GeoNames (CC BY 4.0).

  * DE/AT/CH        - alle Orte (auch kleine Gemeinden)
  * uebriges Europa - Orte ab 15.000 Einwohnern

Ergebnis:
  data/gazetteer.json -> [[Name, lat, lon, Laendercode], ...]
  data/plz.json       -> [[Postleitzahl, Ort, lat, lon, Laendercode], ...]

Die Postleitzahl ist die verlaesslichere Eingabe: Ortsnamen sind mehrdeutig
(Seeheim gibt es mehrfach), eine Postleitzahl trifft genau einen Zustellbereich.
"""

from __future__ import annotations

import csv
import io
import zipfile

from gemeinsam import CACHE as SEITEN_CACHE, DATA, EUROPA_CODES, schreib_json
from netz import datei_holen

CACHE = SEITEN_CACHE / "geonames"
OUT = DATA / "gazetteer.json"
OUT_PLZ = DATA / "plz.json"

DUMP = "https://download.geonames.org/export/dump/"

FULL = ["DE", "AT", "CH"]          # feine Aufloesung
EUROPE = set(EUROPA_CODES)

# GeoNames-Spalten
NAME, ASCII, ALT, LAT, LON, FCLASS, FCODE, CC, POP = 1, 2, 3, 4, 5, 6, 7, 8, 14

# Nur bewohnte Orte, keine Ortsteile/Farmen
PLACE_CODES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG", "PPLS"}


def grab(filename: str, kind: str = "dump") -> bytes:
    """kind='dump' liefert Ortsdaten, kind='zip' die Postleitzahlen."""
    basis = DUMP if kind == "dump" else "https://download.geonames.org/export/zip/"
    return datei_holen(basis + filename, CACHE / f"{kind}_{filename}",
                       f"{kind}/{filename}")


# Spalten des Postleitzahl-Datensatzes
Z_CC, Z_CODE, Z_PLACE, Z_LAT, Z_LON = 0, 1, 2, 9, 10


def build_plz() -> int:
    """Postleitzahlen fuer DE/AT/CH. Je Code der erste Zustellbereich."""
    seen: dict[tuple[str, str], list] = {}
    for cc in FULL:
        print(f"{cc}: Postleitzahlen", flush=True)
        for r in rows(f"{cc}.zip", kind="zip"):
            if len(r) <= Z_LON:
                continue
            code, place = r[Z_CODE].strip(), r[Z_PLACE].strip()
            if not code or not r[Z_LAT] or not r[Z_LON]:
                continue
            key = (code, r[Z_CC])
            if key not in seen:
                seen[key] = [code, place, round(float(r[Z_LAT]), 4),
                             round(float(r[Z_LON]), 4), r[Z_CC]]
    out = sorted(seen.values(), key=lambda e: (e[4], e[0]))
    schreib_json(OUT_PLZ, out, kompakt=True)
    print(f"{OUT_PLZ}  ({OUT_PLZ.stat().st_size / 1e6:.2f} MB, {len(out)} Postleitzahlen)")
    return len(out)


def rows(filename: str, kind: str = "dump"):
    """Zeilen der Datendatei im ZIP - nicht der beiliegenden readme.txt."""
    with zipfile.ZipFile(io.BytesIO(grab(filename, kind))) as z:
        want = filename[:-4] + ".txt"
        names = z.namelist()
        inner = want if want in names else next(
            n for n in names if n.endswith(".txt") and "readme" not in n.lower())
        # Ortsdatensatz hat 19 Spalten, der Postleitzahlsatz nur 12
        need = POP if kind == "dump" else Z_LON
        with z.open(inner) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8", newline="")
            for row in csv.reader(text, delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(row) > need:
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
    schreib_json(OUT, out, kompakt=True)
    print(f"{OUT}  ({OUT.stat().st_size / 1e6:.1f} MB, {len(out)} Orte)")
    build_plz()


if __name__ == "__main__":
    main()
