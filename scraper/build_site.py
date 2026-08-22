"""Erzeugt site/data.js aus den Daten in data/.

Alles, was die Webseite braucht, steht danach in einer einzigen JS-Datei:
Festivals als Zahlenreihen, Bandnamen und Genres als Listen, dazu das
Ortsverzeichnis und die Kartengrenzen. Die Seite läuft damit auch per
Doppelklick (file://), wo der Browser fetch() auf lokale Dateien blockiert.
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime

from gemeinsam import (DATA, EUROPA_RAHMEN, ISO_CODES, KONTINENT, SITE,
                       land_code, lies_json)
from genres import OBERBEGRIFFE, oberbegriffe
from text import KOSTENLOS, fold

# Spalten einer Festivalzeile - dieselbe Reihenfolge steht in site/app.js
NAME, VON, BIS, ORT, LAND, VENUE, EURO, PREIS_TEXT, WEB, LAT, LON, \
    LINEUP, HINWEIS, ABGESAGT, GENRES = range(15)

# Bezugspunkt für die Obergrenze des Umkreisreglers
REF_PLZ = "97209"


# --------------------------------------------------------------------------
# Preise
# --------------------------------------------------------------------------

# Näherungswerte, nur für Filter und Sortierung - keine Tagesaktualität nötig.
KURSE = {"EUR": 1.0, "€": 1.0, "CHF": 1.06, "GBP": 1.17, "USD": 0.92,
         "DKK": 0.134, "SEK": 0.088, "NOK": 0.086, "PLN": 0.235,
         "CZK": 0.040, "HUF": 0.0025}

# Welche Währung in welchem Land gilt. Nur die, für die oben ein Kurs steht:
# Ein Feld "von - bis" in einer Währung, die niemand umrechnen kann, wäre eine
# Zahl ohne Bedeutung. Alles Übrige rechnet in Euro.
WAEHRUNG_LAND = {
    "CH": "CHF", "LI": "CHF",
    "GB": "GBP", "GG": "GBP", "JE": "GBP", "IM": "GBP", "GI": "GBP",
    "US": "USD", "EC": "USD", "SV": "USD", "PA": "USD",
    "DK": "DKK", "GL": "DKK", "FO": "DKK",
    "SE": "SEK", "NO": "NOK", "SJ": "NOK",
    "PL": "PLN", "CZ": "CZK", "HU": "HUF",
}

_ZAHL = r"\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:\.\d{1,2})?"
_WAEHRUNG = r"€|EUR|CHF|GBP|USD|DKK|SEK|NOK|PLN|CZK|HUF"

# Reihenfolge ist Absicht: Spannen zuerst, damit "19,80 - 27,50 €" den unteren
# Wert liefert und nicht den oberen.
SPANNE = re.compile(rf"({_ZAHL})\s*(?:-|–|bis)\s*(?:{_ZAHL})\s*({_WAEHRUNG})", re.I)
ZAHL_WAEHRUNG = re.compile(rf"({_ZAHL})\s*({_WAEHRUNG})", re.I)
WAEHRUNG_ZAHL = re.compile(rf"({_WAEHRUNG})\s*({_ZAHL})", re.I)
IRGENDEINE_WAEHRUNG = re.compile(_WAEHRUNG, re.I)
NACKTE_ZAHL = re.compile(_ZAHL)


def zahl(roh: str) -> float | None:
    roh = roh.strip()
    if "," in roh:                      # deutsches Format: 1.234,56
        roh = roh.replace(".", "").replace(",", ".")
    try:
        return float(roh)
    except ValueError:
        return None


def kurs(waehrung: str) -> float:
    return KURSE.get(waehrung if waehrung == "€" else waehrung.upper(), 1.0)


def preis_eur(text: str) -> float | None:
    """Günstigster Einstiegspreis in Euro; None, wenn nicht ermittelbar.

    Nur Zahlen, die unmittelbar an einer Währung hängen, gelten als Preis.
    Sonst würde "VVK 199 EUR (Stufe 2)" als 2 EUR gelesen.
    """
    if not text:
        return None

    kandidaten: list[float] = []
    for m in SPANNE.finditer(text):                      # "19,80 - 27,50 €"
        v = zahl(m.group(1))
        if v is not None:
            kandidaten.append(v * kurs(m.group(2)))
    for muster, zahl_gruppe, waehrung_gruppe in ((ZAHL_WAEHRUNG, 1, 2),
                                                 (WAEHRUNG_ZAHL, 2, 1)):
        for m in muster.finditer(text):                  # "351 €" / "EUR 49,50"
            v = zahl(m.group(zahl_gruppe))
            if v is not None:
                kandidaten.append(v * kurs(m.group(waehrung_gruppe)))

    kandidaten = [c for c in kandidaten if 0 < c <= 5000]

    # Ein Gratis-Hinweis zählt nur, wenn er vor der ersten Preisangabe steht.
    # "Kostenlos bis 39 EUR je Event" ist freier Eintritt, während bei "VVK
    # 45-172 EUR (Pay what you can)" der Nachsatz den Preis nicht aufhebt.
    frei = KOSTENLOS.search(text)
    if frei:
        betrag = re.search(rf"({_ZAHL})\s*(?:{_WAEHRUNG})|(?:{_WAEHRUNG})\s*({_ZAHL})",
                           text, re.I)
        if not kandidaten or (betrag and frei.start() < betrag.start()):
            return 0.0

    if not kandidaten and not IRGENDEINE_WAEHRUNG.search(text):
        # Währungslose Angabe wie "VVK 42,95 (Stufe 2)": hier zählt die erste
        # Zahl, nicht die kleinste - die Nachsätze nennen Preisstufen.
        for m in NACKTE_ZAHL.finditer(text):
            v = zahl(m.group(0))
            if v is not None and 0 < v <= 5000:
                return round(v, 2)
        return None

    return round(min(kandidaten), 2) if kandidaten else None


# --------------------------------------------------------------------------
# Reglergrenzen
# --------------------------------------------------------------------------

def aufrunden(wert: float) -> int:
    """Auf die nächste runde Zahl aufrunden."""
    schritt = 100 if wert >= 1000 else 50 if wert >= 200 else 10
    return int(math.ceil(wert / schritt) * schritt)


def luftlinie(a_lat, a_lon, b_lat, b_lon) -> float:
    r, rad = 6371.0, math.pi / 180
    d_lat, d_lon = (b_lat - a_lat) * rad, (b_lon - a_lon) * rad
    h = (math.sin(d_lat / 2) ** 2 +
         math.cos(a_lat * rad) * math.cos(b_lat * rad) * math.sin(d_lon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def max_entfernung_km(zeilen: list, plz: list) -> int:
    """Entfernung zum entferntesten Festival ab REF_PLZ, aufgerundet."""
    ref = next((p for p in plz if p[0] == REF_PLZ), None)
    if not ref:
        return 3300
    weit = max((luftlinie(ref[2], ref[3], z[LAT], z[LON])
                for z in zeilen if z[LAT] is not None), default=0)
    return aufrunden(weit)


def max_preis_eur(zeilen: list) -> int:
    """Teuerstes ausgelesenes Ticket, aufgerundet."""
    return aufrunden(max((z[EURO] for z in zeilen if z[EURO] is not None), default=0))


def datenrahmen(zeilen: list) -> list[float]:
    """Das Rechteck um alle Festivals mit Koordinate: lat0, lat1, lon0, lon1.

    Es bestimmt den Kartenausschnitt, solange kein Wohnort eingetragen ist.
    Fest verdrahtet war dort Mitteleuropa - bei weltweiten Daten zeigte die
    Karte damit einen Bruchteil dessen, was sie hat.
    """
    punkte = [(z[LAT], z[LON]) for z in zeilen if z[LAT] is not None]
    if not punkte:
        return [EUROPA_RAHMEN[0], EUROPA_RAHMEN[1], EUROPA_RAHMEN[2], EUROPA_RAHMEN[3]]
    lats = [p[0] for p in punkte]
    lons = [p[1] for p in punkte]
    return [round(min(lats), 2), round(max(lats), 2),
            round(min(lons), 2), round(max(lons), 2)]


def frueheste_monatsgrenze(zeilen: list) -> str:
    """Erster Tag des Monats, in dem das früheste Festival beginnt.

    Damit lässt sich im Kalender nichts einstellen, wofür es ohnehin keine
    Daten gibt: Startet das früheste Festival am 16.05.2026, ist der 01.05.2026
    die Untergrenze.
    """
    termine = [z[VON] for z in zeilen if z[VON]]
    return min(termine)[:8] + "01" if termine else ""


def iso(datum: str) -> str:
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", datum or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


# --------------------------------------------------------------------------
# Koordinaten
# --------------------------------------------------------------------------

def laender_rahmen(orte: list) -> dict[str, tuple[float, float, float, float]]:
    """Grobe Umrisse je Land aus dem Ortsverzeichnis: (lat0, lat1, lon0, lon1)."""
    rahmen: dict[str, list[float]] = {}
    for _name, lat, lon, cc in orte:
        if not cc:
            continue
        r = rahmen.setdefault(cc, [90.0, -90.0, 180.0, -180.0])
        r[0], r[1] = min(r[0], lat), max(r[1], lat)
        r[2], r[3] = min(r[2], lon), max(r[3], lon)
    return {cc: tuple(r) for cc, r in rahmen.items()}


def platzhalter(festivals: list) -> set[tuple[float, float]]:
    """Koordinaten, die für mehrere verschiedene Orte herhalten müssen.

    Die Quelle setzt bei unbekanntem Ort gern den Landesmittelpunkt ein -
    51.5/10.5 steht dreizehnmal da, quer durch Deutschland und die Schweiz.
    Ein echter Veranstaltungsort taucht zwar auch mehrfach auf, dann aber
    immer mit demselben Ortsnamen.
    """
    orte: dict[tuple[float, float], set[str]] = {}
    for f in festivals:
        if f["lat"] is None:
            continue
        schluessel = (round(f["lat"], 4), round(f["lon"], 4))
        orte.setdefault(schluessel, set()).add((f["city"] or "").casefold())
    return {k for k, v in orte.items() if len(v) >= 3}


class Verorter:
    """Findet zu jedem Festival eine Koordinate — in vier Rängen.

    1. Postleitzahl: trifft den Zustellbereich und ist damit am genauesten.
       Die große Tabelle deckt ganz Europa ab; ohne sie bleibt es bei DE/AT/CH.
    2. Ortsname im Geo-Cache (Nominatim), sofern schon einmal gefragt.
    3. Ortsname im mitgebauten Ortsverzeichnis — für alles, was der Cache noch
       nicht kennt. Das erspart die Nachfrage bei einem fremden Dienst.
    4. Der Punkt aus dem Datenblatt der Quellseite, aber nur, wenn er im Rahmen
       seines Landes liegt: Bei 37 Einträgen liegt er im falschen Land, Lugano
       landete in Buenos Aires, Basel in Berlin.

    Warum der Cache vor dem Ortsverzeichnis steht: Bei mehrdeutigen Namen
    wählen beide verschieden — "Bernau" gibt es dreimal in Deutschland. Keiner
    hat nachweislich recht, deshalb bleibt es bei der Antwort, die schon in den
    Daten steht, statt bestehende Koordinaten ohne Grund zu verschieben.
    """

    def __init__(self, festivals: list, geo: dict, verortung: dict,
                 gazetteer: list, plz: list):
        self.aus_plz = self.aus_ort = self.aus_quelle = self.gefunden = 0

        # Postleitzahl -> Koordinate, einmal mit Land und einmal ohne. Der
        # zweite Index fängt Einträge ohne Landesangabe ab, ohne dafür die
        # ganze Tabelle zu durchlaufen; mehrdeutige Codes fallen dabei weg.
        plz_tabelle = verortung.get("plz") or [[c, la, lo, cc]
                                               for c, _ort, la, lo, cc in plz]
        self.nach_plz: dict[tuple[str, str], tuple] = {}
        self.nur_plz: dict[str, tuple] = {}
        mehrdeutig: set[str] = set()
        for code, lat, lon, cc in plz_tabelle:
            self.nach_plz.setdefault((code, cc), (lat, lon))
            if code in self.nur_plz and self.nur_plz[code][2] != cc:
                mehrdeutig.add(code)
            self.nur_plz.setdefault(code, (lat, lon, cc))
        for code in mehrdeutig:
            self.nur_plz.pop(code, None)

        # Der Geo-Cache ist unter der ursprünglichen Landesschreibweise
        # abgelegt ("Wacken|Deutschland"), die Festivals tragen inzwischen das
        # Kürzel. Ein normalisierter Index erspart das erneute Geokodieren.
        self.cache_mit_land: dict[tuple[str, str], dict] = {}
        self.cache_ohne_land: dict[str, tuple[dict, str]] = {}
        for schluessel, wert in geo.items():
            if not wert or wert.get("lat") is None:
                continue
            ort, _, land = schluessel.partition("|")
            code = land_code(land)
            self.cache_mit_land.setdefault((ort.strip().casefold(), code), wert)
            # Fehlt in der Quelle die Landesangabe, liefert sie der Geokodierer
            # als letztes Glied seiner Adresse mit ("..., Deutschland").
            if not code:
                code = land_code((wert.get("display") or "").rsplit(",", 1)[-1])
            self.cache_ohne_land.setdefault(ort.strip().casefold(), (wert, code))

        # Ortsverzeichnis: gefaltete Namen, weil GeoNames "Zürich" schreibt und
        # die Quellen mal "Zurich", mal "Zuerich".
        orte = verortung.get("orte") or gazetteer
        self.nach_ort: dict[tuple[str, str], tuple] = {}
        for name, lat, lon, cc in orte:
            self.nach_ort.setdefault((fold(name), cc), (lat, lon))

        self.rahmen = laender_rahmen(orte)
        self.verdaechtig = platzhalter(festivals)

    def __call__(self, f: dict) -> tuple[float | None, float | None, str]:
        """Koordinate und (gegebenenfalls ergänztes) Land eines Festivals."""
        city, country = f["city"].strip(), f["country"].strip()
        code = (f["plz"] or "").strip().replace(" ", "")

        treffer = self.nach_plz.get((code, country)) if code else None
        if treffer is None and code and code in self.nur_plz:
            # Land unbekannt oder abweichend notiert: eindeutige PLZ genügt
            lat, lon, cc = self.nur_plz[code]
            treffer, country = (lat, lon), country or cc
        if treffer:
            self.aus_plz += 1
            self.gefunden += 1
            return treffer[0], treffer[1], country

        # Zuerst der genaue Treffer aus Ort und Land; fehlt die Landesangabe,
        # zählt der Ortstreffer samt nachgetragenem Kürzel.
        g = self.cache_mit_land.get((city.casefold(), country)) if country else None
        if g is None and city:
            gefunden = self.cache_ohne_land.get(city.casefold())
            if gefunden:
                g, ergaenzt = gefunden
                country = country or ergaenzt
        if g and g.get("lat") is not None:
            self.gefunden += 1
            return g["lat"], g["lon"], country

        treffer = self.nach_ort.get((fold(city), country)) if city and country else None
        if treffer:
            self.aus_ort += 1
            self.gefunden += 1
            return treffer[0], treffer[1], country

        lat, lon = self.quellkoordinate(f, country)
        if lat is not None:
            self.aus_quelle += 1
            self.gefunden += 1
        return lat, lon, country

    def quellkoordinate(self, f: dict, country: str):
        """Koordinate der Quellseite, sofern sie zum Land passt."""
        lat, lon = f["lat"], f["lon"]
        if lat is None or lon is None:
            return None, None
        if (round(lat, 4), round(lon, 4)) in self.verdaechtig:
            return None, None
        r = self.rahmen.get(country)
        if r and not (r[0] - 1 <= lat <= r[1] + 1 and r[2] - 1 <= lon <= r[3] + 1):
            return None, None
        return lat, lon


# --------------------------------------------------------------------------

def pruefe_zeilen(zeilen: list, bands: list, genres: list) -> None:
    """Die Zahlenreihen prüfen, bevor sie ausgeliefert werden.

    Die Webseite liest jede Zeile über feste Spaltennummern und jede Band über
    ihren Index. Stimmt daran etwas nicht, bleibt die Seite leer - und zwar
    still. Deshalb lieber hier abbrechen: Dann behält die Veröffentlichung den
    letzten guten Stand.
    """
    for nr, z in enumerate(zeilen):
        if len(z) != 16:
            raise ValueError(f"Zeile {nr} hat {len(z)} statt 16 Spalten")
        if not isinstance(z[NAME], str) or not z[NAME]:
            raise ValueError(f"Zeile {nr} ohne Namen")
        if any(not 0 <= b < len(bands) for b in z[LINEUP]):
            raise ValueError(f"{z[NAME]}: Bandnummer außerhalb der Liste")
        if any(not 0 <= g < len(genres) for g in z[GENRES]):
            raise ValueError(f"{z[NAME]}: Genrenummer außerhalb der Liste")
        if (z[LAT] is None) != (z[LON] is None):
            raise ValueError(f"{z[NAME]}: nur eine Koordinatenhälfte")
        if z[EURO] is not None and not 0 <= z[EURO] <= 5000:
            raise ValueError(f"{z[NAME]}: Preis {z[EURO]} ist unplausibel")


def als_javascript(payload: dict) -> str:
    """Die Daten als JS-Datei — der Inhalt bleibt dabei JSON.

    `window.DATA = {…}` müsste der Browser als Quelltext lesen; über
    JSON.parse geht dasselbe rund doppelt so schnell (gemessen 64 statt 137 ms
    für 6 MB). Die JSON-Zeichenkette steht dafür in einfachen Anführungszeichen,
    sodass die vielen doppelten aus dem JSON unangetastet bleiben.
    """
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    text = (text.replace("\\", "\\\\").replace("'", "\\'")
                # In der gebündelten Einzelseite steht das Ganze in einem
                # <script>; ein "</" im Text würde es sonst beenden.
                .replace("</", "<\\/")
                # Zeilentrenner sind in JSON erlaubt, in JS-Zeichenketten nicht
                .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return f"window.DATA = JSON.parse('{text}');\n"


def main() -> None:
    festivals = lies_json(DATA / "festivals.json", [])
    geo = lies_json(DATA / "geo.json", {})
    plz = lies_json(DATA / "plz.json", [])
    gazetteer = lies_json(DATA / "gazetteer.json", [])
    # Die große Verortungstabelle wird nicht mitversioniert; fehlt sie, reichen
    # die mitgelieferten Verzeichnisse (dann eben nur DE/AT/CH bei den PLZ).
    verortung = lies_json(DATA / "verortung.json", {})

    # Oberbegriffe als Spaltennummern - die Namen stehen auf der Seite in der
    # jeweiligen Sprache, in den Daten steht nur der Index.
    genre_keys = list(OBERBEGRIFFE)
    genre_ix = {k: n for n, k in enumerate(genre_keys)}

    bands: list[str] = []
    band_ix: dict[str, int] = {}

    def band_nr(name: str) -> int:
        if name not in band_ix:
            band_ix[name] = len(bands)
            bands.append(name)
        return band_ix[name]

    verorten = Verorter(festivals, geo, verortung, gazetteer, plz)
    zeilen = []
    for f in festivals:
        lat, lon, land = verorten(f)
        zeilen.append([
            f["name"], iso(f["date_from"]), iso(f["date_to"]),
            f["city"].strip(), land, f["venue"],
            preis_eur(f["price"]), f["price"], f["website"],
            lat, lon,
            sorted(band_nr(b) for b in f["lineup"]),
            f["note"], 1 if f["cancelled"] else 0,
            [genre_ix[k] for k in oberbegriffe(f["genre"])],
            # Preis zum Verkaufsstart, sofern die Quelle ihn inzwischen
            # geändert hat - sonst leer
            f["price_start"],
        ])

    # Ortsverzeichnis für die Wohnortsuche. Die veröffentlichte Fassung darf
    # keine externen Dienste aufrufen, deshalb wird es mitgeliefert.
    orte = gazetteer or [[k.split("|")[0], v["lat"], v["lon"], ""]
                         for k, v in geo.items() if v and v.get("lat") is not None]

    # Kürzel und Zweitschreibweisen aus data/band_aliase.json. Der Scraper
    # vereinheitlicht sie in den Daten; die Suche braucht sie trotzdem, sonst
    # findet "TBS" nichts, obwohl der Act als The Butcher Sisters drinsteht.
    aliase = lies_json(DATA / "band_aliase.json", {})
    alias_paare = [[kurz, band_ix[voll]] for kurz, voll in aliase.items()
                   if voll in band_ix and kurz.casefold() != voll.casefold()]

    payload = {
        # mit Uhrzeit, damit auf der Seite steht, wie frisch die Daten sind
        "generated": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M%z"),
        "bands": bands,
        "bandAlias": alias_paare,
        "genres": genre_keys,
        "festivals": zeilen,
        "places": [[n, round(la, 3), round(lo, 3), cc] for n, la, lo, cc in orte],
        # Damit die Seite "1012 NL" (Land) von "1012 AB" (niederländischer
        # Postleitzahlteil) unterscheiden kann - weltweit, sonst gilt "US"
        # als Ortsname.
        "laender": sorted(ISO_CODES),
        # Kürzel → Erdteil, für die Einordnung auf der Karte und in der Liste
        "kontinente": {c: k for c, k in sorted(KONTINENT.items()) if k},
        "plz": [[c, o, round(la, 3), round(lo, 3), cc] for c, o, la, lo, cc in plz],
        "world": lies_json(DATA / "welt_grob.json", []),
        "worldFine": lies_json(DATA / "welt_fein.json", []),
        # Ausschnitt, für den feine Umrisse vorliegen: lon0, lon1, lat0, lat1
        "fineBox": [EUROPA_RAHMEN[2], EUROPA_RAHMEN[3],
                    EUROPA_RAHMEN[0], EUROPA_RAHMEN[1]],
        # Ausschnitt der Karte ohne Wohnort: lat0, lat1, lon0, lon1
        "dataBox": datenrahmen(zeilen),
        "maxDistanceKm": max_entfernung_km(zeilen, plz),
        "maxPriceEur": max_preis_eur(zeilen),
        "minDate": frueheste_monatsgrenze(zeilen),
        # Preisgrenzen darf man in seiner eigenen Währung eingeben. Verglichen
        # wird intern immer in Euro, deshalb reisen die Kurse mit - und die
        # Zuordnung, welches Land welche Währung führt.
        "kurse": {w: k for w, k in sorted(KURSE.items()) if w != "€"},
        "waehrungLand": dict(sorted(WAEHRUNG_LAND.items())),
    }
    pruefe_zeilen(zeilen, bands, genre_keys)
    # Das große Ortsverzeichnis kommt in eine eigene Datei: Wer eine
    # Postleitzahl aus DE/AT/CH oder eine größere Stadt eingibt, braucht es
    # nie - die Seite lädt es erst nach, wenn die kleine Liste nichts hergibt.
    europa = verortung.get("orte") or gazetteer
    plz_europa = verortung.get("plz_nachladen") or []
    orte_ziel = SITE / "orte.js"
    orte_ziel.write_text(
        "window.ORTE_WELT = " + json.dumps({
            "orte": [[n, round(la, 3), round(lo, 3), cc] for n, la, lo, cc in europa],
            "plz": [[c, o, round(la, 3), round(lo, 3), cc]
                    for c, o, la, lo, cc in plz_europa],
        }, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8")
    print(f"{orte_ziel}  ({orte_ziel.stat().st_size / 1e6:.1f} MB zum Nachladen: "
          f"{len(europa)} Orte, {len(plz_europa)} Postleitzahlen)")
    if not plz_europa:
        # Ohne verortung.json bleibt nur das mitgelieferte Verzeichnis: Wohnorte
        # in DE/AT/CH gehen weiter, ausländische Postleitzahlen nicht mehr.
        print("  ! verortung.json fehlt - keine ausländischen Postleitzahlen",
              file=sys.stderr)

    ziel = SITE / "data.js"
    ziel.write_text(als_javascript(payload), encoding="utf-8")

    mit_preis = sum(1 for z in zeilen if z[EURO] is not None)
    mit_genre = sum(1 for z in zeilen if z[GENRES])
    print(f"{ziel}  ({ziel.stat().st_size / 1e6:.1f} MB)")
    print(f"  Koordinaten aus Postleitzahl: {verorten.aus_plz}, aus dem Geo-Cache: "
          f"{verorten.gefunden - verorten.aus_plz - verorten.aus_ort - verorten.aus_quelle}"
          f", aus dem Ortsverzeichnis: {verorten.aus_ort}, "
          f"aus der Quellseite: {verorten.aus_quelle}")
    print(f"  Festivals {len(zeilen)} | mit Koordinaten {verorten.gefunden} | "
          f"mit Preis in EUR {mit_preis} | Acts {len(bands)} | Orte {len(orte)} | "
          f"PLZ {len(plz)}")
    print(f"  Genre-Oberbegriffe {len(genre_keys)} | Festivals zugeordnet {mit_genre}"
          f" | Bandkürzel {len(alias_paare)}")
    print(f"  Reglergrenzen: Umkreis bis {payload['maxDistanceKm']} km "
          f"(ab {REF_PLZ}), Preis bis {payload['maxPriceEur']} EUR, "
          f"Kalender ab {payload['minDate'] or 'unbegrenzt'}")


if __name__ == "__main__":
    main()
