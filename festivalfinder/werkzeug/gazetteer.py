"""Ortsverzeichnisse aus GeoNames (CC BY 4.0).

Zwei Zwecke, zwei Größen:

  `data/gazetteer.json`   Wohnortsuche im Browser: DE/AT/CH vollständig, die
  `data/plz.json`         übrige Welt ab 15.000 Einwohnern, Postleitzahlen
                          DE/AT/CH. Beides liegt in site/data.js und muss klein
                          bleiben.

  `data/verortung.json`   Verortung der Festivals beim Bauen: Postleitzahlen
                          weltweit und alle Orte ab 1.000 Einwohnern. Bleibt
                          auf dem Rechner, wird nicht ausgeliefert.

  `data/wohnort.json`     Wohnortsuche aus jedem Land, bei Bedarf nachgeladen:
                          Postleitzahlen von 121 Ländern, so genau wie eine
                          Umkreissuche es braucht; Orte ab 1.000 Einwohnern,
                          Zweitnamen großer Städte („Warszawa", „Москва",
                          „東京"), Bundesstaaten und Provinzen.

Die Postleitzahl ist die verlässlichere Angabe: Ortsnamen sind mehrdeutig
(Bernau gibt es dreimal), eine Postleitzahl trifft genau einen Zustellbereich.
Deshalb lohnt die große Tabelle — sie bringt 634 Festivals von einem geratenen
Ortsmittelpunkt auf ihren Zustellbereich.
"""

import csv
import io
import math
import re
import statistics
import zipfile

from ..kern.text import fold
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
NAME, ASCII, ZWEIT, LAT, LON, FCLASS, FCODE, CC, ADMIN1, POP = 1, 2, 3, 4, 5, 6, 7, 8, 10, 14
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


# --------------------------------------------------------------------------
# Wohnortsuche aus jedem Land
# --------------------------------------------------------------------------

#: So genau bleibt eine Postleitzahl. Die Seite rechnet in Kilometern; fünf
#: davon Abweichung merkt kein Umkreisfilter. Portugal führt jede Straße mit
#: eigenem Code, Singapur jedes Haus — für die Umkreissuche genügt das Viertel.
PLZ_GENAU_KM = 5.0

#: Die Emirate haben keine Postleitzahlen; GeoNames führt dort 178.000
#: Postfachnummern, die ein Wohnort nie ist.
PLZ_OHNE = {"AE"}

#: Den Ländervorsatz schreiben manche Länder in den Code („LV-1050",
#: „L-4968"). Gesucht wird ohne ihn; die Seite liest ihn als Landesangabe.
PLZ_VORSATZ = {"LV": "LV", "LU": "L", "MD": "MD", "AZ": "AZ", "AD": "AD",
               "AI": "AI", "HT": "HT"}

