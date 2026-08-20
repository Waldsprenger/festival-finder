"""Ortsverzeichnisse aus GeoNames (CC BY 4.0).

Zwei Zwecke, zwei Größen:

  `data/gazetteer.json`   Wohnortsuche im Browser: DE/AT/CH vollständig, übriges
  `data/plz.json`         Europa ab 15.000 Einwohnern, Postleitzahlen DE/AT/CH.
                          Beides liegt in site/data.js und muss klein bleiben.

  `data/verortung.json`   Verortung der Festivals beim Bauen: Postleitzahlen
                          ganz Europas und alle Orte ab 1.000 Einwohnern.
                          Bleibt auf dem Rechner, wird nicht ausgeliefert.

Die Postleitzahl ist die verlässlichere Angabe: Ortsnamen sind mehrdeutig
(Bernau gibt es dreimal), eine Postleitzahl trifft genau einen Zustellbereich.
Deshalb lohnt die große Tabelle — sie bringt 634 Festivals von einem geratenen
Ortsmittelpunkt auf ihren Zustellbereich.
"""

from __future__ import annotations

import csv
import io
import zipfile

from gemeinsam import CACHE as SEITEN_CACHE, DATA, EUROPA_CODES, schreib_json
from netz import datei_holen

CACHE = SEITEN_CACHE / "geonames"
GAZETTEER = DATA / "gazetteer.json"
PLZ = DATA / "plz.json"
VERORTUNG = DATA / "verortung.json"

DUMP = "https://download.geonames.org/export/dump/"
ZIP = "https://download.geonames.org/export/zip/"

FEIN = ["DE", "AT", "CH"]          # alle Orte, auch kleine Gemeinden
EUROPA = set(EUROPA_CODES)

# Spalten des Ortsdatensatzes
NAME, ASCII, LAT, LON, FCLASS, FCODE, CC, POP = 1, 2, 4, 5, 6, 7, 8, 14
# Spalten des Postleitzahl-Datensatzes
Z_CC, Z_CODE, Z_ORT, Z_LAT, Z_LON = 0, 1, 2, 9, 10

# Nur bewohnte Orte, keine Ortsteile/Farmen
ORTSARTEN = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG", "PPLS"}


def zeilen(datei: str, art: str = "dump"):
    """Zeilen der Datendatei im ZIP — nicht der beiliegenden readme.txt."""
    roh = datei_holen((DUMP if art == "dump" else ZIP) + datei,
                      CACHE / f"{art}_{datei}", f"{art}/{datei}")
    with zipfile.ZipFile(io.BytesIO(roh)) as z:
        gesucht = datei[:-4] + ".txt"
        namen = z.namelist()
        innen = gesucht if gesucht in namen else next(
            n for n in namen if n.endswith(".txt") and "readme" not in n.lower())
        mindestens = POP if art == "dump" else Z_LON
        with z.open(innen) as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8", newline="")
            for zeile in csv.reader(text, delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(zeile) > mindestens:
                    yield zeile


def orte_sammeln(ab_einwohnern: int) -> dict[tuple[str, str], list]:
    """Orte je (Name, Land): DE/AT/CH vollständig, Europa ab N Einwohnern.

    Bei gleichem Namen im selben Land gewinnt der größere Ort — dieselbe Regel,
    nach der auch ein Ortsverzeichnis den bekannteren zuerst nennt.
    """
    orte: dict[tuple[str, str], list] = {}

    def merken(name: str, lat: str, lon: str, cc: str, pop: str) -> None:
        name = name.strip()
        if not name or len(name) > 60:
            return
        schluessel, einwohner = (name.casefold(), cc), int(pop or 0)
        vorhanden = orte.get(schluessel)
        if vorhanden is None or einwohner > vorhanden[4]:
            orte[schluessel] = [name, round(float(lat), 4), round(float(lon), 4),
                                cc, einwohner]

    for cc in FEIN:
        print(f"{cc}: alle Orte", flush=True)
        for r in zeilen(f"{cc}.zip"):
            if r[FCLASS] == "P" and r[FCODE] in ORTSARTEN:
                merken(r[NAME], r[LAT], r[LON], r[CC], r[POP])

    datei = f"cities{ab_einwohnern}.zip"
    print(f"Europa: Orte ab {ab_einwohnern:,} Einwohnern".replace(",", "."), flush=True)
    for r in zeilen(datei):
        if r[CC] in EUROPA and r[CC] not in FEIN:
            merken(r[NAME], r[LAT], r[LON], r[CC], r[POP])
            # Die Umschrift ohne Sonderzeichen ist oft die Schreibweise der
            # Quellen ("Zurich" statt "Zürich").
            if r[ASCII] and r[ASCII] != r[NAME]:
                merken(r[ASCII], r[LAT], r[LON], r[CC], r[POP])
    return orte


def postleitzahlen(laender: list[str] | None) -> list[list]:
    """Je Postleitzahl der erste Zustellbereich.

    Ohne Länderliste kommt die Weltdatei und wird auf Europa gefiltert; das
    spart vierzig einzelne Abrufe.
    """
    gesehen: dict[tuple[str, str], list] = {}
    quellen = [f"{cc}.zip" for cc in laender] if laender else ["allCountries.zip"]
    for datei in quellen:
        print(f"Postleitzahlen: {datei}", flush=True)
        for r in zeilen(datei, art="zip"):
            code, cc = r[Z_CODE].strip().replace(" ", ""), r[Z_CC]
            if not code or cc not in EUROPA or not r[Z_LAT] or not r[Z_LON]:
                continue
            gesehen.setdefault((code, cc), [code, r[Z_ORT].strip(),
                                            round(float(r[Z_LAT]), 4),
                                            round(float(r[Z_LON]), 4), cc])
    return sorted(gesehen.values(), key=lambda e: (e[4], e[0]))


def main() -> None:
    # --- mitgeliefert: klein genug für site/data.js -----------------------
    orte = orte_sammeln(15000)
    # Größte Orte zuerst: Bei mehrdeutigen Namen gewinnt in der Suche der
    # bekanntere. Die Einwohnerzahl dient nur der Sortierung.
    schlank = [e[:4] for e in sorted(orte.values(), key=lambda e: -e[4])]
    schreib_json(GAZETTEER, schlank, kompakt=True)
    print(f"{GAZETTEER}  ({GAZETTEER.stat().st_size / 1e6:.1f} MB, "
          f"{len(schlank)} Orte)")

    plz_dach = postleitzahlen(FEIN)
    schreib_json(PLZ, plz_dach, kompakt=True)
    print(f"{PLZ}  ({PLZ.stat().st_size / 1e6:.2f} MB, {len(plz_dach)} Postleitzahlen)")

    # --- nur zum Bauen: so genau wie möglich ------------------------------
    fein = orte_sammeln(1000)
    plz_europa = postleitzahlen(None)
    # Beide Tabellen in derselben Form wie die mitgelieferten:
    # Postleitzahl bzw. Name, dann Breite, Länge, Land.
    schreib_json(VERORTUNG, {
        "plz": [[e[0], e[2], e[3], e[4]] for e in plz_europa],
        "orte": [e[:4] for e in fein.values()],
    }, kompakt=True)
    print(f"{VERORTUNG}  ({VERORTUNG.stat().st_size / 1e6:.1f} MB, "
          f"{len(plz_europa)} Postleitzahlen, {len(fein)} Orte)")


if __name__ == "__main__":
    main()
