/* Festival Finder — Sprache, Filter, Auswahl, Trefferliste.

   Läuft ohne Server; die Daten liegen in data.js als window.DATA, die
   Übersetzungen in i18n.js, die Landkarte in karte.js. */

(() => {
  'use strict';

  const D = window.DATA;
  if (!D || !Array.isArray(D.festivals)) {
    // data.js ist sechs Megabyte gross. Bleibt sie unterwegs haengen, stand
    // hier bisher ein Absturz in der zweiten Zeile - die Seite blieb leer,
    // ohne ein Wort dazu. Jetzt sagt sie, was los ist.
    const sagen = () => {
      const texte = (window.I18N && window.I18N.TEXTE['app.noData']) || {};
      const kurz = (navigator.language || 'de').slice(0, 2);
      const hinweis = document.createElement('p');
      hinweis.className = 'hint err';
      hinweis.style.margin = '2rem';
      hinweis.textContent = texte[kurz] || texte.de ||
        'Die Festivaldaten konnten nicht geladen werden. Bitte neu laden.';
      (document.querySelector('main') || document.body).prepend(hinweis);
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', sagen);
    } else {
      sagen();
    }
    return;
  }
  const F = D.festivals;
  const BANDS = D.bands;
  // Schlüssel der Genre-Oberbegriffe; die Namen stehen übersetzt in i18n.js
  const GENRES = D.genres || [];

  // Spaltenindizes von data.js
  const NAME = 0, FROM = 1, TO = 2, CITY = 3, LAND = 4, VENUE = 5,
        EUR = 6, PRICE_RAW = 7, WEB = 8, LAT = 9, LON = 10, LINEUP = 11,
        NOTE = 12, CANCELLED = 13, GENRE_IDS = 14, PRICE_START = 15;

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

  /** Zahlen, die in Hilfetexten vorkommen — aus den Daten statt aus dem Text.

      Eine Zahl im Hilfetext veraltet still: "rund 450 Festivals ohne Preis"
      stand in zehn Sprachen da, während es längst dreimal so viele waren. */
  function hilfszahlen() {
    const zahl = (n) => n.toLocaleString(sprache);
    return {
      ohnePreis: zahl(F.reduce((n, r) => n + (r[EUR] === null ? 1 : 0), 0)),
      ohneGenre: zahl(F.reduce((n, r) => n + ((r[GENRE_IDS] || []).length ? 0 : 1), 0)),
    };
  }

  /** Trägt alle ausgezeichneten Texte im Dokument neu ein. */
  function spracheAnwenden() {
    document.documentElement.lang = sprache;
    const zahlen = hilfszahlen();
    for (const el of document.querySelectorAll('[data-i18n]')) {
      el.textContent = t(el.dataset.i18n);
    }
    for (const el of document.querySelectorAll('[data-i18n-html]')) {
      el.innerHTML = t(el.dataset.i18nHtml);
    }
    for (const el of document.querySelectorAll('[data-i18n-title]')) {
      el.title = t(el.dataset.i18nTitle, zahlen);
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
    // Sortierung je Filterart, damit ein Wechsel die eigene Wahl behält
    sort: { bands: 'match', genre: 'date', off: 'distance' },
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

  /* Dieselben Regeln wie fold() in scraper/text.py — die Suche soll Namen
     genauso zusammenfassen wie die Daten selbst. Vorher unterschieden sich
     beide bei jedem achten Bandnamen: Wer "2 Engel and Charlie" tippte, fand
     "2 Engel & Charlie" nicht, obwohl es für die Daten dieselbe Band ist.
     Wird hier etwas geändert, gehört es auch dorthin. */
  const SONDERZEICHEN = [['ß', 'ss'], ['ø', 'o'], ['æ', 'ae'], ['œ', 'oe'],
                         ['đ', 'd'], ['ħ', 'h'], ['ł', 'l'], ['ı', 'i'],
                         ['þ', 'th'], ['ð', 'd']];
  const foldCache = new Map();
  const fold = (s) => {
    let v = foldCache.get(s);
    if (v === undefined) {
      v = s.toLowerCase().normalize('NFKD').replace(/\p{M}+/gu, '');
      for (const [a, b] of SONDERZEICHEN) v = v.split(a).join(b);
      v = v.replace(/[&+]/g, ' and ').replace(/[’´`]/g, "'")
           .replace(/[–—]/g, '-').replace(/…/g, '')
           .replace(/\b(feat|ft|featuring|vs|with|und|and)\b/g, ' and ')
           .replace(/[^\p{L}\p{N}]+/gu, ' ')
           .replace(/\s+/g, ' ').trim()
           .replace(/^(the|die|der|das|los|las|les) /, '')
           .replace(/ (band|live|dj ?set|djset|acoustic)$/, '');
      foldCache.set(s, v);
    }
    return v;
  };
  const bandsFolded = BANDS.map(fold);

  /* Kuerzel und Zweitschreibweisen: In den Daten steht der ausgeschriebene
     Name, gesucht wird aber auch nach der Abkuerzung. "TBS" führt deshalb zu
     The Butcher Sisters - angezeigt wird immer der ausgeschriebene Name, mit
     dem Kürzel als Hinweis dahinter. */
  const ALIAS = (D.bandAlias || []).map(([text, i]) => [fold(text), text, i]);
  const aliasVonBand = new Map();
  for (const [, text, i] of ALIAS) {
    if (!aliasVonBand.has(i)) aliasVonBand.set(i, []);
    aliasVonBand.get(i).push(text);
  }

  /* ---------------- Umkreis ----------------
     Der Regler zeigt Kilometer, laeuft aber logarithmisch: Weltweit reicht
     der Umkreis bis 20.000 km, gesucht wird fast immer unter 500. Linear
     laegen diese ersten 500 km in den ersten zweieinhalb Prozent des Weges. */

  const UMKREIS_MIN = 10;
  const reglerMax = () => Math.max(100, D.maxDistanceKm || 3300);

  /** Reglerstellung (0..1000) → Kilometer, auf runde Werte gebracht. */
  function stellungZuKm(p) {
    const roh = UMKREIS_MIN * Math.pow(reglerMax() / UMKREIS_MIN, p / 1000);
    const schritt = roh < 200 ? 10 : roh < 1000 ? 50 : roh < 5000 ? 100 : 500;
    return Math.min(reglerMax(), Math.round(roh / schritt) * schritt) || UMKREIS_MIN;
  }

  /** Kilometer → Reglerstellung, für die Voreinstellung und geteilte Links. */
  function kmZuStellung(km) {
    const wert = Math.min(Math.max(km, UMKREIS_MIN), reglerMax());
    return Math.round(1000 * Math.log(wert / UMKREIS_MIN) /
                      Math.log(reglerMax() / UMKREIS_MIN));
  }

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

  /* Das mitgelieferte Verzeichnis deckt DE/AT/CH vollständig ab und das
     übrige Welt ab 15.000 Einwohnern. Alles darunter steht in site/orte.js
     und wird erst geholt, wenn jemand danach sucht - als <script>, damit es
     auch beim Öffnen per Doppelklick (file://) funktioniert, wo fetch()
     scheitert. In der gebündelten Einzelseite gibt es die Datei nicht; dort
     bleibt es beim kleinen Verzeichnis. */
  let europaVerzeichnis = null;

  function grossesOrtsverzeichnis() {
    if (europaVerzeichnis) return europaVerzeichnis;
    europaVerzeichnis = new Promise((fertig) => {
      if (window.ORTE_WELT) return fertig(window.ORTE_WELT);
      // Die Datei setzt window.ORTE_WELT = {orte, plz}
      const skript = document.createElement('script');
      skript.src = 'orte.js';
      skript.onload = () => fertig(window.ORTE_WELT || null);
      skript.onerror = () => fertig(null);
      document.head.append(skript);
    });
    return europaVerzeichnis;
  }

  /** Postleitzahl im nachgeladenen Verzeichnis, sonst null. */
  async function plzNachladen(code, land) {
    const europa = await grossesOrtsverzeichnis();
    const treffer = (europa && europa.plz || []).filter(
      (p) => p[0] === code && (!land || fold(p[4]) === land));
    if (!treffer.length) return null;
    const pick = treffer[0];
    const andere = treffer.filter((p) => p[4] !== pick[4]).map((p) => p[4]);
    return {
      lat: pick[2], lon: pick[3],
      label: `${pick[0]} ${pick[1]} (${pick[4]})`,
      ambiguous: andere.length ? andere : null,
    };
  }

  /** Einen Ortsnamen in einem Verzeichnis suchen: genau, sonst am Wortanfang. */
  function ortSuchen(verzeichnis, needle) {
    let exact = null, prefix = null, weitere = 0;
    for (const [name, lat, lon, cc] of verzeichnis) {
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
    if (!treffer) return null;
    if (exact && prefix) weitere++;
    if (weitere) treffer.ambiguousName = weitere;
    return treffer;
  }

  async function geocode(query) {
    const q = query.trim();
    if (!q) return null;

    // 1. Postleitzahl - die eindeutigste Eingabe. Erlaubt sind "97209",
    //    "97209 Veitshöchheim" und "1010 AT" zur Trennung von AT und CH.
    const pm = q.match(/^\s*(\d{4,5})\b\s*([A-Za-zÄÖÜäöü].*)?$/);
    if (pm) {
        const code = pm[1];
        const rest = fold(pm[2] || '');
        // "1012 NL" nennt ein Land, "1012 AB" ist eine niederländische
        // Postleitzahl, "97209 Veitshöchheim" nennt den Ort.
        const laender = new Set((D.laender || []).map((c) => c.toLowerCase()));
        const genanntesLand = laender.has(rest) ? rest : '';
        // "1012 AB" ist eine niederländische Postleitzahl, keine Ortsangabe -
        // dafür ist Nominatim zuständig, unsere Tabelle führt nur die Zahl.
        const buchstabenteil = !genanntesLand && /^[a-z]{1,3}$/.test(rest);
        let hits = buchstabenteil ? [] : (D.plz || []).filter((p) => p[0] === code);
        if (genanntesLand) hits = hits.filter((p) => fold(p[4]) === genanntesLand);
        if (hits.length) {
            let pick = hits[0];
            if (rest && !genanntesLand) {
                pick = hits.find((p) => fold(p[1]).startsWith(rest)) || pick;
            }
            const andere = hits.filter((p) => p[4] !== pick[4]).map((p) => p[4]);
            return {
                lat: pick[2], lon: pick[3],
                label: `${pick[0]} ${pick[1]} (${pick[4]})`,
                ambiguous: andere.length ? andere : null,
            };
        }
        // Mitgeliefert sind die Postleitzahlen von DE/AT/CH. Für die übrigen
        // Länder liegt die Tabelle in orte.js und wird jetzt nachgeladen.
        if (!buchstabenteil) {
          const fern = await plzNachladen(code, genanntesLand);
          if (fern) return fern;
        }
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

    // 3. Kleinerer Ort irgendwo auf der Welt: das große Verzeichnis
    //    dieselbe Suche noch einmal führen.
    const europa = await grossesOrtsverzeichnis();
    if (europa && europa.orte) {
      const weiterer = ortSuchen(europa.orte, needle);
      if (weiterer) return weiterer;
    }

    // 4. Nur wenn auch dort nichts passt: Nominatim (OpenStreetMap).
    //    In der eingebetteten Fassung blockiert die Sicherheitsrichtlinie
    //    externe Aufrufe - dann bleibt es bei den Schritten davor.
    //    Eine Postleitzahl wird strukturiert gefragt: Als Freitext lieferte
    //    "1012 NL" die Hausnummer "42-1012" irgendwo.
    const felder = new URLSearchParams({ format: 'jsonv2', limit: '1',
                                         'accept-language': sprache });
    if (pm) {
      const rest = (pm[2] || '').trim();
      const laender = new Set((D.laender || []).map((c) => c.toLowerCase()));
      if (laender.has(fold(rest))) {
        felder.set('postalcode', pm[1]);
        felder.set('countrycodes', fold(rest));
      } else if (/^[A-Za-z]{1,3}$/.test(rest)) {
        // Der Buchstabenteil gehört zur Postleitzahl ("1012 AB", "SW1A 1AA")
        felder.set('postalcode', `${pm[1]} ${rest.toUpperCase()}`);
      } else {
        felder.set('postalcode', pm[1]);
        if (rest) felder.set('city', rest);
      }
    } else {
      felder.set('q', q);
    }
    try {
      const res = await fetch('https://nominatim.openstreetmap.org/search?' + felder,
                              { headers: { Accept: 'application/json' } });
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

    // Wer eine Postleitzahl eingegeben hat, soll das auch hören - "Ort nicht
    // gefunden" führt sonst auf die falsche Fährte.
    return pm ? { notFound: pm[1] } : null;
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
    KARTE.zentrieren();
    render();
    KARTE.zeichnen();
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
      // Der Zeitraum zählt, nicht der Beginn: Ein Festival, das gestern
      // angefangen hat und bis Sonntag läuft, ist heute noch zu erreichen.
      // Vorher fielen an einem beliebigen Tag rund hundert laufende
      // Veranstaltungen aus der Liste, weil die Vorgabe "ab heute" lautet.
      const ende = row[TO] || row[FROM];
      if (state.from && ende < state.from) return false;
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
    // Kürzel zählen wie ein Namenstreffer, doppelte fallen weg
    for (const [gefaltet, , i] of ALIAS) {
      const pos = gefaltet.indexOf(term);
      if (pos < 0) continue;
      if (!starts.includes(i) && !contains.includes(i)) {
        (pos === 0 ? starts : contains).push(i);
      }
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
      if (aliasVonBand.has(i)) {
        const kurz = document.createElement('span');
        kurz.className = 'alias';
        kurz.textContent = t('bands.alsoKnown', { kurz: aliasVonBand.get(i).join(', ') });
        label.append(kurz);
      }
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

  /** Preisangabe einer Karte — heutiger Stand, davor der Startpreis.

      Die Quellen nennen fast immer den Preis zum Verkaufsstart. Ändert eine
      Quelle ihn, merkt sich der Datenlauf beides: Angezeigt wird dann der
      heutige Preis, der erste beobachtete steht in Klammern dahinter. */
  function priceLabel(row) {
    const start = (row[PRICE_START] || '').trim();
    const seit = start ? ` (${t('card.priceStart')} ${start})` : '';
    if (row[EUR] === 0) return t('card.free') + seit;

    const raw = (row[PRICE_RAW] || '').trim();
    if (row[EUR] == null) return (raw || t('card.priceUnknown')) + seit;

    const eur = `${row[EUR].toLocaleString(sprache, { minimumFractionDigits: 2 })} €`;
    // Fremde Währung: umgerechnet zeigen, den Originalpreis dahinter.
    if (FREMDWAEHRUNG.test(raw)) return `${t('card.from')} ${eur} (${raw})` + seit;
    // Sonst den Quelltext nur zeigen, wenn er mehr sagt als die Zahl selbst.
    return (preisZusatz(raw) ? raw : `${t('card.from')} ${eur}`) + seit;
  }

  //: Währungen, die erst umgerechnet vergleichbar sind
  const FREMDWAEHRUNG = /\b(CHF|GBP|USD|DKK|SEK|NOK|PLN|CZK|HUF)\b|£|\$/i;

  /** Was bleibt vom Preistext, wenn Betrag, Währung und "ab" weg sind?

      "ab 12,90 Eur" sagt nichts, was die Zahl nicht schon sagt — angezeigt
      wurde daraus "ab 12,90 € (ab 12,90 Eur)", zweimal dasselbe. "VVK 22,50 €
      | AK 24 €" dagegen trägt zwei Preise und gehört im Wortlaut auf die
      Karte. */
  function preisZusatz(raw) {
    return raw
      .replace(/\d+(?:[.,]\d+)?/g, ' ')
      .replace(/€|\bEUR\b|\bab\b|\bfrom\b/gi, ' ')
      .replace(/[^\p{L}]+/gu, ' ')
      .trim();
  }

  /* ---------------- Sortierung ----------------
     Die Voreinstellung folgt dem Filter: Mit Bandauswahl zählt zuerst die
     Übereinstimmung, mit Genreauswahl der Termin — ein Genre trifft auf
     Hunderte Festivals zu, da hilft die Prozentzahl beim Ordnen wenig.
     Wählbar ist unabhängig davon Entfernung, Preis oder Datum. */

  const SORTIERUNGEN = {
    bands: ['match', 'distance', 'price', 'date'],
    genre: ['date', 'distance', 'price'],
    off: ['distance', 'date', 'price'],
  };

  /** Aktuell gewählte Sortierung; unbekannte Wahl fällt auf die erste zurück. */
  function sortierung() {
    const erlaubt = SORTIERUNGEN[state.mode];
    const wahl = state.sort[state.mode];
    return erlaubt.includes(wahl) ? wahl : erlaubt[0];
  }

  // Fehlende Angaben ans Ende, egal wonach sortiert wird: Ein Festival ohne
  // Preis ist nicht das günstigste, eines ohne Termin nicht das nächste.
  const km = (e) => e.dist ?? Infinity;
  const eur = (e) => e.row[EUR] ?? Infinity;
  const tag = (e) => e.row[FROM] || '9999-99-99';
  const pct = (e) => (e.pct === null ? -1 : e.pct);

  function vergleicher() {
    const name = (a, b) => a.row[NAME].localeCompare(b.row[NAME], sprache);
    const datum = (a, b) => tag(a).localeCompare(tag(b));
    switch (sortierung()) {
      case 'distance':
        return (a, b) => km(a) - km(b) || datum(a, b) || eur(a) - eur(b) || name(a, b);
      case 'price':
        return (a, b) => eur(a) - eur(b) || km(a) - km(b) || datum(a, b) || name(a, b);
      case 'date':
        return (a, b) => datum(a, b) || km(a) - km(b) || eur(a) - eur(b) || name(a, b);
      default:                                   // 'match'
        return (a, b) => pct(b) - pct(a) || km(a) - km(b) || datum(a, b) ||
                         eur(a) - eur(b) || name(a, b);
    }
  }

  /** Baut die Auswahlliste passend zum Filter neu auf. */
  function renderSortierung() {
    const wahl = $('sort');
    if (!wahl) return;
    const aktiv = sortierung();
    wahl.innerHTML = '';
    for (const key of SORTIERUNGEN[state.mode]) {
      const o = document.createElement('option');
      o.value = key;
      o.textContent = t('sort.' + key);
      wahl.append(o);
    }
    wahl.value = aktiv;
    state.sort[state.mode] = aktiv;
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
      KARTE.setzePins([]);
      KARTE.zeichnen();
      return;
    }
    if (state.mode === 'genre' && !state.genres.size) {
      $('result-stat').textContent = t('res.needGenre');
      KARTE.setzePins([]);
      KARTE.zeichnen();
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

    scored.sort(vergleicher());

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

    treffer = scored.slice(0, 300);
    treffer.forEach((s, n) => { s.eintragId = `fest-${n}`; });
    gezeigt = stapel();
    listeZeichnen();

    KARTE.setzePins(treffer
      .filter((s) => s.row[LAT] != null)
      .map((s) => ({
        lat: s.row[LAT], lon: s.row[LON], name: s.row[NAME],
        pct: s.pct, dist: s.dist, eintragId: s.eintragId, px: 0, py: 0,
      })));
    KARTE.zeichnen();

    if (scored.length > 300) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = t('res.more', { n: scored.length - 300 });
      list.append(li);
    }
  }

  /* Nur die ersten Treffer zeichnen und auf Wunsch nachlegen. Alle 300 auf
     einmal ergaben am Telefon eine Seite von 109.000 Pixeln Hoehe - über
     hundert Bildschirme, die niemand durchwischt, und jede Karte kostet
     Aufbauzeit. */
  // Am Telefon ein kleinerer Stapel als am Rechner: dort zaehlt jede Karte
  // Aufbauzeit und Wischweg, hier passt mehr auf einen Blick.
  const stapel = () => (window.innerWidth < 620 ? 25 : 50);
  let treffer = [];
  let gezeigt = stapel();

  function listeZeichnen() {
    const list = $('festival-list');
    const bisher = list.querySelectorAll('.fest').length;
    const mehrKnopf = list.querySelector('.mehr');
    if (mehrKnopf) mehrKnopf.remove();

    const frag = document.createDocumentFragment();
    for (let n = bisher; n < Math.min(gezeigt, treffer.length); n++) {
      frag.append(eintragKarte(treffer[n]));
    }
    list.append(frag);

    if (gezeigt < treffer.length) {
      const li = document.createElement('li');
      li.className = 'mehr';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ghost';
      btn.textContent = t('res.showMore', {
        n: Math.min(stapel(), treffer.length - gezeigt),
        rest: treffer.length - gezeigt,
      });
      btn.addEventListener('click', () => { gezeigt += stapel(); listeZeichnen(); });
      li.append(btn);
      list.append(li);
    }
  }

  /** Sorgt dafür, dass ein Eintrag gezeichnet ist — etwa nach einem Klick auf
      einen Kartenpin, dessen Eintrag noch im Nachschub steckt. */
  function eintragZeigen(eintragId) {
    const stelle = treffer.findIndex((s) => s.eintragId === eintragId);
    if (stelle >= gezeigt) {
      gezeigt = Math.ceil((stelle + 1) / stapel()) * stapel();
      listeZeichnen();
    }
    return $(eintragId);
  }

  function eintragKarte(s) {
    const row = s.row;
    const li = document.createElement('li');
    li.className = 'fest' + (s.pct !== null && s.pct >= 50 ? ' top' : '') +
                   (row[CANCELLED] ? ' cancelled' : '');
    li.id = s.eintragId;

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
    // Der Zustand gehört an den Knopf, sonst kündigt ein Screenreader das
    // Aufklappen nicht an.
    for (const btn of document.querySelectorAll('button.help')) {
      btn.setAttribute('aria-expanded', 'false');
    }
    const box = document.createElement('div');
    box.className = 'help-box';
    box.hidden = true;
    box.setAttribute('role', 'status');
    document.body.append(box);

    let offen = null;

    function schliessen() {
      box.hidden = true;
      if (offen) {
        offen.classList.remove('on');
        offen.setAttribute('aria-expanded', 'false');
      }
      offen = null;
    }

    function oeffnen(btn) {
      box.textContent = btn.getAttribute('title') || '';
      box.hidden = false;
      btn.classList.add('on');
      btn.setAttribute('aria-expanded', 'true');
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
      renderSortierung();
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
    if (D.maxPriceEur) pri.max = String(D.maxPriceEur);
    rad.value = String(kmZuStellung(state.radius));
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
      state.radius = stellungZuKm(+e.target.value);
      $('radius-out').textContent = `${state.radius.toLocaleString('de-DE')} km`;
      KARTE.zeichnen();
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
        renderSortierung();
        render();
      });
    }

    $('sort').addEventListener('change', (e) => {
      state.sort[state.mode] = e.target.value;
      render();
    });

    $('genre-unknown').addEventListener('change', (e) => {
      state.allowUnknownGenre = e.target.checked; render();
    });

    $('clear-genres').addEventListener('click', () => {
      state.genres.clear(); renderGenres(); render();
    });

    // Die beiden Felder begrenzen sich gegenseitig, damit kein leerer
    // Zeitraum entstehen kann.
    /** Erklärt, warum ein Datum zurückgezogen wurde, und warnt vor
     *  Zeiträumen in der Vergangenheit. */
    function datumsHinweis(zuFrueh) {
      const el = $('date-hint');
      const vergangen = (state.from && state.from < today) ||
                        (state.to && state.to < today);
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
    KARTE.start({
      t,
      sprache: () => sprache,
      wohnort: () => state.home,
      umkreis: () => state.radius,
      datenRahmen: () => D.dataBox || null,
      welt: D.world,
      weltFein: D.worldFine,
      fineBox: D.fineBox,
      // Ein Klick auf einen Pin springt zum Eintrag - notfalls muss die Karte
      // dafuer erst nachgezeichnet werden.
      aufPinKlick: (eintragId) => {
        const eintrag = eintragZeigen(eintragId);
        if (!eintrag) return;
        eintrag.scrollIntoView({ behavior: 'smooth', block: 'center' });
        eintrag.classList.add('flash');
        setTimeout(() => eintrag.classList.remove('flash'), 1600);
      },
    });
    initHelp();
    initPwa();
    initZaehler();
    initFeedback();
    initLegal();
    modusAnwenden();
    renderSortierung();
    renderBandResults();
    renderChosen();
    renderGenres();
    render();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