#: Bundesstaaten und Provinzen, wie man sie hinter den Ort schreibt: „Austin,
#: TX", „Sydney NSW", „London, Ontario". Ohne sie läge „Portland, ME" in
#: Oregon — der größere Ort gleichen Namens. In den USA sind die Kennungen von
#: GeoNames schon die Postkürzel, Kanada und Australien zählen durch.
VERWALTUNG = {
    "US": {k: (k, n) for k, n in (
        ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
        ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"),
        ("DE", "Delaware"), ("DC", "District of Columbia"), ("FL", "Florida"),
        ("GA", "Georgia"), ("HI", "Hawaii"), ("ID", "Idaho"), ("IL", "Illinois"),
        ("IN", "Indiana"), ("IA", "Iowa"), ("KS", "Kansas"), ("KY", "Kentucky"),
        ("LA", "Louisiana"), ("ME", "Maine"), ("MD", "Maryland"),
        ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"),
        ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"),
        ("NE", "Nebraska"), ("NV", "Nevada"), ("NH", "New Hampshire"),
        ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
        ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"),
        ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"),
        ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"),
        ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"),
        ("VA", "Virginia"), ("WA", "Washington"), ("WV", "West Virginia"),
        ("WI", "Wisconsin"), ("WY", "Wyoming"))},
    "CA": {"01": ("AB", "Alberta"), "02": ("BC", "British Columbia"),
           "03": ("MB", "Manitoba"), "04": ("NB", "New Brunswick"),
           "05": ("NL", "Newfoundland and Labrador"), "07": ("NS", "Nova Scotia"),
           "08": ("ON", "Ontario"), "09": ("PE", "Prince Edward Island"),
           "10": ("QC", "Québec"), "11": ("SK", "Saskatchewan"), "12": ("YT", "Yukon"),
           "13": ("NT", "Northwest Territories"), "14": ("NU", "Nunavut")},
    "AU": {"01": ("ACT", "Australian Capital Territory"), "02": ("NSW", "New South Wales"),
           "03": ("NT", "Northern Territory"), "04": ("QLD", "Queensland"),
           "05": ("SA", "South Australia"), "06": ("TAS", "Tasmania"),
           "07": ("VIC", "Victoria"), "08": ("WA", "Western Australia")},
}

#: Zweitnamen nur für Städte ab dieser Größe: Wer „Warszawa", „Lisboa" oder
#: „東京" schreibt, meint fast immer eine große Stadt. Für alle ab 15.000
#: Einwohnern wären es dreimal so viele Namen für wenige Treffer mehr.
ZWEITNAMEN_AB = 100_000


def plz_schluessel(code: str, cc: str) -> tuple[str, str]:
    """(Schreibform, Suchschlüssel) einer Postleitzahl aus GeoNames.

    Die Schreibform behält die Trenner („3750-000", „624 66") — an ihr
    erkennt die Seite, aus welchem Land ein Code stammen kann. Der Schlüssel
    ist nur Großbuchstaben und Ziffern. „CEDEX" ist in Frankreich ein Zusatz
    für Großkunden, kein Teil des Gebiets.
    """
    form = re.sub(r"\s+CEDEX.*$", "", code.strip().upper())
    vorsatz = PLZ_VORSATZ.get(cc)
    if vorsatz and form.startswith(vorsatz):
        rest = form[len(vorsatz):].lstrip("- ")
        if rest[:1].isdigit():
            form = rest
    return form, re.sub(r"[^0-9A-Z]", "", form)


def form_von(code: str) -> str:
    """„SW1A" → „AA9A", „3750-000" → „9999-999"; Trenner werden zu „-"."""
    return re.sub(r"[\s.-]+", "-", re.sub(r"\d", "9", re.sub(r"[A-Z]", "A", code)))


def _km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b_lon - a_lon) / 2) ** 2)
    return 12742 * math.asin(min(1.0, math.sqrt(h)))


def plz_verdichten(codes: dict[str, tuple[float, float]],
                   genau_km: float = PLZ_GENAU_KM) -> dict[str, list[float]]:
    """Die kürzesten Präfixe, deren Codes alle nah beieinanderliegen.

    Ein Präfixbaum über die Codes eines Landes: Ein Knoten wird zum Blatt,
    sobald alle Codes darunter höchstens `genau_km` von ihrem Mittel entfernt
    liegen. Die Seite sucht dann mit dem längsten Präfix ihrer Eingabe, den es
    gibt. Höchstens zwei Stellen dürfen dabei wegfallen: Sonst fiele Monaco
    mit allen Codes in fünf Kilometern auf den leeren Präfix — und jede
    fünfstellige Zahl der Welt wäre eine Postleitzahl in Monaco.
    """
    ergebnis: dict[str, list[float]] = {}
    stapel = [("", list(codes.items()))]
    while stapel:
        praefix, eintraege = stapel.pop()
        lat = sum(v[0] for _, v in eintraege) / len(eintraege)
        lon = sum(v[1] for _, v in eintraege) / len(eintraege)
        kuerzest = min(len(c) for c, _ in eintraege)
        if (len(praefix) >= min(kuerzest, max(2, kuerzest - 2))
                and all(_km(lat, lon, *v) <= genau_km for _, v in eintraege)):
            ergebnis[praefix] = [round(lat, 3), round(lon, 3)]
            continue
        kinder: dict[str, list] = {}
        for c, v in eintraege:
            if len(c) == len(praefix):
                ergebnis[c] = [round(v[0], 3), round(v[1], 3)]
            else:
                kinder.setdefault(c[:len(praefix) + 1], []).append((c, v))
        stapel.extend(kinder.items())
    return dict(sorted(ergebnis.items()))


