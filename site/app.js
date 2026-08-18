/* Festival Finder — Filter, Bandauswahl, Trefferberechnung.
   Läuft ohne Server; die Daten liegen in data.js als window.DATA. */

(() => {
  'use strict';

  const D = window.DATA;
  const F = D.festivals;
  const BANDS = D.bands;
  // Schlüssel der Genre-Oberbegriffe; die Namen stehen übersetzt in i18n.js
  const GENRES = D.genres || [];

  // Spaltenindizes von data.js
  const NAME = 0, FROM = 1, TO = 2, CITY = 3, LAND = 4, VENUE = 5,
        EUR = 6, PRICE_RAW = 7, WEB = 8, LAT = 9, LON = 10, LINEUP = 11,
        GENRE = 12, NOTE = 13, CANCELLED = 14, GENRE_IDS = 15;

  const $ = (id) => document.getElementById(id);

  /* ---------------- Sprache ----------------
     Die Texte stehen in i18n.js. Fehlt eine Übersetzung, greift Deutsch;
     die Seite bleibt damit auch bei unvollständiger Sprachdatei benutzbar. */

  const I18N = window.I18N || { SPRACHEN: { de: 'Deutsch' }, TEXTE: {} };
  const SPEICHER = 'ff.sprache';

  function startSprache() {
    try {
      const gemerkt = localStorage.getItem(SPEICHER);
      if (gemerkt && I18N.SPRACHEN[gemerkt]) return gemerkt;
    } catch (_) { /* Speicher gesperrt - dann eben die Browsersprache */ }
    for (const wunsch of (navigator.languages || [navigator.language || 'de'])) {
      const kurz = String(wunsch).slice(0, 2).toLowerCase();
      if (I18N.SPRACHEN[kurz]) return kurz;
    }
    return 'de';
  }

  let sprache = startSprache();

  /** Übersetzt einen Schlüssel und ersetzt {platzhalter}. */
  function t(schluessel, werte) {
    const eintrag = I18N.TEXTE[schluessel];
    let text = eintrag ? (eintrag[sprache] ?? eintrag.de ?? '') : schluessel;
    if (werte) {
      for (const [k, v] of Object.entries(werte)) {
        text = text.split('{' + k + '}').join(String(v));
      }
    }
    return text;
  }

  /** Trägt alle ausgezeichneten Texte im Dokument neu ein. */
  function spracheAnwenden() {
    document.documentElement.lang = sprache;
    for (const el of document.querySelectorAll('[data-i18n]')) {
      el.textContent = t(el.dataset.i18n);
    }
    for (const el of document.querySelectorAll('[data-i18n-html]')) {
      el.innerHTML = t(el.dataset.i18nHtml);
    }
    for (const el of document.querySelectorAll('[data-i18n-title]')) {
      el.title = t(el.dataset.i18nTitle);
    }
    for (const el of document.querySelectorAll('[data-i18n-ph]')) {
      el.placeholder = t(el.dataset.i18nPh);
    }
    for (const el of document.querySelectorAll('[data-i18n-aria]')) {
      el.setAttribute('aria-label', t(el.dataset.i18nAria));
    }
    const titel = t('html.title');
    if (titel) document.title = titel;

    // Rechtstexte bleiben auf Deutsch - der Hinweis erscheint nur, wenn nötig
    const hinweis = $('legal-note');
    if (hinweis) hinweis.hidden = !t('legal.germanOnly');
  }

  const state = {
    home: null,              // {lat, lon, label}
    radius: 200,
    maxPrice: 150,
    allowUnknownPrice: true,
    allowUnknownGeo: false,
    showCancelled: false,
    // Gefiltert wird entweder nach Bands oder nach Genre: 'bands' | 'genre' | 'off'
    mode: 'bands',
    allowUnknownGenre: false,
    from: '',
    to: '',
    minDate: '',
    allowUnknownDate: false,
    selected: new Map(),     // bandIndex -> Gewicht (1 oder 2)
    genres: new Set(),       // gewählte Oberbegriffe als Spaltenindex
  };

  // Lineups als Set für schnelle Treffersuche
  const sets = F.map((r) => new Set(r[LINEUP]));

  // Wie oft kommt eine Band insgesamt vor? (für die Suchergebnisse)
  const bandFreq = new Int32Array(BANDS.length);
  for (const r of F) for (const b of r[LINEUP]) bandFreq[b]++;

  // Wie viele Festivals hat ein Oberbegriff? (für die Genreliste)
  const genreFreq = new Int32Array(GENRES.length);
  for (const r of F) for (const g of (r[GENRE_IDS] || [])) genreFreq[g]++;

  const genreName = (i) => t('genre.' + GENRES[i]);

  const foldCache = new Map();
  const fold = (s) => {
    let v = foldCache.get(s);
    if (v === undefined) {
      v = s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
           .replace(/ß/g, 'ss').replace(/ø/g, 'o').replace(/æ/g, 'ae')
           .replace(/[-.'’]/g, ' ').replace(/\s+/g, ' ').trim();
      foldCache.set(s, v);
    }
    return v;
  };
  const bandsFolded = BANDS.map(fold);

  /* ---------------- Entfernung ---------------- */

  function haversine(aLat, aLon, bLat, bLon) {
    const R = 6371, rad = Math.PI / 180;
    const dLat = (bLat - aLat) * rad, dLon = (bLon - aLon) * rad;
    const s = Math.sin(dLat / 2) ** 2 +
      Math.cos(aLat * rad) * Math.cos(bLat * rad) * Math.sin(dLon / 2) ** 2;
    return Math.round(2 * R * Math.asin(Math.sqrt(s)));
  }

  function distanceOf(row) {
    if (!state.home || row[LAT] == null) return null;
    return haversine(state.home.lat, state.home.lon, row[LAT], row[LON]);
  }

  /* ---------------- Wohnort bestimmen ---------------- */

  async function geocode(query) {
    const q = query.trim();
    if (!q) return null;

    // 1. Postleitzahl - die eindeutigste Eingabe. Erlaubt sind "97209",
    //    "97209 Veitshöchheim" und "1010 AT" zur Trennung von AT und CH.
    const pm = q.match(/^\s*(\d{4,5})\b\s*([A-Za-zÄÖÜäöü].*)?$/);
    if (pm) {
        const code = pm[1];
        const rest = fold(pm[2] || '');
        const hits = (D.plz || []).filter((p) => p[0] === code);
        if (hits.length) {
            let pick = hits[0];
            if (rest) {
                pick = hits.find((p) => fold(p[4]) === rest)
                    || hits.find((p) => fold(p[1]).startsWith(rest))
                    || pick;
            }
            const alt = hits.filter((p) => p[4] !== pick[4]).map((p) => p[4]);
            return {
                lat: pick[2], lon: pick[3],
                label: `${pick[0]} ${pick[1]} (${pick[4]})`,
                ambiguous: alt.length ? alt : null,
            };
        }
        return { notFound: code };
    }

    // 2. Ortsverzeichnis (GeoNames), nach Einwohnerzahl sortiert - der erste
    //    Treffer ist also der bekannteste Ort gleichen Namens.
    const needle = fold(q);
    let exact = null, prefix = null, weitere = 0;
    for (const [name, lat, lon, cc] of D.places) {
      const f = fold(name);
      if (f === needle) {
        if (exact) { weitere++; continue; }
        exact = { lat, lon, label: `${name} (${cc})` };
      } else if (f.startsWith(needle)) {
        if (prefix) { weitere++; continue; }
        prefix = { lat, lon, label: `${name} (${cc})` };
      }
    }
    const treffer = exact || prefix;
    if (treffer) {
      // Ortsnamen sind mehrdeutig - darauf hinweisen statt stillschweigend zu raten
      if (exact && prefix) weitere++;
      if (weitere) treffer.ambiguousName = weitere;
      return treffer;
    }

    // 3. Nur wenn lokal nichts passt: Nominatim (OpenStreetMap).
    //    In der veroeffentlichten Fassung blockiert die Sicherheitsrichtlinie
    //    externe Aufrufe - dann bleibt es beim Ergebnis aus Schritt 1.
    try {
      const url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1' +
        '&accept-language=de&q=' + encodeURIComponent(q);
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (res.ok) {
        const hits = await res.json();
        if (hits.length) {
          return {
            lat: parseFloat(hits[0].lat),
            lon: parseFloat(hits[0].lon),
            label: hits[0].display_name.split(',').slice(0, 2).join(',').trim(),
            online: true,
          };
        }
      }
    } catch (_) { /* offline oder blockiert */ }

    return null;
  }

  async function resolveHome() {
    const status = $('home-status');
    const q = $('home').value;
    if (!q.trim()) {
      state.home = null;
      status.className = 'hint';
      status.textContent = t('home.statusStart');
      render();
      return;
    }
    status.className = 'hint';
    status.textContent = t('home.statusSearching');
    const hit = await geocode(q);
    if (!hit || hit.notFound) {
      state.home = null;
      status.className = 'hint err';
      status.textContent = hit && hit.notFound
        ? t('home.statusPlzUnknown', { code: hit.notFound })
        : t('home.statusNotFound');
    } else {
      state.home = hit;
      status.className = 'hint ok';
      status.textContent = t('home.statusActive', { ort: hit.label }) +
        (hit.ambiguous
          ? t('home.ambiguousPlz', {
              laender: hit.ambiguous.join(', '),
              beispiel: `${q.trim().split(/\s+/)[0]} ${hit.ambiguous[0]}`,
            })
          : '') +
        (hit.ambiguousName ? t('home.ambiguousName', { n: hit.ambiguousName }) : '');
    }
    map.center = null;
    render();
    drawMap();
  }

  /* ---------------- Karte ----------------
     Gezeichnet wird auf Canvas aus mitgelieferten Vektorgrenzen. Kartenkacheln
     fremder Server sind in der veröffentlichten Fassung blockiert — und eine
     eigene Zeichnung verrät niemandem, wo jemand sucht. */

  const map = {
    canvas: null, ctx: null, view: null, pins: [], hover: -1,
    zoom: 1, center: null, drag: null, moved: false,
  };

  const ZOOM_MIN = 0.02, ZOOM_MAX = 60;

  // Umschließendes Rechteck je Polygonring, einmal berechnet und gemerkt
  const bounds = new WeakMap();
  function ringBounds(ring) {
    let b = bounds.get(ring);
    if (b) return b;
    let lon0 = Infinity, lon1 = -Infinity, lat0 = Infinity, lat1 = -Infinity;
    for (const [lon, lat] of ring) {
      if (lon < lon0) lon0 = lon;
      if (lon > lon1) lon1 = lon;
      if (lat < lat0) lat0 = lat;
      if (lat > lat1) lat1 = lat;
    }
    b = { lon0, lon1, lat0, lat1 };
    bounds.set(ring, b);
    return b;
  }

  // Mittabstandstreue Zylinderprojektion, an der Bildmitte ausgerichtet.
  // Für Ausschnitte bis ~2000 km ist die Verzerrung vernachlässigbar.
  function makeView(centerLat, centerLon, spanKm, w, h) {
    const kmPerDegLat = 111.32;
    const kmPerDegLon = kmPerDegLat * Math.cos(centerLat * Math.PI / 180);
    const aspect = w / h;
    const halfKmY = spanKm, halfKmX = spanKm * aspect;
    const sx = (w / 2) / halfKmX, sy = (h / 2) / halfKmY;
    return {
      w, h, centerLat, centerLon,
      x: (lon) => w / 2 + (lon - centerLon) * kmPerDegLon * sx,
      y: (lat) => h / 2 - (lat - centerLat) * kmPerDegLat * sy,
      lon: (px) => centerLon + (px - w / 2) / (kmPerDegLon * sx),
      lat: (py) => centerLat - (py - h / 2) / (kmPerDegLat * sy),
      kmToPxY: (km) => km * sy,
    };
  }

  function baseSpan() {
    return state.home ? state.radius * 1.35 : 2100;
  }

  function mapCenter() {
    if (map.center) return map.center;
    return state.home ? { lat: state.home.lat, lon: state.home.lon }
                      : { lat: 52.5, lon: 12.0 };
  }

  function resetMapView() {
    map.zoom = 1;
    map.center = null;
    drawMap();
  }

  function drawMap() {
    const cv = map.canvas;
    if (!cv) return;
    const ctx = map.ctx;
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth || 1000;
    const h = Math.round(w * 0.44);
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
      cv.style.height = h + 'px';
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    // Ausschnitt: um den Wohnort herum etwas mehr als der Radius, ohne Wohnort
    // ganz Europa - beides veränderbar durch Zoomen und Ziehen
    const c = mapCenter();
    const v = makeView(c.lat, c.lon, baseSpan() / map.zoom, w, h);
    map.view = v;

    ctx.fillStyle = '#080b10';                 // Wasser
    ctx.fillRect(0, 0, w, h);

    // Landmassen. Ringe ausserhalb des Ausschnitts werden uebersprungen -
    // die Weltkarte hat rund 90.000 Punkte, beim Hineinzoomen liegt das
    // meiste davon weit weg.
    const sicht = {
      lon0: v.lon(-40), lon1: v.lon(w + 40),
      lat0: v.lat(h + 40), lat1: v.lat(-40),
    };

    // Nah dran die feinen Umrisse, sonst die grobe Weltkarte: In der
    // Weltansicht kostet jeder Punkt Zeichenzeit, in der Nahansicht fiele
    // jede Vereinfachung als Kante auf.
    const box = D.fineBox;
    const nah = (baseSpan() / map.zoom) <= 1200;
    const inEuropa = box && sicht.lon0 >= box[0] && sicht.lon1 <= box[1]
                         && sicht.lat0 >= box[2] && sicht.lat1 <= box[3];
    const umrisse = (nah && inEuropa && D.worldFine && D.worldFine.length)
      ? D.worldFine : (D.world || []);

    ctx.beginPath();
    for (const ring of umrisse) {
      const b = ringBounds(ring);
      if (b.lon1 < sicht.lon0 || b.lon0 > sicht.lon1 ||
          b.lat1 < sicht.lat0 || b.lat0 > sicht.lat1) continue;
      let started = false;
      for (const [lon, lat] of ring) {
        const px = v.x(lon), py = v.y(lat);
        if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
      }
      ctx.closePath();
    }
    ctx.fillStyle = '#39424f';                 // Land, deutlich heller als Wasser
    ctx.fill('evenodd');
    ctx.strokeStyle = '#7d8899';               // Küstenlinie
    ctx.lineWidth = 0.9;
    ctx.stroke();

    // Radiuskreis. Die Projektion ist in beiden Achsen maßstabsgleich,
    // ein Bildschirmkreis entspricht also einer echten Luftlinie.
    if (state.home) {
      const hx = v.x(state.home.lon), hy = v.y(state.home.lat);
      const rPx = v.kmToPxY(state.radius);
      ctx.beginPath();
      ctx.ellipse(hx, hy, rPx, rPx, 0, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(226,35,26,.16)';
      ctx.fill();
      ctx.strokeStyle = '#ff3b30';
      ctx.lineWidth = 2.2;
      ctx.setLineDash([6, 5]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Pins der aktuellen Treffer
    for (const p of map.pins) {
      p.px = v.x(p.lon);
      p.py = v.y(p.lat);
    }
    map.pins.forEach((p, i) => {
      const active = i === map.hover;
      ctx.beginPath();
      ctx.arc(p.px, p.py, active ? 7 : 4.5, 0, Math.PI * 2);
      ctx.fillStyle = p.pct >= 50 ? '#ffb703' : '#f2f0ec';
      ctx.fill();
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = '#0b0b0d';
      ctx.stroke();
    });

    // Wohnort als Kreuz
    if (state.home) {
      const hx = v.x(state.home.lon), hy = v.y(state.home.lat);
      ctx.strokeStyle = '#6ec36e';
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      ctx.moveTo(hx - 7, hy); ctx.lineTo(hx + 7, hy);
      ctx.moveTo(hx, hy - 7); ctx.lineTo(hx, hy + 7);
      ctx.stroke();
    }

    // Maßstab: passt sich dem sichtbaren Ausschnitt an
    const visibleKm = baseSpan() / map.zoom;
    const stepKm = visibleKm >= 800 ? 500 : visibleKm >= 300 ? 100
                 : visibleKm >= 80 ? 25 : visibleKm >= 25 ? 10 : 2;
    const barPx = v.kmToPxY(stepKm);
    ctx.strokeStyle = '#9a978f';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(14, h - 16); ctx.lineTo(14 + barPx, h - 16);
    ctx.stroke();
    ctx.fillStyle = '#9a978f';
    ctx.font = '11px system-ui, sans-serif';
    ctx.fillText(`${stepKm} km`, 14, h - 22);

    // Hinweistext unter der Karte
    const cap = $('map-caption');
    const zoomInfo = map.zoom !== 1 || map.center
      ? t('map.view', { zoom: map.zoom.toFixed(1) })
      : t('map.zoomHint');
    const hovered = map.hover >= 0 ? map.pins[map.hover] : null;
    const km = state.radius.toLocaleString(sprache);

    if (hovered) {
      cap.textContent = `${hovered.name} — ${hovered.pct === null ? '' : hovered.pct.toFixed(0) + ' % '}` +
        (hovered.pct === null ? '' : t('card.match')) +
        (hovered.dist === null ? '' : `, ${hovered.dist.toLocaleString(sprache)} km`);
    } else if (!state.home) {
      cap.textContent = t('map.captionNoHome') + zoomInfo;
    } else if (!map.pins.length) {
      cap.textContent = t('map.captionRadius', { km, ort: state.home.label }) + zoomInfo;
    } else {
      cap.textContent = t(map.pins.length === 1 ? 'map.captionPin1' : 'map.captionPins',
        { n: map.pins.length, km, ort: state.home.label }) + zoomInfo;
    }
  }

  function initMap() {
    map.canvas = $('map');
    if (!map.canvas) return;
    map.ctx = map.canvas.getContext('2d');

    // Zoom am Mauszeiger: der Punkt unter dem Cursor bleibt liegen
    map.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const v = map.view;
      if (!v) return;
      const r = map.canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const lon0 = v.lon(mx), lat0 = v.lat(my);

      const factor = Math.exp(-e.deltaY * 0.0015);
      const next = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, map.zoom * factor));
      if (next === map.zoom) return;
      map.zoom = next;

      const c = mapCenter();
      const v2 = makeView(c.lat, c.lon, baseSpan() / map.zoom,
                          map.canvas.clientWidth, map.canvas.clientHeight);
      map.center = { lat: c.lat + (lat0 - v2.lat(my)), lon: c.lon + (lon0 - v2.lon(mx)) };
      drawMap();
    }, { passive: false });

    map.canvas.addEventListener('mousedown', (e) => {
      map.drag = { x: e.clientX, y: e.clientY, center: mapCenter() };
      map.moved = false;
      map.canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mouseup', () => {
      if (!map.drag) return;
      map.drag = null;
      map.canvas.style.cursor = map.hover >= 0 ? 'pointer' : 'default';
    });

    map.canvas.addEventListener('dblclick', resetMapView);

    map.canvas.addEventListener('mousemove', (e) => {
      const r = map.canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;

      if (map.drag && map.view) {
        const v = map.view;
        const dLon = v.lon(mx) - v.lon(mx - (e.clientX - map.drag.x));
        const dLat = v.lat(my) - v.lat(my - (e.clientY - map.drag.y));
        map.center = { lat: map.drag.center.lat - dLat, lon: map.drag.center.lon - dLon };
        if (Math.abs(e.clientX - map.drag.x) + Math.abs(e.clientY - map.drag.y) > 3) map.moved = true;
        drawMap();
        return;
      }

      let found = -1, bestD = 12 * 12;
      map.pins.forEach((p, i) => {
        const d = (p.px - mx) ** 2 + (p.py - my) ** 2;
        if (d < bestD) { bestD = d; found = i; }
      });
      if (found !== map.hover) {
        map.hover = found;
        map.canvas.style.cursor = found >= 0 ? 'pointer' : 'default';
        drawMap();
      }
    });

    map.canvas.addEventListener('mouseleave', () => {
      if (map.hover !== -1) { map.hover = -1; drawMap(); }
    });

    map.canvas.addEventListener('click', () => {
      if (map.moved) { map.moved = false; return; }   // war ein Verschieben
      if (map.hover < 0) return;
      const card = document.getElementById(map.pins[map.hover].cardId);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('flash');
        setTimeout(() => card.classList.remove('flash'), 1600);
      }
    });

    const step = (factor) => {
      map.zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, map.zoom * factor));
      drawMap();
    };
    $('zoom-in').addEventListener('click', () => step(1.5));
    $('zoom-out').addEventListener('click', () => step(1 / 1.5));
    $('zoom-reset').addEventListener('click', resetMapView);

    // Zwei Finger auf Touchgeräten
    let pinch = 0;
    const spread = (t) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
    map.canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 2) pinch = spread(e.touches);
    }, { passive: true });
    map.canvas.addEventListener('touchmove', (e) => {
      if (e.touches.length !== 2 || !pinch) return;
      e.preventDefault();
      const now = spread(e.touches);
      map.zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, map.zoom * (now / pinch)));
      pinch = now;
      drawMap();
    }, { passive: false });
    map.canvas.addEventListener('touchend', () => { pinch = 0; });

    window.addEventListener('resize', () => drawMap());
  }

  /* ---------------- Filter ---------------- */

  function passes(row) {
    if (row[CANCELLED] && !state.showCancelled) return false;
    if (state.home) {
      const d = distanceOf(row);
      if (d === null) { if (!state.allowUnknownGeo) return false; }
      else if (d > state.radius) return false;
    }
    const p = row[EUR];
    if (p === null) { if (!state.allowUnknownPrice) return false; }
    else if (p > state.maxPrice) return false;

    if (!row[FROM]) {
      if (!state.allowUnknownDate) return false;
    } else {
      if (state.from && row[FROM] < state.from) return false;
      if (state.to && row[FROM] > state.to) return false;
    }

    return true;
  }

  const filtered = () => F.map((r, i) => i).filter((i) => passes(F[i]));

  /* ---------------- Bandsuche ---------------- */

  let searchTimer = null;

  function renderBandResults() {
    const term = fold($('band-search').value.trim());
    const list = $('band-results');
    const hint = $('band-hint');
    list.innerHTML = '';

    if (term.length < 2) {
      hint.textContent = t('bands.hintMin', { n: BANDS.length.toLocaleString(sprache) });
      return;
    }

    const starts = [], contains = [];
    for (let i = 0; i < bandsFolded.length; i++) {
      const pos = bandsFolded[i].indexOf(term);
      if (pos === 0) starts.push(i);
      else if (pos > 0) contains.push(i);
      if (starts.length > 400) break;
    }
    const hits = starts.concat(contains);
    hits.sort((a, b) => bandFreq[b] - bandFreq[a] || BANDS[a].localeCompare(BANDS[b], sprache));
    const show = hits.slice(0, 80);

    hint.textContent = hits.length
      ? t('bands.hintHits', {
          n: hits.length,
          rest: hits.length > show.length ? t('bands.hintShown', { m: show.length }) : '',
        })
      : t('bands.hintNone');

    const frag = document.createDocumentFragment();
    for (const i of show) {
      const li = document.createElement('li');
      const label = document.createElement('span');
      label.textContent = BANDS[i];
      const cnt = document.createElement('span');
      cnt.className = 'cnt';
      cnt.textContent = bandFreq[i] === 1
        ? t('bands.festival1') : t('bands.festivals', { n: bandFreq[i] });
      const btn = document.createElement('button');
      const chosen = state.selected.has(i);
      btn.textContent = chosen ? t('bands.chosenBtn') : t('bands.choose');
      btn.disabled = chosen;
      btn.className = chosen ? 'ghost' : '';
      btn.title = t(chosen ? 'bands.chosenTitle' : 'bands.chooseTitle', { band: BANDS[i] });
      btn.addEventListener('click', () => {
        state.selected.set(i, 1);
        // Feld leeren, damit sich die nächste Band ohne Umweg tippen lässt
        const feld = $('band-search');
        feld.value = '';
        feld.focus();
        renderBandResults();
        renderChosen();
        render();
      });
      const left = document.createElement('div');
      left.append(label, document.createTextNode(' '), cnt);
      li.append(left, btn);
      frag.append(li);
    }
    list.append(frag);
  }

  function renderChosen() {
    const list = $('chosen-list');
    list.innerHTML = '';
    $('chosen-count').textContent = state.selected.size;

    if (!state.selected.size) {
      const li = document.createElement('li');
      li.className = 'hint';
      li.textContent = t('bands.empty');
      list.append(li);
      return;
    }

    const entries = [...state.selected.entries()]
      .sort((a, b) => BANDS[a[0]].localeCompare(BANDS[b[0]], sprache));

    for (const [i, weight] of entries) {
      const li = document.createElement('li');
      li.className = 'chip' + (weight === 2 ? ' double' : '');

      const name = document.createElement('span');
      name.textContent = BANDS[i];

      const w = document.createElement('button');
      w.className = 'w';
      w.textContent = weight === 2 ? '×2' : '×1';
      w.title = t(weight === 2 ? 'bands.weightDouble' : 'bands.weightSingle');
      w.addEventListener('click', () => {
        state.selected.set(i, weight === 2 ? 1 : 2);
        renderChosen(); render();
      });

      const x = document.createElement('button');
      x.className = 'x';
      x.textContent = '×';
      x.title = t('bands.remove');
      x.addEventListener('click', () => {
        state.selected.delete(i);
        renderChosen(); renderBandResults(); render();
      });

      li.append(name, w, x);
      list.append(li);
    }
  }

  /* ---------------- Genreauswahl ----------------
     Die Quellen schreiben das Genre als Freitext (1.544 Schreibweisen).
     scraper/genres.py fasst das zu Oberbegriffen zusammen; hier stehen nur
     noch deren Spaltennummern. */

  function renderGenres() {
    const list = $('genre-list');
    if (!list) return;
    list.innerHTML = '';

    const reihe = GENRES.map((_, i) => i)
      .sort((a, b) => genreName(a).localeCompare(genreName(b), sprache));

    const frag = document.createDocumentFragment();
    for (const i of reihe) {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      const an = state.genres.has(i);
      btn.className = 'genre-chip' + (an ? ' on' : '');
      btn.setAttribute('aria-pressed', an ? 'true' : 'false');
      btn.title = t(an ? 'genre.removeTitle' : 'genre.addTitle', { genre: genreName(i) });
      const name = document.createElement('span');
      name.textContent = genreName(i);
      const cnt = document.createElement('span');
      cnt.className = 'cnt';
      cnt.textContent = genreFreq[i].toLocaleString(sprache);
      btn.append(name, cnt);
      btn.addEventListener('click', () => {
        if (state.genres.has(i)) state.genres.delete(i); else state.genres.add(i);
        renderGenres();
        render();
      });
      li.append(btn);
      frag.append(li);
    }
    list.append(frag);

    $('genre-hint').textContent = !state.genres.size ? t('genre.empty')
      : state.genres.size === 1 ? t('genre.chosen1')
      : t('genre.chosen', { n: state.genres.size });
  }

  /** Zeigt den Block, nach dem gerade gefiltert wird. */
  function modusAnwenden() {
    $('band-block').hidden = state.mode === 'genre';
    $('genre-block').hidden = state.mode !== 'genre';
    $('step-bands').classList.toggle('bands-off', state.mode === 'off');
  }

  /* ---------------- Treffer ---------------- */

  /** Datenstand mit Uhrzeit: "10.08.2026 um 14:32 Uhr" */
  function fmtStand(stamp) {
    if (!stamp) return 'unbekannt';
    const m = String(stamp).match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
    if (!m) return stamp;
    const datum = `${m[3]}.${m[2]}.${m[1]}`;
    return m[4] ? t('stand.at', { datum, zeit: `${m[4]}:${m[5]}` }) : datum;
  }

  const fmtDate = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}.${m}.${y}`;
  };

  function dateLabel(row) {
    if (!row[FROM]) return row[NOTE] || t('card.dateOpen');
    return row[TO] && row[TO] !== row[FROM]
      ? `${fmtDate(row[FROM])} – ${fmtDate(row[TO])}`
      : fmtDate(row[FROM]);
  }

  function priceLabel(row) {
    if (row[EUR] === 0) return t('card.free');
    if (row[EUR] == null) return row[PRICE_RAW] || t('card.priceUnknown');
    const eur = `${row[EUR].toLocaleString(sprache, { minimumFractionDigits: 2 })} €`;
    const raw = (row[PRICE_RAW] || '').trim();
    const ab = t('card.from');
    return /^(ab )?(EUR|€)/i.test(raw) ? `${ab} ${eur}` : `${ab} ${eur} (${raw})`;
  }

  function render() {
    const pool = filtered();
    const total = state.selected.size
      ? [...state.selected.values()].reduce((a, b) => a + b, 0) : 0;

    $('filter-stat').innerHTML =
      t('filter.stat', { n: pool.length.toLocaleString(sprache),
                         gesamt: F.length.toLocaleString(sprache) }) +
      (state.home ? '' : t('filter.noHome'));

    const list = $('festival-list');
    list.innerHTML = '';

    if (state.mode === 'bands' && !total) {
      $('result-stat').textContent = t('res.needBand');
      map.pins = [];
      map.hover = -1;
      drawMap();
      return;
    }
    if (state.mode === 'genre' && !state.genres.size) {
      $('result-stat').textContent = t('res.needGenre');
      map.pins = [];
      map.hover = -1;
      drawMap();
      return;
    }

    const scored = [];
    for (const i of pool) {
      const row = F[i], set = sets[i];
      const eintrag = { i, row, pct: null, hits: [], gHits: [], dist: distanceOf(row) };
      if (state.mode === 'bands') {
        let weight = 0;
        for (const [b, w] of state.selected) {
          if (set.has(b)) { weight += w; eintrag.hits.push([b, w]); }
        }
        if (!weight) continue;                 // ohne Treffer nicht anzeigen
        eintrag.pct = (weight / total) * 100;
      } else if (state.mode === 'genre') {
        const eigene = row[GENRE_IDS] || [];
        for (const g of eigene) if (state.genres.has(g)) eintrag.gHits.push(g);
        if (eintrag.gHits.length) {
          eintrag.pct = (eintrag.gHits.length / state.genres.size) * 100;
        } else if (!eigene.length && state.allowUnknownGenre) {
          eintrag.pct = null;                  // Genre unbekannt: ans Ende
        } else {
          continue;
        }
      }
      scored.push(eintrag);
    }

    // Ohne Band- und Genrefilter gibt es keine Übereinstimmung, nach der sich
    // sortieren ließe - dann entscheidet Entfernung, danach Termin und Preis.
    // Beim Genrefilter stehen Festivals ohne Genreangabe (pct null) hinten.
    const rang = (e) => (e.pct === null ? -1 : e.pct);
    scored.sort((a, b) =>
      (state.mode === 'off' ? 0 : rang(b) - rang(a)) ||
      (a.dist ?? Infinity) - (b.dist ?? Infinity) ||
      (a.row[FROM] || '9999').localeCompare(b.row[FROM] || '9999') ||
      (a.row[EUR] ?? Infinity) - (b.row[EUR] ?? Infinity) ||
      a.row[NAME].localeCompare(b.row[NAME], sprache));

    const eins = scored.length === 1;
    if (state.mode === 'off') {
      $('result-stat').innerHTML = !scored.length ? t('res.none')
        : t(eins ? 'res.oneWithoutBands' : 'res.withoutBands', { n: scored.length });
    } else if (state.mode === 'genre') {
      const schluessel = !scored.length ? null
        : eins ? (state.genres.size === 1 ? 'res.oneWithGenre1' : 'res.oneWithGenres')
               : (state.genres.size === 1 ? 'res.withGenres1' : 'res.withGenres');
      $('result-stat').innerHTML = schluessel
        ? t(schluessel, { n: scored.length, g: state.genres.size })
        : t('res.noneGenres');
    } else {
      const schluessel = !scored.length ? null
        : eins ? (state.selected.size === 1 ? 'res.oneWithBand1' : 'res.oneWithBands')
               : (state.selected.size === 1 ? 'res.withBands1' : 'res.withBands');
      $('result-stat').innerHTML = schluessel
        ? t(schluessel, { n: scored.length, b: state.selected.size })
        : t('res.noneBands');
    }

    const shown = scored.slice(0, 300);
    const frag = document.createDocumentFragment();
    shown.forEach((s, n) => { s.cardId = `fest-${n}`; frag.append(card(s)); });
    list.append(frag);

    map.pins = shown
      .filter((s) => s.row[LAT] != null)
      .map((s) => ({
        lat: s.row[LAT], lon: s.row[LON], name: s.row[NAME],
        pct: s.pct, dist: s.dist, cardId: s.cardId, px: 0, py: 0,
      }));
    map.hover = -1;
    drawMap();

    if (scored.length > 300) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = t('res.more', { n: scored.length - 300 });
      list.append(li);
    }
  }

  function card(s) {
    const row = s.row;
    const li = document.createElement('li');
    li.className = 'fest' + (s.pct !== null && s.pct >= 50 ? ' top' : '') +
                   (row[CANCELLED] ? ' cancelled' : '');
    li.id = s.cardId;

    const head = document.createElement('div');
    head.className = 'fest-head';

    const h3 = document.createElement('h3');
    if (row[WEB]) {
      const a = document.createElement('a');
      a.href = row[WEB]; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = row[NAME];
      a.title = t('card.websiteTitle', { name: row[NAME] });
      h3.append(a);
    } else h3.textContent = row[NAME];

    const titleBox = document.createElement('div');
    if (row[CANCELLED]) {
      const flag = document.createElement('span');
      flag.className = 'flag';
      flag.textContent = t('card.cancelled');
      flag.title = t('card.cancelledTitle');
      titleBox.append(flag);
    }
    titleBox.append(h3);
    head.append(titleBox);

    if (s.pct !== null) {
      const pct = document.createElement('div');
      pct.className = 'pct';
      pct.textContent = `${s.pct.toFixed(0)} %`;
      const small = document.createElement('small');
      small.textContent = t('card.match');
      pct.append(small);
      head.append(pct);
    }

    const facts = document.createElement('ul');
    facts.className = 'facts';
    const place = [row[VENUE], row[CITY], row[LAND]].filter(Boolean).join(', ');
    const items = [
      [t('card.date'), dateLabel(row)],
      [t('card.price'), priceLabel(row)],
      [t('card.place'), place || t('card.unknownPlace')],
      [t('card.distance'), s.dist === null
        ? (state.home ? t('card.unknownPlace') : t('card.noHomeSet'))
        : `${s.dist.toLocaleString(sprache)} km`],
    ];
    for (const [k, v] of items) {
      const el = document.createElement('li');
      el.innerHTML = `${k}: <b></b>`;
      el.querySelector('b').textContent = v;
      facts.append(el);
    }
    // Genre-Oberbegriffe des Festivals; die gewählten sind hervorgehoben.
    const genres = row[GENRE_IDS] || [];
    if (genres.length) {
      const el = document.createElement('li');
      el.className = 'genre-line';
      el.append(document.createTextNode(t('card.genre') + ': '));
      const treffer = new Set(s.gHits);
      genres.forEach((g, n) => {
        const span = document.createElement(treffer.has(g) ? 'mark' : 'b');
        span.textContent = genreName(g);
        el.append(span);
        if (n < genres.length - 1) el.append(document.createTextNode(' · '));
      });
      facts.append(el);
    }

    if (row[WEB]) {
      const el = document.createElement('li');
      const a = document.createElement('a');
      a.href = row[WEB]; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = t('card.website');
      a.title = t('card.websiteTitle', { name: row[NAME] });
      el.append(a);
      facts.append(el);
    }

    const hits = document.createElement('p');
    hits.className = 'hits';
    if (!s.hits.length) hits.hidden = true;
    const hitNames = s.hits
      .sort((a, b) => b[1] - a[1] || BANDS[a[0]].localeCompare(BANDS[b[0]], sprache));
    hits.append(document.createTextNode(t('card.yourBands')));
    hitNames.forEach(([b, w], n) => {
      const span = document.createElement('span');
      span.className = 'hit' + (w === 2 ? ' dbl' : '');
      span.textContent = BANDS[b];
      span.title = t(w === 2 ? 'card.bandDouble' : 'card.bandSingle', { band: BANDS[b] });
      hits.append(span);
      if (n < hitNames.length - 1) hits.append(document.createTextNode(', '));
    });

    const det = document.createElement('details');
    det.className = 'lineup';
    const sum = document.createElement('summary');
    sum.textContent = t('card.lineup', { n: row[LINEUP].length });
    sum.title = t('card.lineupTitle');
    const all = document.createElement('div');
    all.className = 'all';
    const chosenIdx = new Set(s.hits.map((h) => h[0]));
    const names = row[LINEUP].map((b) => [BANDS[b], chosenIdx.has(b)])
      .sort((a, b) => a[0].localeCompare(b[0], sprache));
    names.forEach(([n, isHit], k) => {
      const el = document.createElement(isHit ? 'mark' : 'span');
      el.textContent = n;
      all.append(el);
      if (k < names.length - 1) all.append(document.createTextNode(' · '));
    });
    if (!names.length) all.textContent = t('card.noLineup');
    det.append(sum, all);

    li.append(head, facts, hits, det);
    return li;
  }

  /* ---------------- Zugriffszählung ----------------
     Eine statische Seite kann sich nicht selbst zählen. Ist in config.js eine
     GoatCounter-Kennung hinterlegt, meldet die Seite den Aufruf dorthin — ohne
     Cookies, ohne Zugriff auf den Gerätespeicher. Ohne Kennung passiert gar
     nichts.

     Die Seite selbst zeigt keinen Zählerstand, auch nicht auf Umwegen: Der
     Stand steht ausschließlich im GoatCounter-Konto hinter der Anmeldung.
     Eine Anzeige hier würde verlangen, die Zahlen bei GoatCounter öffentlich
     zu schalten — und öffentlich soll der Stand zu keinem Zeitpunkt sein. */

  function initZaehler() {
    const code = ((window.CONFIG && window.CONFIG.zaehler) || '').trim();
    const eigenstaendig = window.top === window.self;
    const echteAdresse = location.protocol === 'https:' &&
                         location.hostname !== 'localhost';
    // Eingebettet sperrt die Sicherheitsrichtlinie den Aufruf, lokal zählt
    // GoatCounter ohnehin nicht - dann unterbleibt auch der Hinweis, sonst
    // stünde im Fuß eine Zählung, die gar nicht stattfindet.
    const zaehlt = Boolean(code) && eigenstaendig && echteAdresse;

    const hinweis = $('zaehler-hinweis');
    if (hinweis) hinweis.hidden = !zaehlt;
    if (!zaehlt) return;

    const s = document.createElement('script');
    s.async = true;
    s.src = 'https://gc.zgo.at/count.js';
    s.dataset.goatcounter = `https://${code}.goatcounter.com/count`;
    document.head.append(s);
  }

  /* ---------------- Installierbarkeit ----------------
     Der Service Worker legt die Seite ab, damit sie vom Startbildschirm auch
     ohne Netz startet. Er verlangt eine eigene Adresse über HTTPS; in der
     eingebetteten Fassung ist das gesperrt, deshalb die Prüfungen. */

  function initPwa() {
    const eigenstaendig = window.top === window.self;
    const sicher = location.protocol === 'https:' || location.hostname === 'localhost';
    if ('serviceWorker' in navigator && eigenstaendig && sicher) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('sw.js').catch(() => { /* ohne ist es auch nutzbar */ });
      });
    }

    const knopf = $('install');
    if (!knopf) return;

    // Android und Desktop-Chrome melden sich, wenn eine Installation möglich ist
    let angebot = null;
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      angebot = e;
      knopf.hidden = false;
    });

    knopf.addEventListener('click', async () => {
      if (!angebot) return;
      angebot.prompt();
      await angebot.userChoice;
      angebot = null;
      knopf.hidden = true;
    });

    window.addEventListener('appinstalled', () => { knopf.hidden = true; });

    // iOS kennt kein Installationsangebot - dort führt der Weg über das
    // Teilen-Menü, deshalb dort ein Hinweis statt eines Knopfes.
    const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const schonInstalliert = window.matchMedia('(display-mode: standalone)').matches ||
                             navigator.standalone === true;
    if (iOS && !schonInstalliert && eigenstaendig) {
      const hinweis = $('install-hint');
      if (hinweis) hinweis.hidden = false;
    }
  }

  /* ---------------- Rückmeldung ----------------
     Die veröffentlichte Fassung darf keine fremden Server aufrufen, ein
     Formularversand scheidet damit aus. Der Text wird stattdessen lokal
     zusammengesetzt und an das E-Mail-Programm übergeben; abgeschickt wird
     erst dort. Wer keines eingerichtet hat, kopiert den Text. */

  const FEEDBACK_MAIL = 'waldsprenger@gmail.com';

  function feedbackText() {
    const art = $('fb-art').value;
    const nachricht = $('fb-text').value.trim();
    const kontakt = $('fb-kontakt').value.trim();
    const zeilen = [nachricht];
    if (kontakt) zeilen.push('', `Rückmeldeadresse: ${kontakt}`);
    zeilen.push('', `— Datenstand ${fmtStand(D.generated)}`);
    return { betreff: `Festival Finder: ${art}`, koerper: zeilen.join('\n'), nachricht };
  }

  function initFeedback() {
    if (!$('fb-send')) return;
    const status = $('fb-status');

    const pruefen = () => {
      const { nachricht } = feedbackText();
      if (nachricht) return true;
      status.className = 'hint err';
      status.textContent = t('fb.needText');
      $('fb-text').focus();
      return false;
    };

    // Ein echter Link statt eines Sprungs per Skript: In der eingebetteten
    // Fassung wird eine gesetzte Adresse geblockt, ein Klick auf mailto nicht.
    const linkAktualisieren = () => {
      const { betreff, koerper } = feedbackText();
      $('fb-send').href = `mailto:${FEEDBACK_MAIL}` +
        `?subject=${encodeURIComponent(betreff)}&body=${encodeURIComponent(koerper)}`;
    };

    $('fb-send').addEventListener('click', (e) => {
      if (!pruefen()) { e.preventDefault(); return; }
      linkAktualisieren();
      status.className = 'hint ok';
      status.textContent = t('fb.opened');
    });

    for (const id of ['fb-art', 'fb-text', 'fb-kontakt']) {
      $(id).addEventListener('input', linkAktualisieren);
      $(id).addEventListener('change', linkAktualisieren);
    }
    linkAktualisieren();

    $('fb-copy').addEventListener('click', async () => {
      if (!pruefen()) return;
      const { betreff, koerper } = feedbackText();
      const text = `An: ${FEEDBACK_MAIL}\nBetreff: ${betreff}\n\n${koerper}`;
      try {
        await navigator.clipboard.writeText(text);
        status.className = 'hint ok';
        status.textContent = t('fb.copied', { mail: FEEDBACK_MAIL });
      } catch (_) {
        status.className = 'hint err';
        status.textContent = t('fb.copyFailed');
      }
    });

    for (const id of ['fb-text', 'fb-kontakt']) {
      $(id).addEventListener('input', () => {
        if (status.textContent) { status.className = 'hint'; status.textContent = ''; }
      });
    }
  }

  /* ---------------- Hilfetexte ----------------
     Auf Touchgeräten gibt es kein Mouseover, deshalb öffnet ein Klick auf das
     Fragezeichen den Text in einem Feld. Am Rechner bleibt zusätzlich der
     native Tooltip erhalten. */

  function initHelp() {
    const box = document.createElement('div');
    box.className = 'help-box';
    box.hidden = true;
    box.setAttribute('role', 'status');
    document.body.append(box);

    let offen = null;

    function schliessen() {
      box.hidden = true;
      if (offen) offen.classList.remove('on');
      offen = null;
    }

    function oeffnen(btn) {
      box.textContent = btn.getAttribute('title') || '';
      box.hidden = false;
      btn.classList.add('on');
      offen = btn;

      // unter dem Fragezeichen platzieren, aber im Fenster halten
      const r = btn.getBoundingClientRect();
      const breite = Math.min(320, window.innerWidth - 24);
      box.style.width = breite + 'px';
      let links = r.left + window.scrollX + r.width / 2 - breite / 2;
      links = Math.max(12, Math.min(links, window.innerWidth - breite - 12));
      box.style.left = links + 'px';
      box.style.top = (r.bottom + window.scrollY + 8) + 'px';
    }

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('button.help');
      if (btn) {
        e.preventDefault();
        e.stopPropagation();
        if (offen === btn) schliessen(); else oeffnen(btn);
        return;
      }
      if (!e.target.closest('.help-box')) schliessen();
    });

    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') schliessen(); });
    window.addEventListener('resize', schliessen);
    window.addEventListener('scroll', schliessen, { passive: true });
  }

  /* ---------------- Rechtstexte ----------------
     Nur die gebündelte Einzelseite enthält Impressum und Datenschutz als
     Abschnitte. Dort bleiben sie eingeklappt, bis der Fußlink sie öffnet.
     In der lokalen Fassung sind es eigene Dateien - dann tut das hier nichts. */

  function initLegal() {
    const ids = ['impressum', 'datenschutz'];
    const secs = ids.map((id) => $(id)).filter(Boolean);
    if (!secs.length) return;

    for (const sec of secs) {
      sec.hidden = true;
      const back = document.createElement('button');
      back.type = 'button';
      back.className = 'ghost small legal-close';
      // Der Rechtstext bleibt deutsch, der Weg zurueck ist Oberflaeche -
      // die Auszeichnung sorgt dafuer, dass ein Sprachwechsel ihn mitnimmt.
      back.dataset.i18n = 'legal.back';
      back.dataset.i18nTitle = 'legal.backTitle';
      back.textContent = t('legal.back');
      back.title = t('legal.backTitle');
      back.addEventListener('click', () => show(null));
      sec.append(back);
    }

    function show(id) {
      for (const sec of secs) sec.hidden = sec.id !== id;
      const main = document.querySelector('main');
      const foot = document.querySelector('.site-footer');
      if (main) main.hidden = !!id;
      if (foot) foot.hidden = !!id;
      if (id) $(id).scrollIntoView({ block: 'start' });
      else window.scrollTo({ top: 0 });
    }

    for (const a of document.querySelectorAll('.site-footer nav a')) {
      const id = (a.getAttribute('href') || '').replace('#', '');
      if (!ids.includes(id)) continue;
      a.title = id === 'impressum'
        ? 'Impressum mit Anbieterangaben öffnen.'
        : 'Datenschutzerklärung öffnen — was mit deinen Eingaben passiert.';
      a.addEventListener('click', (e) => { e.preventDefault(); show(id); });
    }
  }

  function aktualisiereDatenstand() {
    $('build-info').textContent = t('footer.build', {
      stand: fmtStand(D.generated),
      f: F.length.toLocaleString(sprache),
      a: BANDS.length.toLocaleString(sprache),
    });
  }

  /** Baut die Sprachauswahl und schaltet die gesamte Oberfläche um. */
  function initSprache() {
    const wahl = $('lang');
    if (!wahl) return;
    for (const [code, name] of Object.entries(I18N.SPRACHEN)) {
      const o = document.createElement('option');
      o.value = code;
      o.textContent = name;
      wahl.append(o);
    }
    wahl.value = sprache;

    wahl.addEventListener('change', () => {
      sprache = wahl.value;
      try { localStorage.setItem(SPEICHER, sprache); } catch (_) { /* egal */ }
      spracheAnwenden();
      // alles neu zeichnen, was Text aus dem Skript enthält
      renderBandResults();
      renderChosen();
      renderGenres();
      render();
      aktualisiereDatenstand();
      datumsHinweisNeu();
    });

    spracheAnwenden();
  }

  // wird in init() gesetzt, damit der Datumshinweis die Sprache mitbekommt
  let datumsHinweisNeu = () => {};

  /* ---------------- Verdrahtung ---------------- */

  function init() {
    // Obergrenzen kommen aus den Daten: der Umkreis reicht bis zum entferntesten
    // Festival, der Preis bis zum teuersten gefundenen Ticket.
    const rad = $('radius'), pri = $('price');
    if (D.maxDistanceKm) rad.max = String(D.maxDistanceKm);
    if (D.maxPriceEur) pri.max = String(D.maxPriceEur);
    state.radius = +rad.value;
    state.maxPrice = +pri.value;
    $('radius-out').textContent = `${state.radius.toLocaleString('de-DE')} km`;
    $('price-out').textContent = `${state.maxPrice} €`;

    // Untergrenze des Kalenders: Monatsanfang des frühesten Festivals im
    // Datenbestand. Voreingestellt bleibt heute, sofern das darin liegt.
    const today = new Date().toISOString().slice(0, 10);
    const minDate = D.minDate || '';
    state.minDate = minDate;
    if (minDate) { $('from').min = minDate; $('to').min = minDate; }
    state.from = minDate && today < minDate ? minDate : today;
    $('from').value = state.from;

    $('locate').addEventListener('click', resolveHome);
    $('home').addEventListener('keydown', (e) => { if (e.key === 'Enter') resolveHome(); });

    $('radius').addEventListener('input', (e) => {
      state.radius = +e.target.value;
      $('radius-out').textContent = `${state.radius.toLocaleString('de-DE')} km`;
      drawMap();
      render();
    });

    $('price').addEventListener('input', (e) => {
      state.maxPrice = +e.target.value;
      $('price-out').textContent = `${state.maxPrice} €`;
      render();
    });

    $('price-unknown').addEventListener('change', (e) => {
      state.allowUnknownPrice = e.target.checked; render();
    });

    $('geo-unknown').addEventListener('change', (e) => {
      state.allowUnknownGeo = e.target.checked; render();
    });

    $('show-cancelled').addEventListener('change', (e) => {
      state.showCancelled = e.target.checked; render();
    });

    // Entweder Bands oder Genre - beide Auswahlen bleiben erhalten, es wirkt
    // aber immer nur die des aktiven Modus.
    for (const el of document.querySelectorAll('input[name="filter-mode"]')) {
      el.addEventListener('change', (e) => {
        if (!e.target.checked) return;
        state.mode = e.target.value;
        modusAnwenden();
        render();
      });
    }

    $('genre-unknown').addEventListener('change', (e) => {
      state.allowUnknownGenre = e.target.checked; render();
    });

    $('clear-genres').addEventListener('click', () => {
      state.genres.clear(); renderGenres(); render();
    });

    // Die beiden Felder begrenzen sich gegenseitig, damit kein leerer
    // Zeitraum entstehen kann
    const heute = today;

    /** Erklärt, warum ein Datum zurückgezogen wurde, und warnt vor
     *  Zeiträumen in der Vergangenheit. */
    function datumsHinweis(zuFrueh) {
      const el = $('date-hint');
      const vergangen = (state.from && state.from < heute) ||
                        (state.to && state.to < heute);
      if (zuFrueh) {
        el.className = 'hint err';
        el.textContent = t('date.tooEarly', { datum: fmtDate(state.minDate) });
      } else if (vergangen) {
        el.className = 'hint warn';
        el.textContent = t('date.past');
      } else {
        el.className = 'hint';
        el.textContent = '';
      }
    }

    // Eingetippte Daten koennen die Untergrenze unterlaufen - der Kalender
    // selbst bietet sie gar nicht erst an
    const klemme = (wert) => (state.minDate && wert && wert < state.minDate)
      ? state.minDate : wert;

    $('from').addEventListener('change', (e) => {
      const eingabe = e.target.value;
      e.target.value = klemme(eingabe);
      state.from = e.target.value;
      $('to').min = state.from || state.minDate || '';
      if (state.to && state.from && state.to < state.from) {
        state.to = state.from;
        $('to').value = state.to;
      }
      datumsHinweis(eingabe && eingabe !== e.target.value);
      render();
    });

    $('to').addEventListener('change', (e) => {
      const eingabe = e.target.value;
      e.target.value = klemme(eingabe);
      state.to = e.target.value;
      $('from').max = state.to || '';
      if (state.from && state.to && state.from > state.to) {
        state.from = state.to;
        $('from').value = state.from;
      }
      datumsHinweis(eingabe && eingabe !== e.target.value);
      render();
    });

    $('date-unknown').addEventListener('change', (e) => {
      state.allowUnknownDate = e.target.checked; render();
    });

    $('band-search').addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(renderBandResults, 120);
    });

    $('clear-bands').addEventListener('click', () => {
      state.selected.clear(); renderChosen(); renderBandResults(); render();
    });

    aktualisiereDatenstand();

    datumsHinweisNeu = () => datumsHinweis(false);
    datumsHinweis(false);
    initSprache();
    initMap();
    initHelp();
    initPwa();
    initZaehler();
    initFeedback();
    initLegal();
    modusAnwenden();
    renderBandResults();
    renderChosen();
    renderGenres();
    render();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
