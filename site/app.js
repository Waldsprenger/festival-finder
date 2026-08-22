/* Festival Finder — die Kette: eine Frage nach der anderen.

   Sechs Schritte bauen sich nacheinander auf (Ort, Zeitraum, Entfernung,
   Preis, Bands, Genre); erst danach stehen die Treffer da. Jeder beantwortete
   Schritt klappt zu einer Zeile zusammen und lässt sich wieder öffnen.

   Läuft ohne Server; die Daten liegen in data.js als window.DATA, die
   Übersetzungen in i18n.js, die Landkarte in karte.js. */

(() => {
  'use strict';

  const D = window.DATA;
  if (!D || !Array.isArray(D.festivals)) {
    // data.js ist neun Megabyte gross. Bleibt sie unterwegs haengen, stand
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

  const zahl = (n) => Number(n).toLocaleString(sprache);

  /** Zahlen, die in Hilfetexten vorkommen — aus den Daten statt aus dem Text.

      Eine Zahl im Hilfetext veraltet still: "rund 450 Festivals ohne Preis"
      stand in zehn Sprachen da, während es längst dreimal so viele waren. */
  function hilfszahlen() {
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

  /* ---------------- Zustand ----------------
     Je Schritt ein Block. `an` sagt, ob dieser Schritt filtert; `antwort`
     sagt, ob die Frage überhaupt schon beantwortet ist. Das sind zwei
     verschiedene Dinge: Eine unbeantwortete Frage sperrt die nächste, eine
     mit "Nein" beantwortete nicht. */

  const KETTE = ['ort', 'zeit', 'entfernung', 'preis', 'bands', 'genre'];

  const state = {
    antwort: {},                 // schritt -> true, sobald beantwortet
    offen: 'ort',                // welcher Schritt gerade aufgeklappt ist

    home: null,                  // {lat, lon, label, land}
    zeit: { von: '', bis: '', minDate: '', ohneTermin: false, abgesagte: false },
    entfernung: { an: false, von: null, bis: null, ohneKoordinate: false },
    preis: { an: false, von: null, bis: null, waehrung: 'EUR', ohnePreis: true },
    bands: { an: false, auswahl: new Map() },   // bandIndex -> Gewicht (1 oder 2)
    genre: { an: false, auswahl: new Set(), ohneGenre: false },

    karte: false,
    // null heisst: noch nicht selbst gewaehlt, es gilt die Vorgabe
    sortierung: null,
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

  /* ---------------- Währung ----------------
     Preisgrenzen darf man in der eigenen Währung eingeben. Verglichen wird
     intern immer in Euro: Die Daten führen einen umgerechneten Eurobetrag,
     und zwei Zahlen in verschiedenen Währungen zu vergleichen wäre falsch. */

  const KURSE = D.kurse || { EUR: 1 };
  const WAEHRUNG_ZEICHEN = { EUR: '€', CHF: 'CHF', GBP: '£', USD: '$',
                             DKK: 'kr.', SEK: 'kr', NOK: 'kr', PLN: 'zł',
                             CZK: 'Kč', HUF: 'Ft' };

  /** Ein Betrag in der gewählten Währung als Eurobetrag. */
  const nachEuro = (betrag) => betrag * (KURSE[state.preis.waehrung] || 1);

  /** Welche Währung gilt an diesem Ort? Ohne bekanntes Land: Euro. */
  function waehrungFuerLand(land) {
    const gefunden = (D.waehrungLand || {})[land];
    return gefunden && KURSE[gefunden] ? gefunden : 'EUR';
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

  /* Das mitgelieferte Verzeichnis deckt DE/AT/CH vollständig ab und die
     übrige Welt ab 15.000 Einwohnern. Alles darunter steht in site/orte.js
     und wird erst geholt, wenn jemand danach sucht - als <script>, damit es
     auch beim Öffnen per Doppelklick (file://) funktioniert, wo fetch()
     scheitert. In der gebündelten Einzelseite gibt es die Datei nicht; dort
     bleibt es beim kleinen Verzeichnis. */
  let weltVerzeichnis = null;

  function grossesOrtsverzeichnis() {
    if (weltVerzeichnis) return weltVerzeichnis;
    weltVerzeichnis = new Promise((fertig) => {
      if (window.ORTE_WELT) return fertig(window.ORTE_WELT);
      // Die Datei setzt window.ORTE_WELT = {orte, plz}
      const skript = document.createElement('script');
      skript.src = 'orte.js';
      skript.onload = () => fertig(window.ORTE_WELT || null);
      skript.onerror = () => fertig(null);
      document.head.append(skript);
    });
    return weltVerzeichnis;
  }

  /** Postleitzahl im nachgeladenen Verzeichnis, sonst null. */
  async function plzNachladen(code, land) {
    const welt = await grossesOrtsverzeichnis();
    const treffer = (welt && welt.plz || []).filter(
      (p) => p[0] === code && (!land || fold(p[4]) === land));
    if (!treffer.length) return null;
    const pick = treffer[0];
    const andere = treffer.filter((p) => p[4] !== pick[4]).map((p) => p[4]);
    return {
      lat: pick[2], lon: pick[3], land: pick[4],
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
        exact = { lat, lon, land: cc, label: `${name} (${cc})` };
      } else if (f.startsWith(needle)) {
        if (prefix) { weitere++; continue; }
        prefix = { lat, lon, land: cc, label: `${name} (${cc})` };
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
          lat: pick[2], lon: pick[3], land: pick[4],
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
    const treffer = ortSuchen(D.places, needle);
    if (treffer) return treffer;

    // 3. Kleinerer Ort irgendwo auf der Welt: dieselbe Suche im großen
    //    Verzeichnis.
    const welt = await grossesOrtsverzeichnis();
    if (welt && welt.orte) {
      const weiterer = ortSuchen(welt.orte, needle);
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
            land: '',
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

  async function ortSetzen() {
    const status = $('home-status');
    const q = $('home').value;
    if (!q.trim()) {
      status.className = 'hint err';
      status.textContent = t('home.statusStart');
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
      zeichnen();
      return;
    }
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

    // Die Währung folgt dem Wohnort, solange niemand selbst gewählt hat.
    if (!state.preis.gewaehlt) {
      state.preis.waehrung = waehrungFuerLand(hit.land);
      waehrungAnwenden();
    }
    KARTE.zentrieren();
    beantworten('ort');
  }

  /* ---------------- Filter ----------------
     Je Schritt ein Prädikat. So lässt sich ausrechnen, wie viele Festivals
     nach jedem einzelnen Schritt noch übrig sind - ohne diese Zahl klickt man
     sechs Fragen durch, ohne zu sehen, was sie bewirken. */

  const PRUEFUNG = {
    // Der Wohnort filtert nicht, er misst nur.
    ort: () => true,

    zeit(row) {
      if (row[CANCELLED] && !state.zeit.abgesagte) return false;
      if (!row[FROM]) return state.zeit.ohneTermin;
      // Der Zeitraum zählt, nicht der Beginn: Ein Festival, das gestern
      // angefangen hat und bis Sonntag läuft, ist heute noch zu erreichen.
      const ende = row[TO] || row[FROM];
      if (state.zeit.von && ende < state.zeit.von) return false;
      if (state.zeit.bis && row[FROM] > state.zeit.bis) return false;
      return true;
    },

    entfernung(row) {
      const e = state.entfernung;
      if (!e.an || !state.home) return true;
      const d = distanceOf(row);
      if (d === null) return e.ohneKoordinate;
      if (e.von !== null && d < e.von) return false;
      if (e.bis !== null && d > e.bis) return false;
      return true;
    },

    preis(row) {
      const p = state.preis;
      if (!p.an) return true;
      const wert = row[EUR];
      if (wert === null) return p.ohnePreis;
      if (p.von !== null && wert < nachEuro(p.von)) return false;
      if (p.bis !== null && wert > nachEuro(p.bis)) return false;
      return true;
    },

    bands(row, i) {
      if (!state.bands.an || !state.bands.auswahl.size) return true;
      for (const b of state.bands.auswahl.keys()) if (sets[i].has(b)) return true;
      return false;
    },

    genre(row) {
      if (!state.genre.an || !state.genre.auswahl.size) return true;
      const eigene = row[GENRE_IDS] || [];
      if (!eigene.length) return state.genre.ohneGenre;
      return eigene.some((g) => state.genre.auswahl.has(g));
    },
  };

  /** Wie viele Festivals überstehen die Schritte bis einschließlich `name`? */
  function uebrig(name) {
    const bis = KETTE.indexOf(name);
    const pruefungen = KETTE.slice(0, bis + 1).map((n) => PRUEFUNG[n]);
    let n = 0;
    for (let i = 0; i < F.length; i++) {
      if (pruefungen.every((p) => p(F[i], i))) n++;
    }
    return n;
  }

  /** Die Zeilennummern, die alle Schritte überstehen. */
  function gefiltert() {
    const raus = [];
    for (let i = 0; i < F.length; i++) {
      if (KETTE.every((n) => PRUEFUNG[n](F[i], i))) raus.push(i);
    }
    return raus;
  }

  /* ---------------- Die Kette ---------------- */

  const sektion = (name) => document.querySelector(`[data-schritt="${name}"]`);

  /** Kurzfassung eines beantworteten Schritts — was gerade gilt. */
  function zusammenfassung(name) {
    const aus = (text) => ({ text, aktiv: false });
    const an = (text) => ({ text, aktiv: true });
    switch (name) {
      case 'ort':
        return state.home ? an(state.home.label) : aus(t('s1.sumNone'));
      case 'zeit': {
        const z = state.zeit;
        if (z.von && z.bis) return an(t('s2.sum', { von: fmtDate(z.von), bis: fmtDate(z.bis) }));
        if (z.von) return an(t('s2.sumFrom', { von: fmtDate(z.von) }));
        if (z.bis) return an(t('s2.sumTo', { bis: fmtDate(z.bis) }));
        return aus(t('s2.sumAll'));
      }
      case 'entfernung': {
        const e = state.entfernung;
        if (!e.an) return aus(t('s3.sumOff'));
        return an(t('s3.sum', { von: zahl(e.von ?? 0),
                                bis: e.bis === null ? '∞' : zahl(e.bis) }));
      }
      case 'preis': {
        const p = state.preis;
        if (!p.an) return aus(t('s4.sumOff'));
        const w = WAEHRUNG_ZEICHEN[p.waehrung] || p.waehrung;
        return an(t('s4.sum', { von: zahl(p.von ?? 0),
                                bis: p.bis === null ? '∞' : zahl(p.bis), w }));
      }
      case 'bands': {
        const n = state.bands.auswahl.size;
        if (!state.bands.an) return aus(t('s5.sumOff'));
        return an(n === 1 ? t('s5.sum1') : t('s5.sum', { n: zahl(n) }));
      }
      case 'genre': {
        const n = state.genre.auswahl.size;
        if (!state.genre.an) return aus(t('s6.sumOff'));
        return an(n === 1 ? t('s6.sum1') : t('s6.sum', { n: zahl(n) }));
      }
      default:
        return aus('');
    }
  }

  /** Die Kurzzeile eines zusammengeklappten Schritts, samt „Ändern". */
  function kurzzeile(sec, name) {
    let kurz = sec.querySelector('.kurz');
    if (!kurz) {
      kurz = document.createElement('div');
      kurz.className = 'kurz';
      const text = document.createElement('span');
      text.className = 'kurz-text';
      const knopf = document.createElement('button');
      knopf.type = 'button';
      knopf.className = 'ghost small';
      knopf.addEventListener('click', () => {
        state.offen = name;
        zeichnen();
        sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      kurz.append(text, knopf);
      sec.querySelector('h2').append(kurz);
    }
    const { text, aktiv } = zusammenfassung(name);
    kurz.querySelector('.kurz-text').textContent = text;
    kurz.querySelector('.kurz-text').className = 'kurz-text' + (aktiv ? '' : ' aus');
    const knopf = kurz.querySelector('button');
    knopf.textContent = t('s.change');
    knopf.title = t('s.changeTitle');
    return kurz;
  }

  /** Baut die Kette neu auf: was sichtbar ist, was offen, was zusammengeklappt. */
  function ketteZeichnen() {
    let davorBeantwortet = true;
    for (const name of KETTE) {
      const sec = sektion(name);
      const beantwortet = !!state.antwort[name];
      sec.hidden = !davorBeantwortet;
      // Aufgeklappt ist, was offen gewählt wurde - und alles noch
      // Unbeantwortete, damit nie ein Schritt ohne Inhalt dasteht.
      const offen = name === state.offen || !beantwortet;
      sec.classList.toggle('erledigt', !offen);
      sec.classList.toggle('dran', offen && davorBeantwortet && !beantwortet);
      sec.querySelector('.koerper').hidden = !offen;
      kurzzeile(sec, name).hidden = offen;

      if (sec.hidden) {
        // Was noch nicht sichtbar ist, braucht auch keine Zahl.
      } else {
        const rest = sec.querySelector('[data-rest]');
        if (rest) {
          rest.innerHTML = t('s.rest', { n: '<b>' + zahl(uebrig(name)) + '</b>',
                                         gesamt: zahl(F.length) });
        }
      }
      davorBeantwortet = davorBeantwortet && beantwortet;
    }
    $('s-ergebnis').hidden = !KETTE.every((n) => state.antwort[n]);
  }

  /** Eine Frage ist beantwortet: den nächsten offenen Schritt aufklappen. */
  function beantworten(name) {
    state.antwort[name] = true;
    const naechster = KETTE.find((n) => !state.antwort[n]);
    state.offen = naechster || null;
    zeichnen();
    const ziel = naechster ? sektion(naechster) : $('s-ergebnis');
    if (ziel && !ziel.hidden) {
      ziel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  /** Ja oder Nein auf eine der Filterfragen. */
  function wahlSetzen(name, an) {
    state[name].an = an;
    const inhalt = $(name + '-inhalt');
    if (inhalt) inhalt.hidden = !an;
    for (const btn of document.querySelectorAll(`[data-wahl="${name}"]`)) {
      btn.setAttribute('aria-pressed', String((btn.dataset.wert === 'ja') === an));
    }
    // "Nein" beantwortet die Frage sofort. "Ja" auch - der Inhalt bleibt
    // offen, solange niemand weiterklickt, denn state.offen zeigt auf ihn.
    if (!state.antwort[name]) {
      if (an) {
        state.antwort[name] = true;
        state.offen = name;                 // aufgeklappt lassen zum Ausfüllen
        zeichnen();
        return;
      }
      beantworten(name);
      return;
    }
    zeichnen();
  }

  /* ---------------- Bandsuche ---------------- */

  let sucheTimer = null;

  function bandtrefferZeichnen() {
    const term = fold($('band-search').value.trim());
    const list = $('band-results');
    const hint = $('band-hint');
    list.innerHTML = '';

    if (term.length < 2) {
      hint.textContent = t('bands.hintMin', { n: zahl(BANDS.length) });
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
      const gewaehlt = state.bands.auswahl.has(i);
      btn.textContent = gewaehlt ? t('bands.chosenBtn') : t('bands.choose');
      btn.disabled = gewaehlt;
      btn.className = gewaehlt ? 'ghost' : '';
      btn.title = t(gewaehlt ? 'bands.chosenTitle' : 'bands.chooseTitle', { band: BANDS[i] });
      btn.addEventListener('click', () => {
        state.bands.auswahl.set(i, 1);
        // Feld leeren, damit sich die nächste Band ohne Umweg tippen lässt
        const feld = $('band-search');
        feld.value = '';
        feld.focus();
        bandtrefferZeichnen();
        bandauswahlZeichnen();
        zeichnen();
      });
      const left = document.createElement('div');
      left.append(label, document.createTextNode(' '), cnt);
      li.append(left, btn);
      frag.append(li);
    }
    list.append(frag);
  }

  function bandauswahlZeichnen() {
    const list = $('chosen-list');
    list.innerHTML = '';
    $('chosen-count').textContent = state.bands.auswahl.size;

    if (!state.bands.auswahl.size) {
      const li = document.createElement('li');
      li.className = 'hint';
      li.textContent = t('bands.empty');
      list.append(li);
      return;
    }

    const eintraege = [...state.bands.auswahl.entries()]
      .sort((a, b) => BANDS[a[0]].localeCompare(BANDS[b[0]], sprache));

    for (const [i, gewicht] of eintraege) {
      const li = document.createElement('li');
      li.className = 'chip' + (gewicht === 2 ? ' double' : '');

      const name = document.createElement('span');
      name.textContent = BANDS[i];

      const w = document.createElement('button');
      w.className = 'w';
      w.textContent = gewicht === 2 ? '×2' : '×1';
      w.title = t(gewicht === 2 ? 'bands.weightDouble' : 'bands.weightSingle');
      w.addEventListener('click', () => {
        state.bands.auswahl.set(i, gewicht === 2 ? 1 : 2);
        bandauswahlZeichnen(); zeichnen();
      });

      const x = document.createElement('button');
      x.className = 'x';
      x.textContent = '×';
      x.title = t('bands.remove');
      x.addEventListener('click', () => {
        state.bands.auswahl.delete(i);
        bandauswahlZeichnen(); bandtrefferZeichnen(); zeichnen();
      });

      li.append(name, w, x);
      list.append(li);
    }
  }

  /* ---------------- Genreauswahl ----------------
     Die Quellen schreiben das Genre als Freitext (1.544 Schreibweisen).
     scraper/genres.py fasst das zu Oberbegriffen zusammen; hier stehen nur
     noch deren Spaltennummern. */

  function genresZeichnen() {
    const list = $('genre-list');
    if (!list) return;
    list.innerHTML = '';

    const reihe = GENRES.map((_, i) => i)
      .sort((a, b) => genreName(a).localeCompare(genreName(b), sprache));

    const frag = document.createDocumentFragment();
    for (const i of reihe) {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      const an = state.genre.auswahl.has(i);
      btn.className = 'genre-chip' + (an ? ' on' : '');
      btn.setAttribute('aria-pressed', an ? 'true' : 'false');
      btn.title = t(an ? 'genre.removeTitle' : 'genre.addTitle', { genre: genreName(i) });
      const name = document.createElement('span');
      name.textContent = genreName(i);
      const cnt = document.createElement('span');
      cnt.className = 'cnt';
      cnt.textContent = zahl(genreFreq[i]);
      btn.append(name, cnt);
      btn.addEventListener('click', () => {
        if (state.genre.auswahl.has(i)) state.genre.auswahl.delete(i);
        else state.genre.auswahl.add(i);
        genresZeichnen();
        zeichnen();
      });
      li.append(btn);
      frag.append(li);
    }
    list.append(frag);

    $('genre-hint').textContent = !state.genre.auswahl.size ? t('genre.empty')
      : state.genre.auswahl.size === 1 ? t('genre.chosen1')
      : t('genre.chosen', { n: state.genre.auswahl.size });
  }

  /* ---------------- Darstellung einzelner Angaben ---------------- */

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

  /** Preisangabe einer Karte — heutiger Stand, davor der Startpreis. */
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

  /* ---------------- Sortierung ----------------
     Nach Übereinstimmung lässt sich nur ordnen, wenn es eine gibt — also
     wenn nach Bands oder nach Genre gefiltert wird. */

  const gewichtet = () => (state.bands.an && state.bands.auswahl.size) ||
                          (state.genre.an && state.genre.auswahl.size);

  /** Was sich zu ordnen lohnt: Uebereinstimmung, Entfernung, Datum, Preis.

      Weggelassen wird, was nichts ordnen kann - ohne Band- oder Genreauswahl
      gibt es keine Uebereinstimmung, ohne Wohnort keine Entfernung. Eine
      Auswahl anzubieten, die alle Zeilen gleich behandelt, waere eine
      Behauptung ueber eine Ordnung, die es nicht gibt. */
  const sortierungen = () => {
    const liste = [];
    if (gewichtet()) liste.push('match');
    if (state.home) liste.push('distance');
    liste.push('date', 'price');
    return liste;
  };

  /** Die geltende Sortierung: die eigene Wahl, sonst die erste moegliche.

      Die Vorgabe muss mitwandern. Frueher hatte jede Filterart ihre eigene
      gemerkte Sortierung; mit der Kette gibt es nur noch eine, und die stand
      vor der Bandauswahl auf "Datum". Kam danach eine Band dazu, blieb sie
      dort stehen - die Liste ordnete nach Termin, waehrend die Prozentzahl
      danebenstand und niemand sie zu Gesicht bekam. */
  function sortierung() {
    const erlaubt = sortierungen();
    return (state.sortierung && erlaubt.includes(state.sortierung))
      ? state.sortierung : erlaubt[0];
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

  function sortierungZeichnen() {
    const wahl = $('sort');
    if (!wahl) return;
    const aktiv = sortierung();
    wahl.innerHTML = '';
    for (const key of sortierungen()) {
      const o = document.createElement('option');
      o.value = key;
      o.textContent = t('sort.' + key);
      wahl.append(o);
    }
    wahl.value = aktiv;
  }

  /** "Zeitraum, Umkreis und Preis" - in der Sprache, die gerade gilt. */
  function aufzaehlen(teile) {
    try {
      return new Intl.ListFormat(sprache, { style: 'long', type: 'conjunction' })
        .format(teile);
    } catch (_) {
      return teile.join(', ');   // aeltere Browser bekommen die Kommafassung
    }
  }

  /* ---------------- Bewertung ----------------
     Bands und Genre dürfen zugleich gelten. Ein Festival muss dann beide
     Bedingungen erfüllen; die Übereinstimmung ist das Mittel aus beiden
     Anteilen - sonst zählte eine der Auswahlen für die Reihenfolge nicht. */

  function bewerten(i) {
    const row = F[i];
    const eintrag = { i, row, pct: null, hits: [], gHits: [], dist: distanceOf(row) };
    const anteile = [];

    if (state.bands.an && state.bands.auswahl.size) {
      const gesamt = [...state.bands.auswahl.values()].reduce((a, b) => a + b, 0);
      let gewicht = 0;
      for (const [b, w] of state.bands.auswahl) {
        if (sets[i].has(b)) { gewicht += w; eintrag.hits.push([b, w]); }
      }
      anteile.push((gewicht / gesamt) * 100);
    }

    if (state.genre.an && state.genre.auswahl.size) {
      for (const g of (row[GENRE_IDS] || [])) {
        if (state.genre.auswahl.has(g)) eintrag.gHits.push(g);
      }
      if (eintrag.gHits.length) {
        anteile.push((eintrag.gHits.length / state.genre.auswahl.size) * 100);
      }
      // Ein Festival ohne Genreangabe, das nur durch "mitzeigen" hier ist,
      // bekommt keinen Anteil - es steht damit hinten, nicht vorn.
    }

    if (anteile.length) {
      eintrag.pct = anteile.reduce((a, b) => a + b, 0) / anteile.length;
    }
    return eintrag;
  }

  /* ---------------- Treffer ---------------- */

  let treffer = [];
  const stapel = () => (window.innerWidth < 620 ? 25 : 50);
  let gezeigt = stapel();

  /** Ein Durchgang: Kette neu aufbauen, Liste und Karte neu füllen. */
  function zeichnen() {
    ketteZeichnen();
    if ($('s-ergebnis').hidden) return;

    // Was zu ordnen ist, aendert sich mit der Auswahl - die Liste also auch.
    sortierungZeichnen();

    const pool = gefiltert();

    // Nur nennen, was auch filtert.
    const kriterien = [t('filter.critDate')];
    if (state.entfernung.an && state.home) kriterien.push(t('filter.critRadius'));
    if (state.preis.an) kriterien.push(t('filter.critPrice'));
    if (state.bands.an && state.bands.auswahl.size) kriterien.push(t('filter.critBands'));
    if (state.genre.an && state.genre.auswahl.size) kriterien.push(t('filter.critGenre'));

    $('filter-stat').innerHTML = t('filter.stat', {
      n: zahl(pool.length), gesamt: zahl(F.length), kriterien: aufzaehlen(kriterien),
    });

    const scored = pool.map(bewerten);
    scored.sort(vergleicher());

    $('result-stat').textContent = !scored.length ? t('res.none')
      : scored.length === 1 ? t('res.one') : t('res.many', { n: zahl(scored.length) });

    treffer = scored.slice(0, 300);
    treffer.forEach((s, n) => { s.eintragId = `fest-${n}`; });
    gezeigt = stapel();
    $('festival-list').innerHTML = '';
    listeZeichnen();

    if (scored.length > 300) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = t('res.more', { n: zahl(scored.length - 300) });
      $('festival-list').append(li);
    }

    KARTE.setzePins(treffer
      .filter((s) => s.row[LAT] != null)
      .map((s) => ({
        lat: s.row[LAT], lon: s.row[LON], name: s.row[NAME],
        pct: s.pct, dist: s.dist, eintragId: s.eintragId, px: 0, py: 0,
      })));
    if (state.karte) KARTE.zeichnen();
  }

  /* Nur die ersten Treffer zeichnen und auf Wunsch nachlegen. Alle 300 auf
     einmal ergaben am Telefon eine Seite von 109.000 Pixeln Hoehe - über
     hundert Bildschirme, die niemand durchwischt, und jede Karte kostet
     Aufbauzeit. */
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
      const pctBox = document.createElement('div');
      pctBox.className = 'pct';
      pctBox.textContent = `${s.pct.toFixed(0)} %`;
      const small = document.createElement('small');
      small.textContent = t('card.match');
      pctBox.append(small);
      head.append(pctBox);
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
        : `${zahl(s.dist)} km`],
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
      const getroffen = new Set(s.gHits);
      genres.forEach((g, n) => {
        const span = document.createElement(getroffen.has(g) ? 'mark' : 'b');
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
    const gewaehlt = new Set(s.hits.map((h) => h[0]));
    const namen = row[LINEUP].map((b) => [BANDS[b], gewaehlt.has(b)])
      .sort((a, b) => a[0].localeCompare(b[0], sprache));
    namen.forEach(([n, istTreffer], k) => {
      const el = document.createElement(istTreffer ? 'mark' : 'span');
      el.textContent = n;
      all.append(el);
      if (k < namen.length - 1) all.append(document.createTextNode(' · '));
    });
    if (!namen.length) all.textContent = t('card.noLineup');
    det.append(sum, all);

    li.append(head, facts, hits, det);
    return li;
  }

  /* ---------------- Karte ----------------
     Die Karte kommt erst auf Wunsch. Sie liegt unter den Treffern, weil sie
     das Ergebnis zeigt und nicht die Frage - und weil ein Canvas, das niemand
     ansieht, bei jeder Änderung mitgezeichnet würde. */

  let karteGestartet = false;

  function karteUmschalten(an) {
    state.karte = an;
    $('karte-block').hidden = !an;
    const knopf = $('karte-schalter');
    knopf.setAttribute('aria-expanded', String(an));
    knopf.textContent = t(an ? 'map.hide' : 'map.show');
    knopf.title = t(an ? 'map.hideTitle' : 'map.showTitle');
    if (!an) return;
    if (!karteGestartet) {
      karteStarten();
      karteGestartet = true;
    }
    // Erst jetzt hat das Canvas eine Breite - vorher wäre es 0 Pixel breit.
    KARTE.zeichnen();
  }

  function karteStarten() {
    KARTE.start({
      t,
      sprache: () => sprache,
      wohnort: () => state.home,
      umkreisAktiv: () => state.entfernung.an && !!state.home,
      umkreisVon: () => state.entfernung.von ?? 0,
      umkreisBis: () => state.entfernung.bis,
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
  }

  /* ---------------- Zugriffszählung ----------------
     Eine statische Seite kann sich nicht selbst zählen. Ist in config.js eine
     GoatCounter-Kennung hinterlegt, meldet die Seite den Aufruf dorthin — ohne
     Cookies, ohne Zugriff auf den Gerätespeicher. Ohne Kennung passiert gar
     nichts.

     Die Seite selbst zeigt keinen Zählerstand, auch nicht auf Umwegen: Der
     Stand steht ausschließlich im GoatCounter-Konto hinter der Anmeldung. */

  function initZaehler() {
    const code = ((window.CONFIG && window.CONFIG.zaehler) || '').trim();
    const eigenstaendig = window.top === window.self;
    const echteAdresse = location.protocol === 'https:' &&
                         location.hostname !== 'localhost';
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

  /* ---------------- Installierbarkeit ---------------- */

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

  /* ---------------- Rückmeldung ---------------- */

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
     Fragezeichen den Text in einem Feld. */

  function initHelp() {
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
     Abschnitte. Dort bleiben sie eingeklappt, bis der Fußlink sie öffnet. */

  function initLegal() {
    const ids = ['impressum', 'datenschutz'];
    const secs = ids.map((id) => $(id)).filter(Boolean);
    if (!secs.length) return;

    for (const sec of secs) {
      sec.hidden = true;
      const back = document.createElement('button');
      back.type = 'button';
      back.className = 'ghost small legal-close';
      back.dataset.i18n = 'legal.back';
      back.dataset.i18nTitle = 'legal.backTitle';
      back.textContent = t('legal.back');
      back.title = t('legal.backTitle');
      back.addEventListener('click', () => zeigen(null));
      sec.append(back);
    }

    function zeigen(id) {
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
      a.addEventListener('click', (e) => { e.preventDefault(); zeigen(id); });
    }
  }

  function datenstandZeigen() {
    $('build-info').textContent = t('footer.build', {
      stand: fmtStand(D.generated),
      f: zahl(F.length),
      a: zahl(BANDS.length),
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
      bandtrefferZeichnen();
      bandauswahlZeichnen();
      genresZeichnen();
      sortierungZeichnen();
      karteUmschalten(state.karte);
      datenstandZeigen();
      datumsHinweis(false);
      zeichnen();
    });

    spracheAnwenden();
  }

  /* ---------------- Zeitraum ---------------- */

  const heute = new Date().toISOString().slice(0, 10);

  /** Erklärt, warum ein Datum zurückgezogen wurde, und warnt vor
      Zeiträumen in der Vergangenheit. */
  function datumsHinweis(zuFrueh) {
    const el = $('date-hint');
    const z = state.zeit;
    const vergangen = (z.von && z.von < heute) || (z.bis && z.bis < heute);
    if (zuFrueh) {
      el.className = 'hint err';
      el.textContent = t('date.tooEarly', { datum: fmtDate(z.minDate) });
    } else if (vergangen) {
      el.className = 'hint warn';
      el.textContent = t('date.past');
    } else {
      el.className = 'hint';
      el.textContent = '';
    }
  }

  /* ---------------- Währungsauswahl ---------------- */

  function waehrungAnwenden() {
    const wahl = $('preis-waehrung');
    if (wahl.value !== state.preis.waehrung) wahl.value = state.preis.waehrung;
    preisHinweis();
  }

  /** Was die Grenzen in Euro bedeuten — bei fremder Währung nicht offensichtlich. */
  function preisHinweis() {
    const el = $('preis-hint');
    const p = state.preis;
    if (p.waehrung === 'EUR' || (p.von === null && p.bis === null)) {
      el.className = 'hint';
      el.textContent = '';
      return;
    }
    const eurText = (v) => v === null ? '∞'
      : nachEuro(v).toLocaleString(sprache, { maximumFractionDigits: 0 }) + ' €';
    el.className = 'hint';
    el.textContent = t('s4.inEuro', { von: eurText(p.von ?? 0), bis: eurText(p.bis) });
  }

  /* ---------------- Verdrahtung ---------------- */

  /** Zahl aus einem Feld; leer heißt „keine Grenze". */
  function feldZahl(el) {
    const roh = el.value.trim();
    if (!roh) return null;
    const wert = Number(roh);
    return Number.isFinite(wert) && wert >= 0 ? wert : null;
  }

  function init() {
    // Untergrenze des Kalenders: Monatsanfang des frühesten Festivals im
    // Datenbestand. Voreingestellt bleibt heute, sofern das darin liegt.
    const minDate = D.minDate || '';
    state.zeit.minDate = minDate;
    if (minDate) { $('from').min = minDate; $('to').min = minDate; }
    state.zeit.von = minDate && heute < minDate ? minDate : heute;
    $('from').value = state.zeit.von;

    // Währungen, für die ein Kurs vorliegt. Ohne Kurs wäre eine Grenze in
    // dieser Währung eine Zahl ohne Bedeutung.
    const wahl = $('preis-waehrung');
    for (const code of Object.keys(KURSE).sort()) {
      const o = document.createElement('option');
      o.value = code;
      o.textContent = code;
      wahl.append(o);
    }
    wahl.value = state.preis.waehrung;

    // --- Schritt 1: Ort
    $('locate').addEventListener('click', ortSetzen);
    $('home').addEventListener('keydown', (e) => { if (e.key === 'Enter') ortSetzen(); });
    $('ort-skip').addEventListener('click', () => {
      state.home = null;
      $('home-status').className = 'hint';
      $('home-status').textContent = t('s1.sumNone');
      beantworten('ort');
    });

    // --- Schritt 2: Zeitraum
    const klemme = (wert) => (state.zeit.minDate && wert && wert < state.zeit.minDate)
      ? state.zeit.minDate : wert;

    $('from').addEventListener('change', (e) => {
      const eingabe = e.target.value;
      e.target.value = klemme(eingabe);
      state.zeit.von = e.target.value;
      $('to').min = state.zeit.von || state.zeit.minDate || '';
      if (state.zeit.bis && state.zeit.von && state.zeit.bis < state.zeit.von) {
        state.zeit.bis = state.zeit.von;
        $('to').value = state.zeit.bis;
      }
      datumsHinweis(eingabe && eingabe !== e.target.value);
      zeichnen();
    });

    $('to').addEventListener('change', (e) => {
      const eingabe = e.target.value;
      e.target.value = klemme(eingabe);
      state.zeit.bis = e.target.value;
      $('from').max = state.zeit.bis || '';
      if (state.zeit.von && state.zeit.bis && state.zeit.von > state.zeit.bis) {
        state.zeit.von = state.zeit.bis;
        $('from').value = state.zeit.von;
      }
      datumsHinweis(eingabe && eingabe !== e.target.value);
      zeichnen();
    });

    $('date-unknown').addEventListener('change', (e) => {
      state.zeit.ohneTermin = e.target.checked; zeichnen();
    });
    $('show-cancelled').addEventListener('change', (e) => {
      state.zeit.abgesagte = e.target.checked; zeichnen();
    });

    // --- Ja/Nein aller Filterfragen
    for (const btn of document.querySelectorAll('[data-wahl]')) {
      btn.addEventListener('click', () => {
        wahlSetzen(btn.dataset.wahl, btn.dataset.wert === 'ja');
      });
    }
    for (const btn of document.querySelectorAll('[data-weiter]')) {
      btn.addEventListener('click', () => beantworten(btn.dataset.weiter));
    }

    // --- Schritt 3: Entfernung
    const kmLesen = () => {
      state.entfernung.von = feldZahl($('km-von'));
      state.entfernung.bis = feldZahl($('km-bis'));
      const e = state.entfernung;
      const el = $('km-hint');
      if (e.von !== null && e.bis !== null && e.von > e.bis) {
        el.className = 'hint err';
        el.textContent = t('s.rangeSwapped');
      } else {
        el.className = 'hint';
        el.textContent = state.home ? '' : t('s3.needHome');
      }
      zeichnen();
    };
    $('km-von').addEventListener('input', kmLesen);
    $('km-bis').addEventListener('input', kmLesen);
    $('geo-unknown').addEventListener('change', (e) => {
      state.entfernung.ohneKoordinate = e.target.checked; zeichnen();
    });

    // --- Schritt 4: Preis
    const preisLesen = () => {
      state.preis.von = feldZahl($('preis-von'));
      state.preis.bis = feldZahl($('preis-bis'));
      preisHinweis();
      zeichnen();
    };
    $('preis-von').addEventListener('input', preisLesen);
    $('preis-bis').addEventListener('input', preisLesen);
    $('preis-waehrung').addEventListener('change', (e) => {
      state.preis.waehrung = e.target.value;
      state.preis.gewaehlt = true;      // ab jetzt nicht mehr vom Ort überschreiben
      preisHinweis();
      zeichnen();
    });
    $('price-unknown').addEventListener('change', (e) => {
      state.preis.ohnePreis = e.target.checked; zeichnen();
    });

    // --- Schritt 5: Bands
    $('band-search').addEventListener('input', () => {
      clearTimeout(sucheTimer);
      sucheTimer = setTimeout(bandtrefferZeichnen, 120);
    });
    $('clear-bands').addEventListener('click', () => {
      state.bands.auswahl.clear();
      bandauswahlZeichnen(); bandtrefferZeichnen(); zeichnen();
    });

    // --- Schritt 6: Genre
    $('clear-genres').addEventListener('click', () => {
      state.genre.auswahl.clear(); genresZeichnen(); zeichnen();
    });
    $('genre-unknown').addEventListener('change', (e) => {
      state.genre.ohneGenre = e.target.checked; zeichnen();
    });

    // --- Ergebnis
    $('sort').addEventListener('change', (e) => {
      state.sortierung = e.target.value;
      zeichnen();
    });
    $('karte-schalter').addEventListener('click', () => karteUmschalten(!state.karte));

    datenstandZeigen();
    datumsHinweis(false);
    initSprache();
    initHelp();
    initPwa();
    initZaehler();
    initFeedback();
    initLegal();
    sortierungZeichnen();
    bandtrefferZeichnen();
    bandauswahlZeichnen();
    genresZeichnen();
    zeichnen();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