def wohnort_daten(netz: Abrufer, fein: dict[tuple[str, str], list]) -> dict:
    """Alles, was die Wohnortsuche über DE/AT/CH hinaus braucht."""
    # Postleitzahlen: verdichtet, dazu ihre Schreibformen je Land
    codes: dict[str, dict[str, tuple[float, float]]] = {}
    formen: dict[str, set[str]] = {}
    for r in zeilen(netz, "allCountries.zip", art="zip"):
        cc = r[Z_CC]
        if not cc or cc in PLZ_OHNE or not r[Z_LAT] or not r[Z_LON]:
            continue
        form, schluessel = plz_schluessel(r[Z_CODE], cc)
        if not schluessel:
            continue
        formen.setdefault(form_von(form), set()).add(cc)
        formen.setdefault(form_von(schluessel), set()).add(cc)
        if cc not in FEIN:          # DE/AT/CH stehen vollständig in geo.js
            codes.setdefault(cc, {}).setdefault(
                schluessel, (float(r[Z_LAT]), float(r[Z_LON])))
    plz = {cc: plz_verdichten(c) for cc, c in sorted(codes.items())}

    # Bundesstaaten: der Median ihrer Orte. Der Mittelwert läge für Alaska
    # irgendwo im Pazifik, weil die Aleuten über die Datumsgrenze reichen.
    #
    # Dazu jeder Ort mit seinem Staat. Die Ortslisten führen je Name und Land
    # nur den größten — es gibt aber 33 Springfields in den USA, und wer
    # „Springfield, IL" schreibt, meint keines davon in Missouri.
    punkte: dict[tuple[str, str], list[tuple[float, float]]] = {}
    staatorte: list[list] = []
    zweitnamen: list[list] = []
    for r in zeilen(netz, "cities1000.zip"):
        if r[CC] in VERWALTUNG and r[ADMIN1] in VERWALTUNG[r[CC]]:
            lat, lon = float(r[LAT]), float(r[LON])
            punkte.setdefault((r[CC], r[ADMIN1]), []).append((lat, lon))
            kuerzel = VERWALTUNG[r[CC]][r[ADMIN1]][0]
            for name in dict.fromkeys(n.strip() for n in (r[NAME], r[ASCII]) if n.strip()):
                staatorte.append([name, round(lat, 4), round(lon, 4), r[CC], kuerzel,
                                  int(r[POP] or 0)])
        if int(r[POP] or 0) >= ZWEITNAMEN_AB:
            zweitnamen += _zweitnamen(r)
    staatorte.sort(key=lambda e: -e[5])
    verwaltung: dict[str, dict[str, list]] = {}
    for (cc, admin), liste in sorted(punkte.items()):
        kuerzel, name = VERWALTUNG[cc][admin]
        verwaltung.setdefault(cc, {})[kuerzel] = [
            round(statistics.median(p[0] for p in liste), 3),
            round(statistics.median(p[1] for p in liste), 3), name]

    return {
        "plz": plz,
        "formen": {f: sorted(l) for f, l in sorted(formen.items())},
        "verwaltung": verwaltung,
        # Die großen liegen in geo.js bei, die übrigen kommen mit orte.js
        "staatorte_gross": [e[:5] for e in staatorte if e[5] >= 15000],
        "staatorte": [e[:5] for e in staatorte if e[5] < 15000],
        # Größte zuerst: Bei gleichem Namen gewinnt in der Suche der bekanntere
        "orte": [e[:4] for e in sorted(fein.values(), key=lambda e: -e[4])],
        "zweitnamen": [e[:4] for e in sorted(zweitnamen, key=lambda e: -e[4])],
    }


