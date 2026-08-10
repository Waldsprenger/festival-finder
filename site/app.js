/* Festival Finder — Filter, Bandauswahl, Trefferberechnung.
   Läuft ohne Server; die Daten liegen in data.js als window.DATA. */

(() => {
  'use strict';

  const D = window.DATA;
  const F = D.festivals;
  const BANDS = D.bands;

  // Spaltenindizes von data.js
  const NAME = 0, FROM = 1, TO = 2, CITY = 3, LAND = 4, VENUE = 5,
        EUR = 6, PRICE_RAW = 7, WEB = 8, LAT = 9, LON = 10, LINEUP = 11,
        GENRE = 12, NOTE = 13;

  const $ = (id) => document.getElementById(id);

  const state = {
    home: null,              // {lat, lon, label}
    radius: 200,
    maxPrice: 150,
    allowUnknownPrice: true,
    allowUnknownGeo: false,
    from: '',
    allowUnknownDate: false,
    selected: new Map(),     // bandIndex -> Gewicht (1 oder 2)
  };

  // Lineups als Set für schnelle Treffersuche
  const sets = F.map((r) => new Set(r[LINEUP]));

  // Wie oft kommt eine Band insgesamt vor? (für die Suchergebnisse)
  const bandFreq = new Int32Array(BANDS.length);
  for (const r of F) for (const b of r[LINEUP]) bandFreq[b]++;

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
        return { notFound: `Zur Postleitzahl ${code} gibt es keinen Eintrag.` };
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
      status.textContent = 'Stadt eingeben und „Suchen“ drücken.';
      render();
      return;
    }
    status.className = 'hint';
    status.textContent = 'Suche Koordinaten …';
    const hit = await geocode(q);
    if (!hit || hit.notFound) {
      state.home = null;
      status.className = 'hint err';
      status.textContent = hit && hit.notFound
        ? hit.notFound
        : 'Ort nicht gefunden. Am sichersten ist die Postleitzahl, z. B. 97209.';
    } else {
      state.home = hit;
      status.className = 'hint ok';
      status.textContent = `${hit.label} — Umkreissuche aktiv.` +
        (hit.ambiguous
          ? ` Diese Postleitzahl gibt es auch in ${hit.ambiguous.join(', ')} — dann Land anhängen, z. B. „${q.trim().split(/\s+/)[0]} ${hit.ambiguous[0]}“.`
          : '') +
        (hit.ambiguousName
          ? ` Achtung: Es gibt ${hit.ambiguousName} weitere${hit.ambiguousName === 1 ? 'n' : ''} Ort${hit.ambiguousName === 1 ? '' : 'e'} mit ähnlichem Namen — mit der Postleitzahl wird es eindeutig.`
          : '');
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

  const ZOOM_MIN = 0.25, ZOOM_MAX = 60;

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

    ctx.fillStyle = '#0e1116';
    ctx.fillRect(0, 0, w, h);

    // Landmassen
    ctx.beginPath();
    for (const ring of (D.europe || [])) {
      let started = false;
      for (const [lon, lat] of ring) {
        const px = v.x(lon), py = v.y(lat);
        if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
      }
      ctx.closePath();
    }
    ctx.fillStyle = '#1c2029';
    ctx.fill('evenodd');
    ctx.strokeStyle = '#333a47';
    ctx.lineWidth = 0.7;
    ctx.stroke();

    // Radiuskreis. Die Projektion ist in beiden Achsen maßstabsgleich,
    // ein Bildschirmkreis entspricht also einer echten Luftlinie.
    if (state.home) {
      const hx = v.x(state.home.lon), hy = v.y(state.home.lat);
      const rPx = v.kmToPxY(state.radius);
      ctx.beginPath();
      ctx.ellipse(hx, hy, rPx, rPx, 0, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(226,35,26,.11)';
      ctx.fill();
      ctx.strokeStyle = '#e2231a';
      ctx.lineWidth = 1.8;
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
      ? ` · Ansicht ${map.zoom.toFixed(1)}×`
      : ' · Mausrad zoomt, Ziehen verschiebt';
    const hovered = map.hover >= 0 ? map.pins[map.hover] : null;

    if (hovered) {
      cap.textContent = `${hovered.name} — ${hovered.pct.toFixed(0)} % Übereinstimmung` +
        (hovered.dist === null ? '' : `, ${hovered.dist.toLocaleString('de-DE')} km`);
    } else if (!state.home) {
      cap.textContent = 'Wohnort eingeben, um den Suchradius zu sehen.' + zoomInfo;
    } else if (!map.pins.length) {
      cap.textContent = `Umkreis ${state.radius.toLocaleString('de-DE')} km um ${state.home.label}. ` +
        'Nach der Bandauswahl erscheinen hier die passenden Festivals.' + zoomInfo;
    } else {
      cap.textContent = `${map.pins.length} Festival${map.pins.length === 1 ? '' : 's'} im Umkreis von ` +
        `${state.radius.toLocaleString('de-DE')} km um ${state.home.label}. Pin anklicken springt zum Eintrag.` +
        zoomInfo;
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
                          map.canvas.clientWidth, parseFloat(map.canvas.style.height));
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
    if (state.home) {
      const d = distanceOf(row);
      if (d === null) { if (!state.allowUnknownGeo) return false; }
      else if (d > state.radius) return false;
    }
    const p = row[EUR];
    if (p === null) { if (!state.allowUnknownPrice) return false; }
    else if (p > state.maxPrice) return false;

    if (!row[FROM]) { if (!state.allowUnknownDate) return false; }
    else if (state.from && row[FROM] < state.from) return false;

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
      hint.textContent = `${BANDS.length.toLocaleString('de-DE')} Acts in der Datenbank — mindestens zwei Zeichen eingeben.`;
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
    hits.sort((a, b) => bandFreq[b] - bandFreq[a] || BANDS[a].localeCompare(BANDS[b], 'de'));
    const show = hits.slice(0, 80);

    hint.textContent = hits.length
      ? `${hits.length} Treffer${hits.length > show.length ? `, die ersten ${show.length} angezeigt` : ''}.`
      : 'Keine Band mit diesem Namen gefunden.';

    const frag = document.createDocumentFragment();
    for (const i of show) {
      const li = document.createElement('li');
      const label = document.createElement('span');
      label.textContent = BANDS[i];
      const cnt = document.createElement('span');
      cnt.className = 'cnt';
      cnt.textContent = `${bandFreq[i]} Festival${bandFreq[i] === 1 ? '' : 's'}`;
      const btn = document.createElement('button');
      const chosen = state.selected.has(i);
      btn.textContent = chosen ? 'gewählt' : 'wählen';
      btn.disabled = chosen;
      btn.className = chosen ? 'ghost' : '';
      btn.title = chosen
        ? `${BANDS[i]} steht bereits in deiner Auswahl.`
        : `${BANDS[i]} zur Auswahl hinzufügen — die Trefferliste aktualisiert sich sofort.`;
      btn.addEventListener('click', () => { state.selected.set(i, 1); renderBandResults(); renderChosen(); render(); });
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
      li.textContent = 'Noch keine Band gewählt.';
      list.append(li);
      return;
    }

    const entries = [...state.selected.entries()]
      .sort((a, b) => BANDS[a[0]].localeCompare(BANDS[b[0]], 'de'));

    for (const [i, weight] of entries) {
      const li = document.createElement('li');
      li.className = 'chip' + (weight === 2 ? ' double' : '');

      const name = document.createElement('span');
      name.textContent = BANDS[i];

      const w = document.createElement('button');
      w.className = 'w';
      w.textContent = weight === 2 ? '×2' : '×1';
      w.title = weight === 2 ? 'Doppelte Gewichtung aktiv — klicken für einfach'
                             : 'Einfache Gewichtung — klicken für doppelt';
      w.addEventListener('click', () => {
        state.selected.set(i, weight === 2 ? 1 : 2);
        renderChosen(); render();
      });

      const x = document.createElement('button');
      x.className = 'x';
      x.textContent = '×';
      x.title = 'Entfernen';
      x.addEventListener('click', () => {
        state.selected.delete(i);
        renderChosen(); renderBandResults(); render();
      });

      li.append(name, w, x);
      list.append(li);
    }
  }

  /* ---------------- Treffer ---------------- */

  const fmtDate = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}.${m}.${y}`;
  };

  function dateLabel(row) {
    if (!row[FROM]) return row[NOTE] || 'Termin offen';
    return row[TO] && row[TO] !== row[FROM]
      ? `${fmtDate(row[FROM])} – ${fmtDate(row[TO])}`
      : fmtDate(row[FROM]);
  }

  function priceLabel(row) {
    if (row[EUR] === 0) return 'Eintritt frei';
    if (row[EUR] == null) return row[PRICE_RAW] || 'Preis unbekannt';
    const eur = `${row[EUR].toLocaleString('de-DE', { minimumFractionDigits: 2 })} €`;
    const raw = (row[PRICE_RAW] || '').trim();
    return /^(ab )?(EUR|€)/i.test(raw) ? `ab ${eur}` : `ab ${eur} (${raw})`;
  }

  function render() {
    const pool = filtered();
    const total = state.selected.size
      ? [...state.selected.values()].reduce((a, b) => a + b, 0) : 0;

    $('filter-stat').innerHTML =
      `<b>${pool.length.toLocaleString('de-DE')}</b> von ${F.length.toLocaleString('de-DE')} Festivals passen zu Umkreis, Preis und Zeitraum.` +
      (state.home ? '' : ' <i>Ohne Wohnort wird nicht nach Entfernung gefiltert.</i>');

    const list = $('festival-list');
    list.innerHTML = '';

    if (!total) {
      $('result-stat').textContent = 'Wähle mindestens eine Band.';
      map.pins = [];
      map.hover = -1;
      drawMap();
      return;
    }

    const scored = [];
    for (const i of pool) {
      const row = F[i], set = sets[i];
      let weight = 0;
      const hits = [];
      for (const [b, w] of state.selected) {
        if (set.has(b)) { weight += w; hits.push([b, w]); }
      }
      if (!weight) continue;
      scored.push({ i, row, pct: (weight / total) * 100, hits, dist: distanceOf(row) });
    }

    scored.sort((a, b) =>
      b.pct - a.pct ||
      (a.dist ?? Infinity) - (b.dist ?? Infinity) ||
      (a.row[EUR] ?? Infinity) - (b.row[EUR] ?? Infinity) ||
      a.row[NAME].localeCompare(b.row[NAME], 'de'));

    $('result-stat').innerHTML = scored.length
      ? `<b>${scored.length}</b> ${scored.length === 1 ? 'Festival spielt' : 'Festivals spielen'} ` +
        (state.selected.size === 1
          ? 'deine gewählte Band'
          : `mindestens eine deiner ${state.selected.size} Bands`) +
        '. Sortiert nach Übereinstimmung, dann Entfernung, dann Preis.'
      : 'Keines der gefilterten Festivals spielt eine deiner Bands. Radius, Preis oder Zeitraum lockern.';

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
      li.textContent = `… ${scored.length - 300} weitere Treffer ausgeblendet. Filter enger stellen.`;
      list.append(li);
    }
  }

  function card(s) {
    const row = s.row;
    const li = document.createElement('li');
    li.className = 'fest' + (s.pct >= 50 ? ' top' : '');
    li.id = s.cardId;

    const head = document.createElement('div');
    head.className = 'fest-head';

    const h3 = document.createElement('h3');
    if (row[WEB]) {
      const a = document.createElement('a');
      a.href = row[WEB]; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = row[NAME];
      a.title = `Offizielle Seite von ${row[NAME]} in neuem Tab öffnen — dort stehen `
              + 'die verbindlichen Termine, Preise und Tickets.';
      h3.append(a);
    } else h3.textContent = row[NAME];

    const pct = document.createElement('div');
    pct.className = 'pct';
    pct.textContent = `${s.pct.toFixed(0)} %`;
    const small = document.createElement('small');
    small.textContent = 'Übereinstimmung';
    pct.append(small);

    const titleBox = document.createElement('div');
    titleBox.append(h3);
    head.append(titleBox, pct);

    const facts = document.createElement('ul');
    facts.className = 'facts';
    const place = [row[VENUE], row[CITY], row[LAND]].filter(Boolean).join(', ');
    const items = [
      ['Termin', dateLabel(row)],
      ['Preis', priceLabel(row)],
      ['Ort', place || 'unbekannt'],
      ['Entfernung', s.dist === null
        ? (state.home ? 'unbekannt' : '— (kein Wohnort gesetzt)')
        : `${s.dist.toLocaleString('de-DE')} km`],
    ];
    for (const [k, v] of items) {
      const el = document.createElement('li');
      el.innerHTML = `${k}: <b></b>`;
      el.querySelector('b').textContent = v;
      facts.append(el);
    }
    if (row[WEB]) {
      const el = document.createElement('li');
      const a = document.createElement('a');
      a.href = row[WEB]; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = 'Offizielle Webseite';
      a.title = `Offizielle Seite von ${row[NAME]} in neuem Tab öffnen.`;
      el.append(a);
      facts.append(el);
    }

    const hits = document.createElement('p');
    hits.className = 'hits';
    const hitNames = s.hits
      .sort((a, b) => b[1] - a[1] || BANDS[a[0]].localeCompare(BANDS[b[0]], 'de'));
    hits.append(document.createTextNode('Deine Bands: '));
    hitNames.forEach(([b, w], n) => {
      const span = document.createElement('span');
      span.className = 'hit' + (w === 2 ? ' dbl' : '');
      span.textContent = BANDS[b];
      span.title = w === 2
        ? `${BANDS[b]} zählt doppelt (gelb hervorgehoben).`
        : `${BANDS[b]} zählt einfach.`;
      hits.append(span);
      if (n < hitNames.length - 1) hits.append(document.createTextNode(', '));
    });

    const det = document.createElement('details');
    det.className = 'lineup';
    const sum = document.createElement('summary');
    sum.textContent = `Komplettes Lineup (${row[LINEUP].length} Acts)`;
    sum.title = 'Aufklappen zeigt alle bestätigten Acts dieses Festivals. '
              + 'Deine gewählten Bands sind grün hervorgehoben.';
    const all = document.createElement('div');
    all.className = 'all';
    const chosenIdx = new Set(s.hits.map((h) => h[0]));
    const names = row[LINEUP].map((b) => [BANDS[b], chosenIdx.has(b)])
      .sort((a, b) => a[0].localeCompare(b[0], 'de'));
    names.forEach(([n, isHit], k) => {
      const el = document.createElement(isHit ? 'mark' : 'span');
      el.textContent = n;
      all.append(el);
      if (k < names.length - 1) all.append(document.createTextNode(' · '));
    });
    if (!names.length) all.textContent = 'Für dieses Festival ist noch kein Lineup veröffentlicht.';
    det.append(sum, all);

    li.append(head, facts, hits, det);
    return li;
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
      back.textContent = '← zurück zur Suche';
      back.title = 'Schließt den Rechtstext und kehrt zur Festivalsuche zurück.';
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

    const today = new Date().toISOString().slice(0, 10);
    $('from').value = today;
    state.from = today;

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

    $('from').addEventListener('change', (e) => { state.from = e.target.value; render(); });

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

    $('build-info').textContent =
      `Datenstand ${fmtDate(D.generated)} · ${F.length.toLocaleString('de-DE')} Festivals · ` +
      `${BANDS.length.toLocaleString('de-DE')} Acts.`;

    initMap();
    initLegal();
    renderBandResults();
    renderChosen();
    render();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
