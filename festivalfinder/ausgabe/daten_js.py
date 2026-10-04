"""Was die Webseite braucht — in vier Dateien, nach Lebensdauer getrennt.

* `site/data.js` — die Festivals, Bands und Genres. Ändert sich mit jedem Lauf.
* `site/geo.js` — Ortsverzeichnis, Postleitzahlen und Kartenumrisse. Ändert
  sich fast nie und machte doch mehr als die Hälfte von `data.js` aus: Jeder
  Besucher lud nach jedem täglichen Lauf 5 MB Geodaten neu, die sich nicht
  geändert hatten. Jetzt trägt `data.js` nur die Kennung des Standes; die Seite
  holt `geo.js?v=<kennung>` nach dem ersten Bildaufbau, und Browser wie
  Service Worker behalten sie, bis sich die Kennung ändert.
* `site/orte.js` — das große Ortsverzeichnis samt Zweitnamen großer Städte
  („Warszawa", „東京"), nur bei Bedarf nachgeladen.
* `site/plz.js` — Postleitzahlen aus 117 Ländern, nur geladen, wenn jemand
  eine Postleitzahl außerhalb von DE/AT/CH eingibt.

Alle vier sind JS-Dateien statt JSON: Die Seite läuft so auch per Doppelklick
(file://), wo der Browser `fetch()` auf lokale Dateien blockiert.
"""

import hashlib
import json
import math
import sys
from datetime import date, datetime

from ..kern import zeit
from ..kern.festival import Festival
from ..kern.genres import OBERBEGRIFFE, oberbegriffe
from ..kern.geld import KURSE, WAEHRUNG_LAND, in_euro
from ..kern.orte import FEINRAHMEN, ISO_CODES
from ..kern.text import REGELN
from ..pfade import DATA, SITE, lies_json, schreib_text
from ..werkzeug import neuheiten
from .verorten import Verorter

#: Spalten einer Festivalzeile — dieselbe Reihenfolge steht in site/js/daten.js
NAME, VON, BIS, ORT, LAND, VENUE, EURO, PREIS_TEXT, WEB, LAT, LON, \
    LINEUP, HINWEIS, ABGESAGT, GENRES, PREIS_START = range(16)


def datenrahmen(zeilen: list) -> list[float]:
    """Das Rechteck um alle Festivals mit Koordinate: lat0, lat1, lon0, lon1.

    Es bestimmt den Kartenausschnitt, solange kein Wohnort eingetragen ist.
    Nach außen gerundet: round(-46.4137, 2) läge nördlich des südlichsten
    Punktes, und die Karte schnitte ihn ab.
    """
    punkte = [(z[LAT], z[LON]) for z in zeilen if z[LAT] is not None]
    if not punkte:
        return list(FEINRAHMEN)
    lats, lons = [p[0] for p in punkte], [p[1] for p in punkte]
    ab = lambda w: math.floor(w * 100) / 100      # noqa: E731
    auf = lambda w: math.ceil(w * 100) / 100      # noqa: E731
    return [ab(min(lats)), auf(max(lats)), ab(min(lons)), auf(max(lons))]


def frueheste_monatsgrenze(zeilen: list) -> str:
    """Erster Tag des Monats, in dem das früheste Festival beginnt — die
    Untergrenze des Kalenders."""
    termine = [z[VON] for z in zeilen if z[VON]]
    return min(termine)[:8] + "01" if termine else ""


