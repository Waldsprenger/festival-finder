"""Ortsverzeichnisse aus GeoNames (CC BY 4.0).

Zwei Zwecke, zwei Größen:

  `data/gazetteer.json`   Wohnortsuche im Browser: DE/AT/CH vollständig, die
  `data/plz.json`         übrige Welt ab 15.000 Einwohnern, Postleitzahlen
                          DE/AT/CH. Beides liegt in site/data.js und muss klein
                          bleiben.

  `data/verortung.json`   Verortung der Festivals beim Bauen: Postleitzahlen
                          weltweit und alle Orte ab 1.000 Einwohnern. Bleibt
                          auf dem Rechner, wird nicht ausgeliefert — bis auf
                          den Teil, den die Seite bei Bedarf nachlädt.

Die Postleitzahl ist die verlässlichere Angabe: Ortsnamen sind mehrdeutig
(Bernau gibt es dreimal), eine Postleitzahl trifft genau einen Zustellbereich.
Deshalb lohnt die große Tabelle — sie bringt 634 Festivals von einem geratenen
Ortsmittelpunkt auf ihren Zustellbereich.
"""

import csv
import io
import zipfile

from ..netz import Abrufer
from ..pfade import CACHE, DATA, schreib_json

ORDNER = CACHE / "geonames"
DUMP = "https://download.geonames.org/export/dump/"
ZIP = "https://download.geonames.org/export/zip/"

# Fein aufgelöst wird zweimal verschieden, weil die beiden Verzeichnisse
# verschiedene Rücksichten kennen:
#
#   Im Browser zählt jedes Kilobyte — dort stehen DE/AT/CH vollständig, weil
#   die Seite von dort genutzt wird und der Wohnort meist von dort kommt.
#
#   Beim Bauen zählt nur Genauigkeit. Dort kommt NL hinzu: wannafest liefert
#   über tausend niederländische Festivals, viele in Dörfern unter tausend
#   Einwohnern. Für Großbritannien lohnt es nicht — 3,6 MB Ortsdaten lösen
#   22 offene Fälle.
#
# Alles andere gilt weltweit: Ein Festival in Tokio, Melbourne oder São Paulo
# soll denselben Punkt auf der Karte bekommen wie eines in Kiel.
FEIN = ["DE", "AT", "CH"]
FEIN_BAU = FEIN + ["NL"]

#: Spalten des Ortsdatensatzes
NAME, ASCII, LAT, LON, FCLASS, FCODE, CC, POP = 1, 2, 4, 5, 6, 7, 8, 14
#: Spalten des Postleitzahl-Datensatzes
Z_CC, Z_CODE, Z_ORT, Z_LAT, Z_LON = 0, 1, 2, 9, 10

#: Nur bewohnte Orte, keine Ortsteile oder Farmen
ORTSARTEN = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG", "PPLS"}


def laendertabelle(netz: Abrufer) -> dict[str, dict]:
    """Alle Staaten der Welt: Kürzel, englischer Name, Kontinent.

    Die handgeschriebene Liste in `kern/orte.py` kennt Europa und eine Handvoll
    Namen darüber hinaus. Weltweit braucht es alle 252 — und den Kontinent
    dazu, damit die Seite nach Erdteilen sortieren kann.
    """
    roh = netz.datei_holen(DUMP + "countryInfo.txt", ORDNER / "countryInfo.txt",
                           "Länderliste")
    tabelle = {}
    for zeile in roh.decode("utf-8").splitlines():
        if not zeile or zeile.startswith("#"):
            continue
        s = zeile.split("\t")
        if len(s) > 8 and len(s[0]) == 2:
            tabelle[s[0]] = {"name": s[4], "kontinent": s[8]}
    return dict(sorted(tabelle.items()))


def zeilen(netz: Abrufer, datei: str, art: str = "dump"):
    """Zeilen der Datendatei im ZIP — nicht der beiliegenden readme.txt."""
    roh = netz.datei_holen((DUMP if art == "dump" else ZIP) + datei,
                           ORDNER / f"{art}_{datei}", f"{art}/{datei}")
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


