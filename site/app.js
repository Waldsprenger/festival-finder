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

    // 1. Mitgeliefertes Ortsverzeichnis (GeoNames). Es ist nach Einwohnerzahl
    //    sortiert, der erste Treffer ist also der bekannteste gleichen Namens.
    const needle = fold(q);
    let prefix = null;
    for (const [name, lat, lon, cc] of D.places) {
      const f = fold(name);
      if (f === needle) return { lat, lon, label: `${name} (${cc})`, online: false };
      if (!prefix && f.startsWith(needle)) prefix = { lat, lon, label: `${name} (${cc})`, online: false };
    }
    if (prefix) return prefix;

    // 2. Nur wenn lokal nichts passt: Nominatim (OpenStreetMap).
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
    if (!hit) {
      state.home = null;
      status.className = 'hint err';
      status.textContent = 'Ort nicht gefunden. Andere Schreibweise probieren.';
    } else {
      state.home = hit;
      status.className = 'hint ok';
      status.textContent = `${hit.label} — Umkreissuche aktiv.`;
    }
    render();
  }

  /* ---------------- Karte ----------------
     Gezeichnet wird auf Canvas aus mitgelieferten Vektorgrenzen. Kartenkacheln
     fremder Server sind in der veröffentlichten Fassung blockiert — und eine
     eigene Zeichnung verrät niemandem, wo jemand sucht. */

  const map = {
    canvas: null, ctx: null, view: null, pins: [], hover: -1,
  };

  // Mittabstandstreue Zylinderprojektion, an der Bildmitte ausgerichtet.
  // Für Ausschnitte bis ~2000 km ist die Verzerrung vernachlässigbar.
  function makeView(centerLat, centerLon, spanKm, w, h) {
    const kmPerDegLat = 111.32;
    const kmPerDegLon = kmPerDegLat * Math.cos(centerLat * Math.PI / 180);
    const aspect = w / h;
    let halfKmY = spanKm, halfKmX = spanKm * aspect;
    return {
      w, h, centerLat, centerLon,
      x: (lon) => w / 2 + ((lon - centerLon) * kmPerDegLon) / halfKmX * (w / 2),
      y: (lat) => h / 2 - ((lat - centerLat) * kmPerDegLat) / halfKmY * (h / 2),
      kmToPxY: (km) => (km / halfKmY) * (h / 2),
    };
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

    // Ausschnitt: um den Wohnort herum etwas mehr als der Radius,
    // ohne Wohnort ganz Europa
    const v = state.home
      ? makeView(state.home.lat, state.home.lon, state.radius * 1.35, w, h)
      : makeView(52.5, 12.0, 2100, w, h);
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

    if (!state.home) {
      $('map-caption').textContent = 'Wohnort eingeben, um den Suchradius zu sehen.';
      map.pins = [];
      return;
    }

    // Radiuskreis: als Punktfolge in echter Entfernung, nicht als Ellipse
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
    ctx.strokeStyle = '#6ec36e';
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.moveTo(hx - 7, hy); ctx.lineTo(hx + 7, hy);
    ctx.moveTo(hx, hy - 7); ctx.lineTo(hx, hy + 7);
    ctx.stroke();

    // Maßstab
    const stepKm = state.radius >= 800 ? 500 : state.radius >= 200 ? 100 : 25;
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
    if (!map.pins.length) {
      cap.textContent = `Umkreis ${state.radius.toLocaleString('de-DE')} km um ${state.home.label}. ` +
        'Nach der Bandauswahl erscheinen hier die passenden Festivals.';
    } else {
      const hovered = map.hover >= 0 ? map.pins[map.hover] : null;
      cap.textContent = hovered
        ? `${hovered.name} — ${hovered.pct.toFixed(0)} % Übereinstimmung, ${hovered.dist} km`
        : `${map.pins.length} Festival${map.pins.length === 1 ? '' : 's'} im Umkreis von ` +
          `${state.radius.toLocaleString('de-DE')} km um ${state.home.label}. Pin anklicken springt zum Eintrag.`;
    }
  }

  function initMap() {
    map.canvas = $('map');
    if (!map.canvas) return;
    map.ctx = map.canvas.getContext('2d');

    map.canvas.addEventListener('mousemove', (e) => {
      const r = map.canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
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
      if (map.hover < 0) return;
      const card = document.getElementById(map.pins[map.hover].cardId);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('flash');
        setTimeout(() => card.classList.remove('flash'), 1600);
      }
    });

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
      ? `<b>${scored.length}</b> ${scored.length === 1 ? 'Festival spielt' : 'Festivals spielen'} mindestens eine deiner ` +
        `${state.selected.size} ${state.selected.size === 1 ? 'Band' : 'Bands'}. ` +
        'Sortiert nach Übereinstimmung, dann Entfernung, dann Preis.'
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

  /* ---------------- Verdrahtung ---------------- */

  function init() {
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
    renderBandResults();
    renderChosen();
    render();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