def pruefe(zeilen: list, bands: list, genres: list) -> None:
    """Die Zahlenreihen prüfen, bevor sie ausgeliefert werden.

    Die Seite liest jede Zeile über feste Spaltennummern und jede Band über
    ihren Index. Stimmt daran etwas nicht, bleibt die Seite still leer — also
    lieber hier abbrechen: Dann behält die Veröffentlichung den letzten Stand.
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

    Über JSON.parse liest der Browser das rund doppelt so schnell wie ein
    Objektliteral (64 statt 137 ms für 6 MB). Die Zeichenkette steht in
    einfachen Anführungszeichen, damit die doppelten des JSON bleiben dürfen.
    """
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    text = (text.replace("\\", "\\\\").replace("'", "\\'")
                # In der Einzelseite steht das Ganze in einem <script>; ein
                # „</" im Text würde es beenden.
                .replace("</", "<\\/")
                # Zeilentrenner sind in JSON erlaubt, in JS-Zeichenketten nicht
                .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return f"window.{name} = JSON.parse('{text}');\n"


def schreiben_wenn_neu(name: str, inhalt: str) -> str:
    """Datei nur schreiben, wenn sich der Inhalt geändert hat; gibt die
    Kennung des Inhalts zurück. So bleibt eine unveränderte Datei auch
    dateisystemseitig dieselbe — und `?v=` zeigt auf denselben Stand."""
    kennung = hashlib.sha1(inhalt.encode("utf-8")).hexdigest()[:12]
    ziel = SITE / name
    if not ziel.exists() or ziel.read_text(encoding="utf-8") != inhalt:
        schreib_text(ziel, inhalt)
    return kennung


def neuigkeiten(festivals: list[Festival], band_nr: dict[str, int]) -> dict:
    """Seit wann wir was kennen — als Teil von `data.js`, nicht als eigene Datei.

    Die Angaben zeigen mit Zeilen- und Bandnummern in `data.js` hinein, die
    jeder Bau neu vergibt; zwei getrennte Dateien könnten aus zwei Läufen
    stammen. Nur, was es heute noch gibt. Die Daten sind Tagesnummern ab
    `beginn`: aus „2027-03-14" wird eine dreistellige Zahl.
    """
    zustand = neuheiten.lesen()
    if not (beginn := zustand["beginn"]):
        return {"beginn": "", "feste": [], "bands": []}
    tag0 = date.fromisoformat(beginn)
    nr = lambda datum: (date.fromisoformat(datum) - tag0).days   # noqa: E731

    feste, bands = [], []
    for n, f in enumerate(festivals):
        seit, dazu = neuheiten.zugaenge(zustand, f.kennung)
        if seit:
            feste.append([n, nr(seit)])
        for name, datum in sorted(dazu.items()):
            if (b := band_nr.get(name)) is not None:
                bands.append([n, b, nr(datum)])
    return {"beginn": beginn, "feste": feste, "bands": bands}


def _orte(liste) -> list:
    return [[n, round(la, 3), round(lo, 3), cc] for n, la, lo, cc in liste]


def _staatorte(liste) -> list:
    """Orte mit Bundesstaat: „Springfield", …, „IL"."""
    return [[n, round(la, 3), round(lo, 3), cc, staat] for n, la, lo, cc, staat in liste]


def _plz(liste) -> list:
    return [[c, o, round(la, 3), round(lo, 3), cc] for c, o, la, lo, cc in liste]


def bauen(festivals: list[Festival]) -> dict:
    """site/data.js, geo.js, orte.js und plz.js; gibt die Kennzahlen zurück."""
    geo = lies_json(DATA / "geo.json", {})
    plz = lies_json(DATA / "plz.json", [])
    gazetteer = lies_json(DATA / "gazetteer.json", [])
    # Die große Verortungstabelle wird nicht mitversioniert; fehlt sie,
    # reichen die mitgelieferten Verzeichnisse (dann nur DE/AT/CH bei den PLZ).
    verortung = lies_json(DATA / "verortung.json", {})
    wohnort = lies_json(DATA / "wohnort.json", {})

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
            f.name, zeit.iso(f.von), zeit.iso(f.bis), f.stadt.strip(), land, f.ort,
            in_euro(f.preis), f.preis, f.webseite, lat, lon,
            sorted(band_nr(b) for b in f.lineup),
            f.hinweis, 1 if f.abgesagt else 0,
            [genre_ix[k] for k in oberbegriffe(f.genre)],
            f.preis_start,
        ])
    pruefe(zeilen, bands, genre_keys)

    # Geodaten: Wohnortsuche und Karte. Die veröffentlichte Fassung darf keine
    # fremden Dienste aufrufen, deshalb liegen sie bei.
    orte = gazetteer or [[k.split("|")[0], v["lat"], v["lon"], ""]
                         for k, v in geo.items() if v and v.get("lat") is not None]
    geo_js = als_javascript("GEO", {
        "places": _orte(orte),
        "plz": _plz(plz),
        "world": lies_json(DATA / "welt_grob.json", []),
        "worldFine": lies_json(DATA / "welt_fein.json", []),
        # Ausschnitt, für den feine Umrisse vorliegen: lon0, lon1, lat0, lat1
        "fineBox": [FEINRAHMEN[2], FEINRAHMEN[3], FEINRAHMEN[0], FEINRAHMEN[1]],
        # Wie Postleitzahlen je Land aussehen („999-9999" → JP) und wo die
        # Bundesstaaten liegen — klein, und die Seite weiß damit, ob sie
        # plz.js überhaupt braucht.
        "plzFormen": wohnort.get("formen", {}),
        "verwaltung": wohnort.get("verwaltung", {}),
        "staatOrte": _staatorte(wohnort.get("staatorte_gross", [])),
    })
    welt_orte = wohnort.get("orte") or verortung.get("orte") or gazetteer
    welt_plz = wohnort.get("plz") or {}
    if not welt_plz:
        print("  ! wohnort.json fehlt - Postleitzahlen nur für DE/AT/CH",
              file=sys.stderr)
    orte_js = als_javascript("ORTE_WELT", {"orte": _orte(welt_orte),
                                           "zweitnamen": _orte(wohnort.get("zweitnamen", [])),
                                           "staatOrte": _staatorte(wohnort.get("staatorte", []))})
    plz_js = als_javascript("PLZ_WELT", welt_plz)

    # Kürzel und Zweitschreibweisen: In den Daten steht der ausgeschriebene
    # Name, die Suche braucht beide — sonst findet „TBS" nichts.
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
        # „1012 NL" (Land) von „1012 AB" (Postleitzahl) unterscheiden
        "laender": sorted(ISO_CODES),
        # Ausschnitt der Karte ohne Wohnort: lat0, lat1, lon0, lon1
        "dataBox": datenrahmen(zeilen),
        "minDate": frueheste_monatsgrenze(zeilen),
        # Preisgrenzen in der eigenen Währung; verglichen wird in Euro
        "kurse": {w: k for w, k in sorted(KURSE.items()) if w != "€"},
        "waehrungLand": dict(sorted(WAEHRUNG_LAND.items())),
        # Die Faltungsregeln der Namenssuche, dieselben wie im Sammler
        "faltung": REGELN,
        "neu": neuigkeiten(festivals, band_ix),
        # Welcher Stand der Geodaten zu diesen Daten gehört
        "versionen": {"geo": schreiben_wenn_neu("geo.js", geo_js),
                      "orte": schreiben_wenn_neu("orte.js", orte_js),
                      "plz": schreiben_wenn_neu("plz.js", plz_js)},
    }
    schreib_text(SITE / "data.js", als_javascript("DATA", payload))

    return {
        "festivals": len(zeilen),
        "neue_festivals": len(payload["neu"]["feste"]),
        "neue_bands": len(payload["neu"]["bands"]),
        "mit_koordinaten": verorten.gefunden,
        "aus_plz": verorten.aus_plz, "aus_cache": verorten.aus_cache,
        "aus_ortsverzeichnis": verorten.aus_ort, "aus_quelle": verorten.aus_quelle,
        "cache_verworfen": verorten.verworfen,
        "mit_preis": sum(1 for z in zeilen if z[EURO] is not None),
        "mit_genre": sum(1 for z in zeilen if z[GENRES]),
        "acts": len(bands), "orte": len(orte), "plz": len(plz),
        "welt_orte": len(welt_orte),
        "welt_plz": sum(len(v) for v in welt_plz.values()), "plz_laender": len(welt_plz),
        "bandkuerzel": len(alias_paare), "ab_datum": payload["minDate"],
        "versionen": payload["versionen"],
        "data_js_mb": (SITE / "data.js").stat().st_size / 1e6,
        "geo_js_mb": (SITE / "geo.js").stat().st_size / 1e6,
        "orte_js_mb": (SITE / "orte.js").stat().st_size / 1e6,
        "plz_js_mb": (SITE / "plz.js").stat().st_size / 1e6,
    }
