"""Macht die Seite installierbar (Progressive Web App).

Erzeugt Manifest, App-Symbole und einen Service Worker. Damit lässt sich die
Seite unter Android und iOS auf den Startbildschirm legen; sie startet dann
ohne Browserleiste, und die Daten liegen offline vor.

Wirksam wird das nur bei eigener Auslieferung über HTTPS, also in der
GitHub-Pages-Fassung. In der eingebetteten Einzelseiten-Fassung ist die
Registrierung eines Service Workers durch die Sicherheitsrichtlinie gesperrt.
"""

import json

from PIL import Image, ImageDraw

from ..pfade import SITE, schreib_text
from .seitenteile import vorrat

ICONS = SITE / "icons"

ROT = (226, 35, 26)
GELB = (255, 183, 3)
DUNKEL = (11, 11, 13)
GROESSEN = [192, 512]


def symbol(px: int, maskierbar: bool) -> Image.Image:
    """Blitz auf dunklem Grund — dasselbe Zeichen wie im Seitenkopf."""
    bild = Image.new("RGBA", (px, px), DUNKEL + (255,))
    d = ImageDraw.Draw(bild)

    # Bei maskierbaren Symbolen schneiden die Systeme außen rund 10 % weg
    rand = px * 0.18 if maskierbar else px * 0.10
    innen = px - 2 * rand

    d.ellipse([rand * 0.55, rand * 0.55, px - rand * 0.55, px - rand * 0.55],
              outline=ROT, width=max(2, int(px * 0.035)))

    # Blitz als Polygon, Koordinaten in Anteilen der Innenfläche
    punkte = [(0.56, 0.06), (0.24, 0.54), (0.45, 0.54), (0.36, 0.94),
              (0.74, 0.42), (0.52, 0.42), (0.62, 0.06)]
    d.polygon([(rand + x * innen, rand + y * innen) for x, y in punkte], fill=GELB)
    return bild


# Erst das Netz, damit neue Festivaldaten ankommen — aber mit Frist. Ohne sie
# hängt die Seite im schlechten Mobilfunknetz am leeren Bildschirm, bis der
# Versuch scheitert; mit ihr erscheint nach 2,5 Sekunden der gespeicherte
# Stand, während der Abruf im Hintergrund weiterläuft. Wie frisch die Daten
# sind, steht im Seitenfuß.
SW = """/* erzeugt von festivalfinder/ausgabe/pwa.py */
const CACHE = 'festival-finder-v__VERSION__';
const DATEIEN = __DATEIEN__;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(DATEIEN)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((k) => Promise.all(k.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

const FRIST = 2500;

async function ausliefern(anfrage) {
  const speicher = await caches.open(CACHE);
  const abgelegt = await speicher.match(anfrage);
  const ausDemNetz = fetch(anfrage).then((res) => {
    if (res && res.ok) speicher.put(anfrage, res.clone()).catch(() => {});
    return res;
  });

  if (!abgelegt) {
    return ausDemNetz.catch(() => speicher.match('./index.html'));
  }
  return Promise.race([
    ausDemNetz.catch(() => abgelegt),
    new Promise((fertig) => setTimeout(() => fertig(abgelegt), FRIST)),
  ]);
}

// Nur eigene Dateien: Ein Zaehlimpuls traegt bei jedem Aufruf eine neue
// Adresse und wuerde den Speicher sonst Aufruf fuer Aufruf fuellen.
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  if (new URL(e.request.url).origin !== self.location.origin) return;
  const antwort = ausliefern(e.request);
  // Der Hintergrundabruf soll auch dann zu Ende laufen, wenn die Frist gewann.
  e.waitUntil(antwort.catch(() => {}));
  e.respondWith(antwort);
});
"""


def bauen() -> dict:
    """Symbole, Manifest und Service Worker schreiben."""
    ICONS.mkdir(parents=True, exist_ok=True)
    dateien = []
    for px in GROESSEN:
        for maskierbar in (False, True):
            name = f"icon-{px}{'-maskable' if maskierbar else ''}.png"
            symbol(px, maskierbar).save(ICONS / name, optimize=True)
            dateien.append({
                "src": f"icons/{name}",
                "sizes": f"{px}x{px}",
                "type": "image/png",
                "purpose": "maskable" if maskierbar else "any",
            })

    manifest = {
        "name": "Festival Finder — Lineup-Abgleich weltweit",
        "short_name": "Festival Finder",
        "description": "Festivals weltweit finden: Wohnort, Zeitraum, "
                       "Entfernung, Preis, Bands, Genre.",
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
    schreib_text(SITE / "manifest.webmanifest",
                 json.dumps(manifest, ensure_ascii=False, indent=2))

    # Die Version folgt dem Datenstand: Ein neuer Bestand heißt neuer Speicher,
    # und die Besucher bekommen ihn beim übernächsten Aufruf.
    stand = (SITE / "data.js").stat().st_mtime if (SITE / "data.js").exists() else 0
    vorgehalten = vorrat()
    schreib_text(SITE / "sw.js",
                 SW.replace("__VERSION__", str(int(stand)))
                   .replace("__DATEIEN__", json.dumps(vorgehalten, indent=17)
                            .replace("\n" + " " * 17 + "]", "]")))
    return {"symbole": [d["src"] for d in dateien], "vorrat": vorgehalten}
