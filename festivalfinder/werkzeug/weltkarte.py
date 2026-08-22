"""Vereinfachte Weltkarten-Umrisse für die Kartenanzeige.

Kartenkacheln fremder Server sind in der veröffentlichten Fassung durch die
Sicherheitsrichtlinie blockiert. Die Karte wird deshalb aus mitgelieferten
Vektorgrenzen selbst gezeichnet.

Zwei Auflösungen: In der Weltansicht kostet jeder Punkt Zeichenzeit, in der
Nahansicht fiele jede Vereinfachung als Kante auf.

Quelle: Natural Earth (gemeinfrei), Auflösung 1:50 Mio.
"""

import json

from ..kern.orte import FEINRAHMEN
from ..netz import Abrufer
from ..pfade import CACHE, DATA, schreib_json

ORDNER = CACHE / "naturalearth"
BASIS = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
         "geojson/")
DATEI_GROB = "ne_110m_admin_0_countries.geojson"   # ganze Welt, wenig Punkte
DATEI_FEIN = "ne_50m_admin_0_countries.geojson"    # für die Nahansicht

#: Der Ausschnitt der feinen Umrisse, als (lon0, lon1) und (lat0, lat1)
FEIN_LON = (FEINRAHMEN[2], FEINRAHMEN[3])
FEIN_LAT = (FEINRAHMEN[0], FEINRAHMEN[1])

# Die ganze Welt: Beim Herauszoomen und Verschieben soll die Karte nicht an
# einer gedachten Kante abreißen. Die Antarktis bleibt außen vor, sie füllt in
# dieser Projektion nur den unteren Rand.
LAT_MIN = -60.0

GENAUIGKEIT = 2        # ~1 km, für Umkreise ab 10 km ausreichend
MIN_RING = 5           # Ringe mit weniger Punkten tragen nichts bei
MIN_UMFANG = 0.35      # Grad; verwirft Kleinstinseln, die als Punkt verschwinden


def laden(netz: Abrufer, datei: str) -> dict:
    ziel = ORDNER / datei
    netz.datei_holen(BASIS + datei, ziel, datei)
    return json.loads(ziel.read_text(encoding="utf-8"))


def ring_saeubern(ring: list, kasten: bool = False) -> list | None:
    """Runden, entdoppeln, Kleinstinseln verwerfen; None, wenn nichts bleibt."""
    raus: list[list[float]] = []
    letzter = None
    drin = not kasten
    for lon, lat in ring:
        if lat < LAT_MIN:
            continue
        if kasten and FEIN_LON[0] <= lon <= FEIN_LON[1] \
                and FEIN_LAT[0] <= lat <= FEIN_LAT[1]:
            drin = True
        p = [round(lon, GENAUIGKEIT), round(lat, GENAUIGKEIT)]
        if p == letzter:
            continue
        raus.append(p)
        letzter = p
    if len(raus) < MIN_RING or not drin:
        return None
    lons = [p[0] for p in raus]
    lats = [p[1] for p in raus]
    if (max(lons) - min(lons)) + (max(lats) - min(lats)) < MIN_UMFANG:
        return None
    return raus


def ringe_von(geom: dict):
    if geom["type"] == "Polygon":
        yield from geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield from poly


def sammeln(netz: Abrufer, datei: str, kasten: bool) -> list:
    ringe = []
    for feat in laden(netz, datei)["features"]:
        geom = feat.get("geometry")
        if not geom:
            continue
        for ring in ringe_von(geom):
            if (sauber := ring_saeubern(ring, kasten)):
                ringe.append(sauber)
    # größte Landmassen zuerst — beim Zeichnen fällt Feinzeug so nicht auf
    ringe.sort(key=len, reverse=True)
    return ringe


def bauen(netz: Abrufer) -> dict:
    zahlen = {}
    for datei, kasten, name, was in (
            (DATEI_GROB, False, "welt_grob.json", "Welt, grob"),
            (DATEI_FEIN, True, "welt_fein.json", "Ausschnitt, fein")):
        ringe = sammeln(netz, datei, kasten)
        ziel = DATA / name
        schreib_json(ziel, ringe, kompakt=True)
        zahlen[name] = {"was": was, "ringe": len(ringe),
                        "punkte": sum(len(r) for r in ringe),
                        "mb": ziel.stat().st_size / 1e6}
    return zahlen
