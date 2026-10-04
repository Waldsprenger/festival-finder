"""Macht die Seite installierbar (Progressive Web App).

Manifest, App-Symbole und Service Worker. Damit lässt sich die Seite unter
Android und iOS auf den Startbildschirm legen; sie startet dann ohne
Browserleiste, und die Daten liegen offline vor. Wirksam nur bei eigener
Auslieferung über HTTPS — in der eingebetteten Einzelseite sperrt die
Sicherheitsrichtlinie den Service Worker.

Die Symbole liegen versioniert in `site/icons/`; gezeichnet werden sie nur,
wenn eines fehlt. Pillow braucht deshalb nur, wer sie neu zeichnen will.
"""

import json

from ..pfade import SITE, schreib_text
from .seitenteile import vorrat

ICONS = SITE / "icons"
GROESSEN = [192, 512]

ROT = (226, 35, 26)
GELB = (255, 183, 3)
DUNKEL = (11, 11, 13)


def symbol(px: int, maskierbar: bool):
    """Blitz auf dunklem Grund — dasselbe Zeichen wie im Seitenkopf."""
    from PIL import Image, ImageDraw

    bild = Image.new("RGBA", (px, px), DUNKEL + (255,))
    d = ImageDraw.Draw(bild)
    # Bei maskierbaren Symbolen schneiden die Systeme außen rund 10 % weg
    rand = px * (0.18 if maskierbar else 0.10)
    innen = px - 2 * rand
    d.ellipse([rand * 0.55, rand * 0.55, px - rand * 0.55, px - rand * 0.55],
              outline=ROT, width=max(2, int(px * 0.035)))
    punkte = [(0.56, 0.06), (0.24, 0.54), (0.45, 0.54), (0.36, 0.94),
              (0.74, 0.42), (0.52, 0.42), (0.62, 0.06)]
    d.polygon([(rand + x * innen, rand + y * innen) for x, y in punkte], fill=GELB)
    return bild


def symbole(neu: bool = False) -> list[dict]:
    """Die Symbole fürs Manifest; gezeichnet wird nur, was fehlt (oder alle mit `neu`)."""
    ICONS.mkdir(parents=True, exist_ok=True)
    eintraege = []
    for px in GROESSEN:
        for maskierbar in (False, True):
            name = f"icon-{px}{'-maskable' if maskierbar else ''}.png"
            if neu or not (ICONS / name).exists():
                symbol(px, maskierbar).save(ICONS / name, optimize=True)
            eintraege.append({"src": f"icons/{name}", "sizes": f"{px}x{px}",
                              "type": "image/png",
                              "purpose": "maskable" if maskierbar else "any"})
    return eintraege


# Zwei Arten von Dateien, zwei Wege:
#
# * Mit Kennung (`geo.js?v=…`): Der Inhalt ändert sich nie, nur die Kennung.
#   Also aus dem Speicher, ohne Netz. Das sind die Geodaten — vorher lud jeder
#   Besucher sie nach jedem täglichen Lauf neu, weil der ganze Speicher am
#   Datenstand hing.
# * Ohne Kennung: erst das Netz, damit neue Festivaldaten ankommen, aber mit
#   Frist. Im schlechten Mobilfunknetz erscheint nach 2,5 Sekunden der
#   gespeicherte Stand, während der Abruf im Hintergrund weiterläuft.
#
# Der Service Worker selbst ändert sich nur, wenn sich die Dateiliste ändert —
# nicht mehr bei jedem Datenstand.
SW = """/* erzeugt von festivalfinder/ausgabe/pwa.py */
const CACHE = 'festival-finder';
const VORRAT = __VORRAT__;
const FRIST = 2500;
const versioniert = (url) => new URL(url, self.location).searchParams.has('v');

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then(async (c) => {
    for (const url of VORRAT) {
      if (versioniert(url) && await c.match(url)) continue;
      try { await c.add(url); } catch (_) { /* beim nächsten Besuch */ }
    }
  }).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  const behalten = new Set(VORRAT.map((u) => new URL(u, self.location).href));
  e.waitUntil((async () => {
    for (const name of await caches.keys()) if (name !== CACHE) await caches.delete(name);
    const c = await caches.open(CACHE);
    for (const anfrage of await c.keys()) {
      // Abgelöste Stände der versionierten Dateien räumen
      if (versioniert(anfrage.url) && !behalten.has(anfrage.url)) await c.delete(anfrage);
    }
    await self.clients.claim();
  })());
});

async function ausliefern(anfrage) {
  const speicher = await caches.open(CACHE);
  const abgelegt = await speicher.match(anfrage);
  if (abgelegt && versioniert(anfrage.url)) return abgelegt;
  const ausDemNetz = fetch(anfrage).then((res) => {
    if (res && res.ok) speicher.put(anfrage, res.clone()).catch(() => {});
    return res;
  });
  if (!abgelegt) return ausDemNetz.catch(() => speicher.match('./index.html'));
  return Promise.race([
    ausDemNetz.catch(() => abgelegt),
    new Promise((fertig) => setTimeout(() => fertig(abgelegt), FRIST)),
  ]);
}

// Nur eigene Dateien: Ein Zählimpuls trägt bei jedem Aufruf eine neue Adresse
// und würde den Speicher sonst Aufruf für Aufruf füllen.
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  if (new URL(e.request.url).origin !== self.location.origin) return;
  const antwort = ausliefern(e.request);
  e.waitUntil(antwort.catch(() => {}));   // Hintergrundabruf zu Ende laufen lassen
  e.respondWith(antwort);
});
"""


def bauen(versionen: dict[str, str] | None = None) -> dict:
    """Manifest und Service Worker schreiben, fehlende Symbole zeichnen."""
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
        "icons": symbole(),
    }
    schreib_text(SITE / "manifest.webmanifest",
                 json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    liste = vorrat()
    if versionen and versionen.get("geo"):
        liste.append(f"./geo.js?v={versionen['geo']}")
    schreib_text(SITE / "sw.js", SW.replace("__VORRAT__", json.dumps(liste, indent=1)))
    return {"vorrat": liste}
