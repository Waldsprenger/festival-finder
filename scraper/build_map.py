"""Erzeugt vereinfachte Weltkarten-Umrisse fuer die Kartenanzeige.

Kartenkacheln von fremden Servern sind in der veroeffentlichten Fassung durch
die Sicherheitsrichtlinie blockiert. Die Karte wird deshalb aus mitgelieferten
Vektorgrenzen selbst gezeichnet.

Quelle: Natural Earth (gemeinfrei), Aufloesung 1:50 Mio.
Ergebnis: data/welt_grob.json (ganze Welt) und data/welt_fein.json
(Europa, fuer die Nahansicht) -> [[[lon, lat], ...], ...]  (Polygonringe)
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "cache" / "naturalearth"
CACHE.mkdir(parents=True, exist_ok=True)
OUT_GROB = BASE / "data" / "welt_grob.json"
OUT_FEIN = BASE / "data" / "welt_fein.json"

BASIS = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
         "geojson/")
DATEI_GROB = "ne_110m_admin_0_countries.geojson"   # ganze Welt, wenig Punkte
DATEI_FEIN = "ne_50m_admin_0_countries.geojson"    # Europa, fuer die Nahansicht

# Ausschnitt der feinen Umrisse
FEIN_LON = (-32.0, 46.0)
FEIN_LAT = (27.0, 72.0)

# Die ganze Welt: Beim Herauszoomen und Verschieben soll die Karte nicht an
# einer gedachten Kante abreissen. Antarktis bleibt aussen vor, sie fuellt in
# dieser Projektion nur den unteren Rand.
LAT_MIN = -60.0

PRECISION = 2          # ~1 km, fuer Umkreise ab 10 km ausreichend
MIN_RING = 5           # Ringe mit weniger Punkten tragen nichts bei
MIN_UMFANG = 0.35      # Grad; verwirft Kleinstinseln, die als Punkt verschwinden


def load(datei: str) -> dict:
    local = CACHE / datei
    if not local.exists():
        print(f"  lade {datei} …", flush=True)
        r = requests.get(BASIS + datei, timeout=300)
        r.raise_for_status()
        local.write_bytes(r.content)
    return json.loads(local.read_text(encoding="utf-8"))


def clean_ring(ring: list, box: tuple | None = None) -> list | None:
    out = []
    last = None
    drin = box is None
    for lon, lat in ring:
        if lat < LAT_MIN:
            continue
        if box and FEIN_LON[0] <= lon <= FEIN_LON[1] and FEIN_LAT[0] <= lat <= FEIN_LAT[1]:
            drin = True
        p = [round(lon, PRECISION), round(lat, PRECISION)]
        if p == last:
            continue
        out.append(p)
        last = p
    if len(out) < MIN_RING or not drin:
        return None
    lons = [p[0] for p in out]
    lats = [p[1] for p in out]
    if (max(lons) - min(lons)) + (max(lats) - min(lats)) < MIN_UMFANG:
        return None
    return out


def rings_of(geom: dict):
    if geom["type"] == "Polygon":
        yield from geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield from poly


def sammeln(datei: str, box: tuple | None) -> list:
    rings = []
    for feat in load(datei)["features"]:
        geom = feat.get("geometry")
        if not geom:
            continue
        for ring in rings_of(geom):
            cleaned = clean_ring(ring, box)
            if cleaned:
                rings.append(cleaned)
    # groesste Landmassen zuerst - beim Zeichnen faellt Feinzeug so nicht auf
    rings.sort(key=len, reverse=True)
    return rings


def main() -> None:
    # Zwei Aufloesungen: In der Weltansicht kostet jeder Punkt Zeichenzeit,
    # in der Nahansicht faellt jede Vereinfachung als Kante auf.
    for datei, box, ziel, was in ((DATEI_GROB, None, OUT_GROB, "Welt, grob"),
                                  (DATEI_FEIN, (FEIN_LON, FEIN_LAT), OUT_FEIN, "Europa, fein")):
        rings = sammeln(datei, box)
        ziel.write_text(json.dumps(rings, separators=(",", ":")), encoding="utf-8")
        pts = sum(len(r) for r in rings)
        print(f"{ziel.name:<16} {was:<14} {ziel.stat().st_size / 1e6:>5.2f} MB, "
              f"{len(rings):>5} Ringe, {pts:>7} Punkte")


if __name__ == "__main__":
    main()
