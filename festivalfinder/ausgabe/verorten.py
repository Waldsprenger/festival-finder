"""Zu jedem Festival eine Koordinate — in vier Rängen.

1. **Postleitzahl**: trifft den Zustellbereich und ist damit am genauesten. Die
   große Tabelle deckt 36 Länder ab; ohne sie bleibt es bei DE/AT/CH.
2. **Ortsname im Geo-Cache** (Nominatim), sofern schon einmal gefragt.
3. **Ortsname im mitgebauten Ortsverzeichnis** — für alles, was der Cache noch
   nicht kennt. Das erspart die Nachfrage bei einem fremden Dienst.
4. **Der Punkt aus dem Datenblatt der Quellseite**, aber nur, wenn er im Rahmen
   seines Landes liegt: Bei 37 Einträgen lag er im falschen Land, Lugano
   landete in Buenos Aires, Basel in Berlin.

Warum der Cache vor dem Ortsverzeichnis steht: Bei mehrdeutigen Namen wählen
beide verschieden — „Bernau" gibt es dreimal in Deutschland. Keiner hat
nachweislich recht, deshalb bleibt es bei der Antwort, die schon in den Daten
steht, statt bestehende Koordinaten ohne Grund zu verschieben.
"""

from ..kern.festival import Festival
from ..kern.orte import land_code
from ..kern.text import fold


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


def platzhalter(festivals: list[Festival]) -> set[tuple[float, float]]:
    """Koordinaten, die für mehrere verschiedene Orte herhalten müssen.

    Die Quelle setzt bei unbekanntem Ort gern den Landesmittelpunkt ein —
    51.5/10.5 steht dreizehnmal da, quer durch Deutschland und die Schweiz. Ein
    echter Veranstaltungsort taucht zwar auch mehrfach auf, dann aber immer mit
    demselben Ortsnamen.
    """
    orte: dict[tuple[float, float], set[str]] = {}
    for f in festivals:
        if f.lat is None:
            continue
        orte.setdefault((round(f.lat, 4), round(f.lon, 4)), set()).add(
            (f.stadt or "").casefold())
    return {k for k, v in orte.items() if len(v) >= 3}


class Verorter:
    """Findet zu jedem Festival eine Koordinate und zählt mit, woher sie kam."""

    def __init__(self, festivals: list[Festival], geo: dict, verortung: dict,
                 gazetteer: list, plz: list):
        self.aus_plz = self.aus_ort = self.aus_quelle = self.gefunden = 0

        self._plz_tabellen(verortung.get("plz") or
                           [[c, la, lo, cc] for c, _o, la, lo, cc in plz])
        self._geo_tabellen(geo)

        # Ortsverzeichnis: gefaltete Namen, weil GeoNames „Zürich" schreibt und
        # die Quellen mal „Zurich", mal „Zuerich".
        orte = verortung.get("orte") or gazetteer
        self.nach_ort: dict[tuple[str, str], tuple] = {}
        for name, lat, lon, cc in orte:
            self.nach_ort.setdefault((fold(name), cc), (lat, lon))

        self.rahmen = laender_rahmen(orte)
        self.verdaechtig = platzhalter(festivals)

    def _plz_tabellen(self, tabelle) -> None:
        """Postleitzahl → Koordinate, einmal mit Land und einmal ohne.

        Der zweite Index fängt Einträge ohne Landesangabe ab, ohne dafür die
        ganze Tabelle zu durchlaufen; mehrdeutige Codes fallen dabei weg.
        """
        self.nach_plz: dict[tuple[str, str], tuple] = {}
        self.nur_plz: dict[str, tuple] = {}
        mehrdeutig: set[str] = set()
        for code, lat, lon, cc in tabelle:
            self.nach_plz.setdefault((code, cc), (lat, lon))
            if code in self.nur_plz and self.nur_plz[code][2] != cc:
                mehrdeutig.add(code)
            self.nur_plz.setdefault(code, (lat, lon, cc))
        for code in mehrdeutig:
            self.nur_plz.pop(code, None)

    def _geo_tabellen(self, geo: dict) -> None:
        """Der Geo-Cache liegt unter der ursprünglichen Landesschreibweise.

        „Wacken|Deutschland" — die Festivals tragen inzwischen das Kürzel. Ein
        normalisierter Index erspart das erneute Geokodieren.
        """
        self.cache_mit_land: dict[tuple[str, str], dict] = {}
        self.cache_ohne_land: dict[str, tuple[dict, str]] = {}
        for schluessel, wert in geo.items():
            if not wert or wert.get("lat") is None:
                continue
            ort, _, land = schluessel.partition("|")
            code = land_code(land)
            self.cache_mit_land.setdefault((ort.strip().casefold(), code), wert)
            # Fehlt in der Quelle die Landesangabe, liefert sie der Geokodierer
            # als letztes Glied seiner Adresse mit („..., Deutschland").
            if not code:
                code = land_code((wert.get("display") or "").rsplit(",", 1)[-1])
            self.cache_ohne_land.setdefault(ort.strip().casefold(), (wert, code))

    def __call__(self, f: Festival) -> tuple[float | None, float | None, str]:
        """Koordinate und (gegebenenfalls ergänztes) Land eines Festivals."""
        stadt, land = f.stadt.strip(), f.land.strip()
        code = (f.plz or "").strip().replace(" ", "")

        treffer = self.nach_plz.get((code, land)) if code else None
        if treffer is None and code and code in self.nur_plz:
            # Land unbekannt oder abweichend notiert: eindeutige PLZ genügt
            lat, lon, cc = self.nur_plz[code]
            treffer, land = (lat, lon), land or cc
        if treffer:
            self.aus_plz += 1
            self.gefunden += 1
            return treffer[0], treffer[1], land

        # Zuerst der genaue Treffer aus Ort und Land; fehlt die Landesangabe,
        # zählt der Ortstreffer samt nachgetragenem Kürzel.
        g = self.cache_mit_land.get((stadt.casefold(), land)) if land else None
        if g is None and stadt:
            if (gefunden := self.cache_ohne_land.get(stadt.casefold())):
                g, ergaenzt = gefunden
                land = land or ergaenzt
        if g and g.get("lat") is not None:
            self.gefunden += 1
            return g["lat"], g["lon"], land

        treffer = self.nach_ort.get((fold(stadt), land)) if stadt and land else None
        if treffer:
            self.aus_ort += 1
            self.gefunden += 1
            return treffer[0], treffer[1], land

        lat, lon = self.quellkoordinate(f, land)
        if lat is not None:
            self.aus_quelle += 1
            self.gefunden += 1
        return lat, lon, land

    def quellkoordinate(self, f: Festival, land: str):
        """Koordinate der Quellseite, sofern sie zum Land passt."""
        lat, lon = f.lat, f.lon
        if lat is None or lon is None:
            return None, None
        if (round(lat, 4), round(lon, 4)) in self.verdaechtig:
            return None, None
        r = self.rahmen.get(land)
        if r and not (r[0] - 1 <= lat <= r[1] + 1 and r[2] - 1 <= lon <= r[3] + 1):
            return None, None
        return lat, lon

    @property
    def aus_cache(self) -> int:
        return self.gefunden - self.aus_plz - self.aus_ort - self.aus_quelle
