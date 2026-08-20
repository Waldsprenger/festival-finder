"""Macht die Seite installierbar (Progressive Web App).

Erzeugt Manifest, App-Symbole und einen Service Worker. Damit lässt sich die
Seite unter Android und iOS auf den Startbildschirm legen und startet dann
ohne Browserleiste; die Daten liegen anschliessend offline vor.

Wirksam wird das nur bei eigener Auslieferung über HTTPS, also in der
GitHub-Pages-Fassung. In der eingebetteten Artifact-Fassung ist die
Registrierung eines Service Workers durch die Sicherheitsrichtlinie gesperrt.
"""

from __future__ import annotations

import json

from PIL import Image, ImageDraw

from gemeinsam import SITE

ICONS = SITE / "icons"
ICONS.mkdir(parents=True, exist_ok=True)

ROT = (226, 35, 26)
GELB = (255, 183, 3)
DUNKEL = (11, 11, 13)

GROESSEN = [192, 512]


def symbol(px: int, maskable: bool) -> Image.Image:
    """Blitz auf dunklem Grund - dasselbe Zeichen wie im Seitenkopf."""
    bild = Image.new("RGBA", (px, px), DUNKEL + (255,))
    d = ImageDraw.Draw(bild)

    # Bei maskierbaren Symbolen schneiden die Systeme aussen rund 10 % weg
    rand = px * 0.18 if maskable else px * 0.10
    innen = px - 2 * rand

    d.ellipse([rand * 0.55, rand * 0.55, px - rand * 0.55, px - rand * 0.55],
              outline=ROT, width=max(2, int(px * 0.035)))

    # Blitz als Polygon, Koordinaten in Anteilen der Innenflaeche
    punkte = [(0.56, 0.06), (0.24, 0.54), (0.45, 0.54), (0.36, 0.94),
              (0.74, 0.42), (0.52, 0.42), (0.62, 0.06)]
    d.polygon([(rand + x * innen, rand + y * innen) for x, y in punkte], fill=GELB)
    return bild


def main() -> None:
    dateien = []
    for px in GROESSEN:
        for maskable in (False, True):
            name = f"icon-{px}{'-maskable' if maskable else ''}.png"
            symbol(px, maskable).save(ICONS / name, optimize=True)
            dateien.append({
                "src": f"icons/{name}",
                "sizes": f"{px}x{px}",
                "type": "image/png",
                "purpose": "maskable" if maskable else "any",
            })

    manifest = {
        "name": "Festival Finder — Lineup-Abgleich für Europa",
        "short_name": "Festival Finder",
        "description": "Festivals in Europa nach Wohnort, Umkreis, Preis, "
                       "Zeitraum und Lieblingsbands finden.",
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#0b0b0d",
        "theme_color": "#e2231a",
        "lang": "de",
        "categories": ["music", "travel", "events"],
        "icons": dateien,
    }
    (SITE / "manifest.webmanifest").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Der Service Worker legt die Seite beim ersten Besuch ab und liefert sie
    # danach auch ohne Netz aus. Die Daten kommen aus dem Netz, sobald es geht,
    # sonst aus dem Speicher.
    sw = """/* erzeugt von build_pwa.py */
const CACHE = 'festival-finder-v__VERSION__';
const DATEIEN = ['./', './index.html', './style.css', './fonts.css',
                 './karte.js', './app.js', './i18n.js', './config.js', './data.js',
                 './impressum.html', './datenschutz.html',
                 './manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(DATEIEN)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((k) => Promise.all(k.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

// Erst das Netz, damit neue Festivaldaten ankommen; ohne Netz der Speicher.
// Nur eigene Dateien: Ein Zaehlimpuls traegt bei jedem Aufruf eine neue Adresse
// und wuerde den Speicher sonst Aufruf fuer Aufruf fuellen.
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  if (new URL(e.request.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const kopie = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, kopie)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(e.request).then((t) => t || caches.match('./index.html')))
  );
});
"""
    stand = (SITE / "data.js").stat().st_mtime if (SITE / "data.js").exists() else 0
    (SITE / "sw.js").write_text(sw.replace("__VERSION__", str(int(stand))), encoding="utf-8")

    print(f"{SITE / 'manifest.webmanifest'}")
    print(f"{SITE / 'sw.js'}")
    for d in dateien:
        p = SITE / d["src"]
        print(f"  {d['src']:<28} {p.stat().st_size / 1024:>5.1f} KB  ({d['purpose']})")


if __name__ == "__main__":
    main()
