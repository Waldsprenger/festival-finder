/* Was eingestellt ist — und was daraus folgt.

   Je Schritt ein Block. `an` sagt, ob dieser Schritt filtert; `antwort` sagt,
   ob die Frage überhaupt schon beantwortet ist. Das sind zwei verschiedene
   Dinge: Eine unbeantwortete Frage sperrt die nächste, eine mit „Nein"
   beantwortete nicht.

   Dazu die Prüfungen. Je Schritt eine — so lässt sich ausrechnen, wie viele
   Festivals nach jedem einzelnen Schritt noch übrig sind. Ohne diese Zahl
   klickt man sechs Fragen durch, ohne zu sehen, was sie bewirken. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { D, F, SPALTE, sets } = FF;

  const KETTE = ['ort', 'zeit', 'entfernung', 'preis', 'bands', 'genre'];

  const state = {
    antwort: {},                 // schritt -> true, sobald beantwortet
    offen: 'ort',                // welcher Schritt gerade aufgeklappt ist

    home: null,                  // {lat, lon, label, land}
    zeit: { von: '', bis: '', minDate: '', ohneTermin: false, abgesagte: false },
    entfernung: { an: false, von: null, bis: null, ohneKoordinate: false },
    preis: { an: false, von: null, bis: null, waehrung: 'EUR',
             gewaehlt: false, ohnePreis: true },
    bands: { an: false, auswahl: new Map() },   // bandIndex -> Gewicht (1 oder 2)
    genre: { an: false, auswahl: new Set(), ohneGenre: false },

    karte: false,
    sortierung: null,            // null = noch nicht gewählt, es gilt die Vorgabe
  };

  /* ---------------- Währung ----------------
     Preisgrenzen darf man in der eigenen Währung eingeben. Verglichen wird
     intern immer in Euro: Die Daten führen einen umgerechneten Eurobetrag, und
     zwei Zahlen in verschiedenen Währungen zu vergleichen wäre falsch. */

  const KURSE = D.kurse || { EUR: 1 };
  const ZEICHEN = { EUR: '€', CHF: 'CHF', GBP: '£', USD: '$', DKK: 'kr.',
                    SEK: 'kr', NOK: 'kr', PLN: 'zł', CZK: 'Kč', HUF: 'Ft' };

  const nachEuro = (betrag) => betrag * (KURSE[state.preis.waehrung] || 1);

  /** Welche Währung gilt an diesem Ort? Ohne bekanntes Land: Euro. */
  function waehrungFuerLand(land) {
    const gefunden = (D.waehrungLand || {})[land];
    return gefunden && KURSE[gefunden] ? gefunden : 'EUR';
  }

  /* ---------------- Entfernung ---------------- */

  function luftlinie(aLat, aLon, bLat, bLon) {
    const R = 6371, rad = Math.PI / 180;
    const dLat = (bLat - aLat) * rad, dLon = (bLon - aLon) * rad;
    const s = Math.sin(dLat / 2) ** 2 +
      Math.cos(aLat * rad) * Math.cos(bLat * rad) * Math.sin(dLon / 2) ** 2;
    return Math.round(2 * R * Math.asin(Math.sqrt(s)));
  }

  function entfernungVon(row) {
    if (!state.home || row[SPALTE.LAT] == null) return null;
    return luftlinie(state.home.lat, state.home.lon, row[SPALTE.LAT], row[SPALTE.LON]);
  }

  /* ---------------- Prüfungen je Schritt ---------------- */

  const PRUEFUNG = {
    // Der Wohnort filtert nicht, er misst nur.
    ort: () => true,

    zeit(row) {
      if (row[SPALTE.ABGESAGT] && !state.zeit.abgesagte) return false;
      if (!row[SPALTE.VON]) return state.zeit.ohneTermin;
      // Der Zeitraum zählt, nicht der Beginn: Ein Festival, das gestern
      // angefangen hat und bis Sonntag läuft, ist heute noch zu erreichen.
      const ende = row[SPALTE.BIS] || row[SPALTE.VON];
      if (state.zeit.von && ende < state.zeit.von) return false;
      if (state.zeit.bis && row[SPALTE.VON] > state.zeit.bis) return false;
      return true;
    },

    entfernung(row) {
      const e = state.entfernung;
      if (!e.an || !state.home) return true;
      const d = entfernungVon(row);
      if (d === null) return e.ohneKoordinate;
      if (e.von !== null && d < e.von) return false;
      if (e.bis !== null && d > e.bis) return false;
      return true;
    },

    preis(row) {
      const p = state.preis;
      if (!p.an) return true;
      const wert = row[SPALTE.EUR];
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
      const eigene = row[SPALTE.GENRES] || [];
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

  /* ---------------- Bewertung ----------------
     Bands und Genre dürfen zugleich gelten. Ein Festival muss dann beide
     Bedingungen erfüllen; die Übereinstimmung ist das Mittel aus beiden
     Anteilen — sonst zählte eine der Auswahlen für die Reihenfolge nicht. */

  function bewerten(i) {
    const row = F[i];
    const eintrag = { i, row, pct: null, hits: [], gHits: [],
                      dist: entfernungVon(row) };
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
      for (const g of (row[SPALTE.GENRES] || [])) {
        if (state.genre.auswahl.has(g)) eintrag.gHits.push(g);
      }
      if (eintrag.gHits.length) {
        anteile.push((eintrag.gHits.length / state.genre.auswahl.size) * 100);
      }
      // Ein Festival ohne Genreangabe, das nur durch „mitzeigen" hier ist,
      // bekommt keinen Anteil - es steht damit hinten, nicht vorn.
    }

    if (anteile.length) {
      eintrag.pct = anteile.reduce((a, b) => a + b, 0) / anteile.length;
    }
    return eintrag;
  }

  /* ---------------- Sortierung ----------------
     Was sich zu ordnen lohnt: Übereinstimmung, Entfernung, Datum, Preis.
     Weggelassen wird, was nichts ordnen kann — ohne Band- oder Genreauswahl
     gibt es keine Übereinstimmung, ohne Wohnort keine Entfernung. Eine Auswahl
     anzubieten, die alle Zeilen gleich behandelt, wäre eine Behauptung über
     eine Ordnung, die es nicht gibt. */

  const gewichtet = () => (state.bands.an && state.bands.auswahl.size) ||
                          (state.genre.an && state.genre.auswahl.size);

  function sortierungen() {
    const liste = [];
    if (gewichtet()) liste.push('match');
    if (state.home) liste.push('distance');
    liste.push('date', 'price');
    return liste;
  }

  /** Die geltende Sortierung: die eigene Wahl, sonst die erste mögliche.

      Die Vorgabe muss mitwandern. Früher hatte jede Filterart ihre eigene
      gemerkte Sortierung; mit der Kette gibt es nur noch eine, und die stand
      vor der Bandauswahl auf „Datum". Kam danach eine Band dazu, blieb sie
      dort stehen — die Liste ordnete nach Termin, während die Prozentzahl
      danebenstand und niemand sie zu Gesicht bekam. */
  function sortierung() {
    const erlaubt = sortierungen();
    return (state.sortierung && erlaubt.includes(state.sortierung))
      ? state.sortierung : erlaubt[0];
  }

  // Fehlende Angaben ans Ende, egal wonach sortiert wird: Ein Festival ohne
  // Preis ist nicht das günstigste, eines ohne Termin nicht das nächste.
  const km = (e) => e.dist ?? Infinity;
  const eur = (e) => e.row[SPALTE.EUR] ?? Infinity;
  const tag = (e) => e.row[SPALTE.VON] || '9999-99-99';
  const pct = (e) => (e.pct === null ? -1 : e.pct);

  function vergleicher() {
    const name = (a, b) => a.row[SPALTE.NAME].localeCompare(b.row[SPALTE.NAME],
                                                            FF.sprache());
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

  Object.assign(FF, {
    state, KETTE, PRUEFUNG, uebrig, gefiltert, bewerten,
    sortierungen, sortierung, vergleicher, gewichtet,
    entfernungVon, nachEuro, waehrungFuerLand, WAEHRUNG_ZEICHEN: ZEICHEN, KURSE,
  });
})();