def _zweitnamen(r: list[str]) -> list[list]:
    """Die anderen Namen einer Stadt, ohne Kennungen und Wiederholungen."""
    gesehen = {fold(r[NAME]), fold(r[ASCII])}
    namen = []
    for n in r[ZWEIT].split(","):
        n = n.strip()
        # Flughafenkürzel („MUC") und Verweise sind keine Ortsnamen
        if (not n or len(n) > 40 or n.startswith("http")
                or (n.isascii() and n.isupper() and len(n) <= 4)):
            continue
        if (f := fold(n)) and f not in gesehen:
            gesehen.add(f)
            namen.append([n, round(float(r[LAT]), 4), round(float(r[LON]), 4),
                          r[CC], int(r[POP] or 0)])
    return namen


#: Was dieser Schritt aus dem Netz holt — und damit alles, was in ORDNER liegen darf
QUELLEN = (["countryInfo.txt", "zip_allCountries.zip", "dump_cities15000.zip",
            "dump_cities1000.zip"] + [f"dump_{cc}.zip" for cc in FEIN_BAU])
#: Was er schreibt
ERGEBNISSE = ["laender.json", "gazetteer.json", "laender_rahmen.json", "plz.json",
              "verortung.json", "wohnort.json"]


def aktuell() -> bool:
    """Sind alle Ergebnisse da und jünger als jede heruntergeladene Quelle?

    Dann gäbe ein neuer Durchgang dieselben Dateien — 13 Sekunden und das
    Einlesen von 60 MB Zip-Archiven für nichts. GeoNames-Daten ändern sich
    hier nur, wenn jemand die Downloads löscht.
    """
    quellen = [ORDNER / q for q in QUELLEN]
    ergebnisse = [DATA / e for e in ERGEBNISSE]
    if not all(p.exists() for p in quellen + ergebnisse):
        return False
    return min(p.stat().st_mtime for p in ergebnisse) >= max(p.stat().st_mtime for p in quellen)


def aufraeumen() -> list[str]:
    """Downloads unter früheren Namen löschen. Sie lagen jahrelang im
    Zwischenspeicher des Serverlaufs — 34 MB, die niemand mehr las."""
    weg = []
    for datei in ORDNER.glob("*"):
        if datei.is_file() and datei.name not in QUELLEN:
            datei.unlink()
            weg.append(datei.name)
    return weg


def bauen(netz: Abrufer) -> dict:
    """Alle fünf Dateien erzeugen; gibt die Kennzahlen zurück."""
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
    schreib_json(DATA / "verortung.json", {
        "plz": [[e[0], e[2], e[3], e[4]] for e in plz_welt],
        "orte": [e[:4] for e in fein.values()],
    }, kompakt=True)

    # --- Wohnortsuche aus jedem Land: nachgeladen, wenn sie gebraucht wird --
    print("Wohnortsuche: Postleitzahlen verdichten, Zweitnamen", flush=True)
    wohnort = wohnort_daten(netz, fein)
    schreib_json(DATA / "wohnort.json", wohnort, kompakt=True)

    return {"laender": len(laender), "orte_klein": len(schlank),
            "rahmen": len(rahmen), "plz_dach": len(plz_dach),
            "plz_welt": len(plz_welt), "orte_fein": len(fein),
            "plz_laender": len(wohnort["plz"]),
            "plz_verdichtet": sum(len(v) for v in wohnort["plz"].values()),
            "zweitnamen": len(wohnort["zweitnamen"])}
