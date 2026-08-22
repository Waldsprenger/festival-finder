"""Alles, was die Webseite braucht, in einer JS-Datei.

Festivals als Zahlenreihen, Bandnamen und Genres als Listen, dazu das
Ortsverzeichnis und die Kartengrenzen. Die Seite läuft damit auch per
Doppelklick (file://), wo der Browser `fetch()` auf lokale Dateien blockiert.

Das große Ortsverzeichnis kommt in eine eigene Datei: Wer eine Postleitzahl aus
DE/AT/CH oder eine größere Stadt eingibt, braucht es nie — die Seite lädt es
erst nach, wenn die kleine Liste nichts hergibt.
"""

import json
import math
import sys
from datetime import datetime

from ..kern import zeit
from ..kern.festival import Festival
from ..kern.genres import OBERBEGRIFFE, oberbegriffe
from ..kern.geld import KURSE, WAEHRUNG_LAND, in_euro
from ..kern.orte import FEINRAHMEN, ISO_CODES, KONTINENT
from ..kern.text import REGELN
from ..pfade import DATA, SITE, lies_json, schreib_text
from .verorten import Verorter

#: Spalten einer Festivalzeile — dieselbe Reihenfolge steht in site/js/daten.js
NAME, VON, BIS, ORT, LAND, VENUE, EURO, PREIS_TEXT, WEB, LAT, LON, \
    LINEUP, HINWEIS, ABGESAGT, GENRES, PREIS_START = range(16)

#: Bezugspunkt für die Obergrenze der Entfernungsangabe
REF_PLZ = "97209"


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
    """
    punkte = [(z[LAT], z[LON]) for z in zeilen if z[LAT] is not None]
    if not punkte:
        return list(FEINRAHMEN)
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


def pruefe(zeilen: list, bands: list, genres: list) -> None:
    """Die Zahlenreihen prüfen, bevor sie ausgeliefert werden.

    Die Webseite liest jede Zeile über feste Spaltennummern und jede Band über
    ihren Index. Stimmt daran etwas nicht, bleibt die Seite leer — und zwar
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