def orte_sammeln(netz: Abrufer, ab_einwohnern: int,
                 vollstaendig: list[str]) -> dict[tuple[str, str], list]:
    """Orte je (Name, Land): genannte Länder vollständig, die Welt ab N Einwohnern.

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

    for cc in vollstaendig:
        print(f"{cc}: alle Orte", flush=True)
        for r in zeilen(netz, f"{cc}.zip"):
            if r[FCLASS] == "P" and r[FCODE] in ORTSARTEN:
                merken(r[NAME], r[LAT], r[LON], r[CC], r[POP])

    print(f"Welt: Orte ab {ab_einwohnern:,} Einwohnern".replace(",", "."), flush=True)
    for r in zeilen(netz, f"cities{ab_einwohnern}.zip"):
        if r[CC] and r[CC] not in vollstaendig:
            merken(r[NAME], r[LAT], r[LON], r[CC], r[POP])
            # Die Umschrift ohne Sonderzeichen ist oft die Schreibweise der
            # Quellen („Zurich" statt „Zürich").
            if r[ASCII] and r[ASCII] != r[NAME]:
                merken(r[ASCII], r[LAT], r[LON], r[CC], r[POP])
    return orte


def postleitzahlen(netz: Abrufer) -> list[list]:
    """Je Postleitzahl der erste Zustellbereich, weltweit.

    Eine einzige Weltdatei statt vierzig Länderabrufe; gefiltert wird hier.
    """
    gesehen: dict[tuple[str, str], list] = {}
    print("Postleitzahlen: allCountries.zip", flush=True)
    for r in zeilen(netz, "allCountries.zip", art="zip"):
        code, cc = r[Z_CODE].strip().replace(" ", ""), r[Z_CC]
        if not code or not cc or not r[Z_LAT] or not r[Z_LON]:
            continue
        gesehen.setdefault((code, cc), [code, r[Z_ORT].strip(),
                                        round(float(r[Z_LAT]), 4),
                                        round(float(r[Z_LON]), 4), cc])
    return sorted(gesehen.values(), key=lambda e: (e[4], e[0]))


def kurze_codes(alle: list[list]) -> set[str]:
    """Länder mit höchstens vierstelligen Postleitzahlen.

    Genau an denen scheitert Nominatim: „75001 FR" findet der Dienst, „1012 NL"
    nicht, weil niederländische Codes dort nur mit ihrem Buchstabenteil erfasst
    sind. Für diese Länder lohnt die eigene Tabelle — sie wird nachgeladen,
    nicht mitgeliefert.
    """
    laenge: dict[str, int] = {}
    for code, _ort, _la, _lo, cc in alle:
        laenge[cc] = max(laenge.get(cc, 0), len(code))
    return {cc for cc, n in laenge.items() if n <= 4}


def bauen(netz: Abrufer) -> dict:
    """Alle vier Dateien erzeugen; gibt die Kennzahlen zurück."""
    laender = laendertabelle(netz)
    schreib_json(DATA / "laender.json", laender)

    # --- mitgeliefert: klein genug für site/data.js -----------------------
    orte = orte_sammeln(netz, 15000, FEIN)
    # Größte Orte zuerst: Bei mehrdeutigen Namen gewinnt in der Suche der
    # bekanntere. Die Einwohnerzahl dient nur der Sortierung.
    schlank = [e[:4] for e in sorted(orte.values(), key=lambda e: -e[4])]
    schreib_json(DATA / "gazetteer.json", schlank, kompakt=True)

    # Der Kasten je Land: Er entscheidet später, ob eine Koordinate zum Land der
    # Quelle passt. Großzügig gerechnet — Frankreich reicht bis
    # Französisch-Guayana —, damit nur grobe Verwechslungen auffallen.
    rahmen: dict[str, list[float]] = {}
    for _name, lat, lon, cc, _pop in orte.values():
        r = rahmen.setdefault(cc, [90.0, -90.0, 180.0, -180.0])
        r[0], r[1] = min(r[0], lat), max(r[1], lat)
        r[2], r[3] = min(r[2], lon), max(r[3], lon)
    schreib_json(DATA / "laender_rahmen.json",
                 {cc: [round(v, 2) for v in r] for cc, r in sorted(rahmen.items())})

    plz_welt = postleitzahlen(netz)
    plz_dach = [e for e in plz_welt if e[4] in FEIN]
    schreib_json(DATA / "plz.json", plz_dach, kompakt=True)

    # --- nur zum Bauen: so genau wie möglich ------------------------------
    fein = orte_sammeln(netz, 1000, FEIN_BAU)
    # Einmal bestimmen, nicht je Eintrag — sonst läuft es nie durch.
    kurz = kurze_codes(plz_welt) - set(FEIN)
    schreib_json(DATA / "verortung.json", {
        "plz": [[e[0], e[2], e[3], e[4]] for e in plz_welt],
        "orte": [e[:4] for e in fein.values()],
        # Für die nachladbare Fassung der Webseite: Postleitzahlen der Länder,
        # die Nominatim nicht beantwortet, mit Ortsnamen für die Anzeige.
        "plz_nachladen": [e for e in plz_welt if e[4] in kurz],
    }, kompakt=True)

    return {"laender": len(laender), "orte_klein": len(schlank),
            "rahmen": len(rahmen), "plz_dach": len(plz_dach),
            "plz_welt": len(plz_welt), "orte_fein": len(fein),
            "plz_nachladen": sum(1 for e in plz_welt if e[4] in kurz)}
