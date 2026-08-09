"""Erzeugt vereinfachte Laendergrenzen fuer die Kartenanzeige.

Kartenkacheln von fremden Servern sind in der veroeffentlichten Fassung durch
die Sicherheitsrichtlinie blockiert. Die Karte wird deshalb aus mitgelieferten
Vektorgrenzen selbst gezeichnet.

Quelle: Natural Earth (gemeinfrei), Aufloesung 1:50 Mio.
Ergebnis: data/europe.json -> [[[lon, lat], ...], ...]  (Polygonringe)
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "cache" / "naturalearth"
CACHE.mkdir(parents=True, exist_ok=True)
OUT = BASE / "data" / "europe.json"

URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
       "geojson/ne_50m_admin_0_countries.geojson")

# Kartenausschnitt: Europa inkl. Randbereiche
LON0, LON1 = -26.0, 46.0
LAT0, LAT1 = 33.0, 72.0

PRECISION = 2          # ~1 km, fuer Umkreise ab 10 km ausreichend
MIN_RING = 5           # Ringe mit weniger Punkten tragen nichts bei


def load() -> dict:
    local = CACHE / "ne_50m_admin_0_countries.geojson"
    if not local.exists():
        print("  lade Natural Earth …", flush=True)
        r = requests.get(URL, timeout=300)
        r.raise_for_status()
        local.write_bytes(r.content)
    return json.loads(local.read_text(encoding="utf-8"))


def clean_ring(ring: list) -> list | None:
    out = []
    last = None
    inside = False
    for lon, lat in ring:
        p = [round(lon, PRECISION), round(lat, PRECISION)]
        if p == last:
            continue
        if LON0 <= p[0] <= LON1 and LAT0 <= p[1] <= LAT1:
            inside = True
        out.append(p)
        last = p
    return out if inside and len(out) >= MIN_RING else None


def rings_of(geom: dict):
    if geom["type"] == "Polygon":
        yield from geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield from poly


def main() -> None:
    gj = load()
    rings = []
    for feat in gj["features"]:
        geom = feat.get("geometry")
        if not geom:
            continue
        # grober Vorfilter ueber die Bounding-Box des Landes
        for ring in rings_of(geom):
            cleaned = clean_ring(ring)
            if cleaned:
                rings.append(cleaned)

    rings.sort(key=len, reverse=True)
    OUT.write_text(json.dumps(rings, separators=(",", ":")), encoding="utf-8")
    pts = sum(len(r) for r in rings)
    print(f"{OUT}  ({OUT.stat().st_size / 1e6:.2f} MB, {len(rings)} Ringe, {pts} Punkte)")


if __name__ == "__main__":
    main()