def als_javascript(name: str, payload: dict) -> str:
    """Die Daten als JS-Datei — der Inhalt bleibt dabei JSON.

    `window.DATA = {…}` müsste der Browser als Quelltext lesen; über JSON.parse
    geht dasselbe rund doppelt so schnell (gemessen 64 statt 137 ms für 6 MB).
    Die JSON-Zeichenkette steht dafür in einfachen Anführungszeichen, sodass die
    vielen doppelten aus dem JSON unangetastet bleiben.
    """
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    text = (text.replace("\\", "\\\\").replace("'", "\\'")
                # In der gebündelten Einzelseite steht das Ganze in einem
                # <script>; ein „</" im Text würde es sonst beenden.
                .replace("</", "<\\/")
                # Zeilentrenner sind in JSON erlaubt, in JS-Zeichenketten nicht
                .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return f"window.{name} = JSON.parse('{text}');\n"


def bauen(festivals: list[Festival]) -> dict:
    """site/data.js und site/orte.js schreiben; gibt die Kennzahlen zurück."""
    geo = lies_json(DATA / "geo.json", {})
    plz = lies_json(DATA / "plz.json", [])
    gazetteer = lies_json(DATA / "gazetteer.json", [])
    # Die große Verortungstabelle wird nicht mitversioniert; fehlt sie, reichen
    # die mitgelieferten Verzeichnisse (dann eben nur DE/AT/CH bei den PLZ).
    verortung = lies_json(DATA / "verortung.json", {})

    # Oberbegriffe als Spaltennummern — die Namen stehen auf der Seite in der
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
            f.name, zeit.iso(f.von), zeit.iso(f.bis),
            f.stadt.strip(), land, f.ort,
            in_euro(f.preis), f.preis, f.webseite,
            lat, lon,
            sorted(band_nr(b) for b in f.lineup),
            f.hinweis, 1 if f.abgesagt else 0,
            [genre_ix[k] for k in oberbegriffe(f.genre)],
            f.preis_start,
        ])

    # Ortsverzeichnis für die Wohnortsuche. Die veröffentlichte Fassung darf
    # keine externen Dienste aufrufen, deshalb wird es mitgeliefert.
    orte = gazetteer or [[k.split("|")[0], v["lat"], v["lon"], ""]
                         for k, v in geo.items() if v and v.get("lat") is not None]

    # Kürzel und Zweitschreibweisen. Der Sammler vereinheitlicht sie in den
    # Daten; die Suche braucht sie trotzdem, sonst findet „TBS" nichts, obwohl
    # der Act als The Butcher Sisters drinsteht.
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
        # Damit die Seite „1012 NL" (Land) von „1012 AB" (niederländischer
        # Postleitzahlteil) unterscheiden kann — weltweit, sonst gilt „US" als
        # Ortsname.
        "laender": sorted(ISO_CODES),
        # Kürzel → Erdteil, für die Einordnung auf der Karte und in der Liste
        "kontinente": {c: k for c, k in sorted(KONTINENT.items()) if k},
        "plz": [[c, o, round(la, 3), round(lo, 3), cc] for c, o, la, lo, cc in plz],
        "world": lies_json(DATA / "welt_grob.json", []),
        "worldFine": lies_json(DATA / "welt_fein.json", []),
        # Ausschnitt, für den feine Umrisse vorliegen: lon0, lon1, lat0, lat1
        "fineBox": [FEINRAHMEN[2], FEINRAHMEN[3], FEINRAHMEN[0], FEINRAHMEN[1]],
        # Ausschnitt der Karte ohne Wohnort: lat0, lat1, lon0, lon1
        "dataBox": datenrahmen(zeilen),
        "maxDistanceKm": max_entfernung_km(zeilen, plz),
        "maxPriceEur": max_preis_eur(zeilen),
        "minDate": frueheste_monatsgrenze(zeilen),
        # Preisgrenzen darf man in seiner eigenen Währung eingeben. Verglichen
        # wird intern in Euro, deshalb reisen die Kurse mit — und die Zuordnung,
        # welches Land welche Währung führt.
        "kurse": {w: k for w, k in sorted(KURSE.items()) if w != "€"},
        "waehrungLand": dict(sorted(WAEHRUNG_LAND.items())),
        # Die Faltungsregeln der Namenssuche. Sie stehen in data/faltung.json
        # und reisen mit, damit Browser und Sammler nicht auseinanderlaufen.
        "faltung": REGELN,
    }
    pruefe(zeilen, bands, genre_keys)

    welt_orte = verortung.get("orte") or gazetteer
    welt_plz = verortung.get("plz_nachladen") or []
    schreib_text(SITE / "orte.js", als_javascript("ORTE_WELT", {
        "orte": [[n, round(la, 3), round(lo, 3), cc] for n, la, lo, cc in welt_orte],
        "plz": [[c, o, round(la, 3), round(lo, 3), cc] for c, o, la, lo, cc in welt_plz],
    }))
    if not welt_plz:
        # Ohne verortung.json bleibt nur das mitgelieferte Verzeichnis:
        # Wohnorte in DE/AT/CH gehen weiter, ausländische Postleitzahlen nicht.
        print("  ! verortung.json fehlt - keine ausländischen Postleitzahlen",
              file=sys.stderr)

    schreib_text(SITE / "data.js", als_javascript("DATA", payload))

    return {
        "festivals": len(zeilen),
        "mit_koordinaten": verorten.gefunden,
        "aus_plz": verorten.aus_plz,
        "aus_cache": verorten.aus_cache,
        "aus_ortsverzeichnis": verorten.aus_ort,
        "aus_quelle": verorten.aus_quelle,
        "mit_preis": sum(1 for z in zeilen if z[EURO] is not None),
        "mit_genre": sum(1 for z in zeilen if z[GENRES]),
        "acts": len(bands),
        "orte": len(orte),
        "plz": len(plz),
        "welt_orte": len(welt_orte),
        "welt_plz": len(welt_plz),
        "bandkuerzel": len(alias_paare),
        "max_km": payload["maxDistanceKm"],
        "max_preis": payload["maxPriceEur"],
        "ab_datum": payload["minDate"],
        "data_js_mb": (SITE / "data.js").stat().st_size / 1e6,
        "orte_js_mb": (SITE / "orte.js").stat().st_size / 1e6,
    }
