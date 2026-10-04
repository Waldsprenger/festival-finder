/* Was eingestellt ist — und was daraus folgt.

   Je Schritt ein Block. `an` sagt, ob dieser Schritt filtert; `antwort`, ob
   die Frage beantwortet ist. Eine unbeantwortete Frage sperrt die nächste,
   eine mit „Nein" beantwortete nicht.

   Dazu je Schritt eine Prüfung. `auswerten()` geht die Festivals einmal durch
   und zählt dabei, wie viele nach jedem Schritt übrig sind — früher lief
   dafür je sichtbarem Schritt ein eigener Durchgang über alle Festivals, bei
   jedem Tastendruck sechs. */

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
    // Nur eine Obergrenze, kein Bereich: „ab 300 km" sucht niemand.
    entfernung: { an: false, bis: null, ohneKoordinate: false },
    preis: { an: false, bis: null, waehrung: 'EUR', gewaehlt: false, ohnePreis: true },
    bands: { an: false, auswahl: new Map() },   // bandIndex -> Gewicht (1 oder 2)
    genre: { an: false, auswahl: new Set(), ohneGenre: false },

    karte: false,
    sortierung: null,            // null = noch nicht gewählt, es gilt die Vorgabe
  };

  /* ---------------- Währung ----------------
     Grenzen in der eigenen Währung; verglichen wird in Euro, denn die Daten
     führen einen umgerechneten Eurobetrag. */

  const KURSE = D.kurse || { EUR: 1 };
  const ZEICHEN = { EUR: '€', CHF: 'CHF', GBP: '£', USD: '$', DKK: 'kr.',
                    SEK: 'kr', NOK: 'kr', PLN: 'zł', CZK: 'Kč', HUF: 'Ft' };

  const nachEuro = (betrag, waehrung) =>
    betrag * (KURSE[waehrung || state.preis.waehrung] || 1);

  function waehrungFuerLand(land) {
    const gefunden = (D.waehrungLand || {})[land];
    return gefunden && KURSE[gefunden] ? gefunden : 'EUR';
  }

  /* ---------------- Entfernung ----------------
     Für den eingestellten Wohnort einmal je Festival gerechnet und gemerkt:
     Jede Änderung an Preis oder Genre zeichnete sonst 13.000 Luftlinien neu. */

  function luftlinie(aLat, aLon, bLat, bLon) {
    const R = 6371, rad = Math.PI / 180;
    const dLat = (bLat - aLat) * rad, dLon = (bLon - aLon) * rad;
    const s = Math.sin(dLat / 2) ** 2 +
      Math.cos(aLat * rad) * Math.cos(bLat * rad) * Math.sin(dLon / 2) ** 2;
    return Math.round(2 * R * Math.asin(Math.sqrt(s)));
  }

  const abstaende = new Float64Array(F.length);
  let abstaendeFuer = null;

  function entfernungVon(row, heim, i) {
    const h = heim === undefined ? state.home : heim;
    if (!h || row[SPALTE.LAT] == null) return null;
    if (i == null || h !== state.home) {
      return luftlinie(h.lat, h.lon, row[SPALTE.LAT], row[SPALTE.LON]);
    }
    if (abstaendeFuer !== h) {
      for (let k = 0; k < F.length; k++) {
        const r = F[k];
        abstaende[k] = r[SPALTE.LAT] == null ? NaN
          : luftlinie(h.lat, h.lon, r[SPALTE.LAT], r[SPALTE.LON]);
      }
      abstaendeFuer = h;
    }
    return abstaende[i];
  }

  /* ---------------- Prüfungen je Schritt ----------------
     Jede bekommt den Filter als erstes Argument, statt ihn aus `state` zu
     holen: Eine gemerkte Suche ist derselbe Filter, nur nicht der gerade
     eingestellte, und wird mit denselben Regeln geprüft. */

  const PRUEFUNG = {
    // Der Wohnort filtert nicht, er misst nur.
    ort: () => true,

    zeit(s, row) {
      if (row[SPALTE.ABGESAGT] && !s.zeit.abgesagte) return false;
      if (!row[SPALTE.VON]) return s.zeit.ohneTermin;
      // Der Zeitraum zählt, nicht der Beginn: Wer gestern anfing und bis
      // Sonntag läuft, ist heute noch zu erreichen.
      if (s.zeit.von && (row[SPALTE.BIS] || row[SPALTE.VON]) < s.zeit.von) return false;
      return !(s.zeit.bis && row[SPALTE.VON] > s.zeit.bis);
    },

    entfernung(s, row, i) {
      const e = s.entfernung;
      if (!e.an || !s.home) return true;
      const d = entfernungVon(row, s.home, i);
      if (d === null) return e.ohneKoordinate;
      return e.bis === null || d <= e.bis;
    },

    preis(s, row) {
      const p = s.preis;
      if (!p.an) return true;
      const wert = row[SPALTE.EUR];
      if (wert === null) return p.ohnePreis;
      return p.bis === null || wert <= nachEuro(p.bis, p.waehrung);
    },

    // Eine ausgewählte Band genügt: Wer fünf nennt, sucht jedes Festival, auf
    // dem eine davon spielt — nicht das eine, auf dem alle fünf spielen.
    bands(s, row, i) {
      if (!s.bands.an || !s.bands.auswahl.size) return true;
      const drin = i == null ? new Set(row[SPALTE.LINEUP] || []) : sets[i];
      for (const b of s.bands.auswahl.keys()) if (drin.has(b)) return true;
      return false;
    },

    genre(s, row) {
      if (!s.genre.an || !s.genre.auswahl.size) return true;
      const eigene = row[SPALTE.GENRES] || [];
      if (!eigene.length) return s.genre.ohneGenre;
      return eigene.some((g) => s.genre.auswahl.has(g));
    },
  };

  const PRUEFUNGEN = KETTE.map((n) => PRUEFUNG[n]);

  /** Ein Durchgang: wie viele nach jedem Schritt übrig sind, und welche
      Zeilen alle überstehen. */
  function auswerten() {
    const rest = new Array(KETTE.length).fill(0);
    const treffer = [];
    for (let i = 0; i < F.length; i++) {
      let k = 0;
      while (k < PRUEFUNGEN.length && PRUEFUNGEN[k](state, F[i], i)) rest[k++]++;
      if (k === PRUEFUNGEN.length) treffer.push(i);
    }
    return { rest: Object.fromEntries(KETTE.map((n, k) => [n, rest[k]])), treffer };
  }

  /* ---------------- Bewertung ----------------
     Bands und Genre dürfen zugleich gelten; die Übereinstimmung ist das
     Mittel beider Anteile, sonst zählte eine Auswahl für die Reihenfolge nicht. */

  function bewerten(i) {
    const row = F[i];
    const eintrag = { i, row, pct: null, hits: [], gHits: [], dist: entfernungVon(row, state.home, i) };
    const anteile = [];

    if (state.bands.an && state.bands.auswahl.size) {
      let gesamt = 0, gewicht = 0;
      for (const [b, w] of state.bands.auswahl) {
        gesamt += w;
        if (sets[i].has(b)) { gewicht += w; eintrag.hits.push([b, w]); }
      }
      anteile.push((gewicht / gesamt) * 100);
    }

    if (state.genre.an && state.genre.auswahl.size) {
      for (const g of (row[SPALTE.GENRES] || [])) {
        if (state.genre.auswahl.has(g)) eintrag.gHits.push(g);
      }
      // Ein Festival ohne Genreangabe, nur durch „mitzeigen" hier, bekommt
      // keinen Anteil und steht damit hinten.
      if (eintrag.gHits.length) {
        anteile.push((eintrag.gHits.length / state.genre.auswahl.size) * 100);
      }
    }

    if (anteile.length) eintrag.pct = anteile.reduce((a, b) => a + b, 0) / anteile.length;
    return eintrag;
  }

  /* ---------------- Sortierung ----------------
     Angeboten wird nur, was ordnen kann: ohne Band- oder Genreauswahl keine
     Übereinstimmung, ohne Wohnort keine Entfernung. */

  const gewichtet = () => (state.bands.an && state.bands.auswahl.size) ||
                          (state.genre.an && state.genre.auswahl.size);

  function sortierungen() {
    const liste = [];
    if (gewichtet()) liste.push('match');
    if (state.home) liste.push('distance');
    liste.push('date', 'price');
    return liste;
  }

  /** Die eigene Wahl, sonst die erste mögliche. Die Vorgabe wandert mit:
      Kam nach der Datumssortierung eine Band dazu, ordnete die Liste sonst
      weiter nach Termin, während die Prozentzahl danebenstand. */
  function sortierung() {
    const erlaubt = sortierungen();
    return (state.sortierung && erlaubt.includes(state.sortierung))
      ? state.sortierung : erlaubt[0];
  }

  // Fehlende Angaben ans Ende: Ohne Preis ist ein Festival nicht das
  // günstigste, ohne Termin nicht das nächste.
  const km = (e) => e.dist ?? Infinity;
  const eur = (e) => e.row[SPALTE.EUR] ?? Infinity;
  const tag = (e) => e.row[SPALTE.VON] || '9999-99-99';
  const pct = (e) => (e.pct === null ? -1 : e.pct);

  function vergleicher() {
    const ordnung = FF.sammler();
    const name = (a, b) => ordnung.compare(a.row[SPALTE.NAME], b.row[SPALTE.NAME]);
    const datum = (a, b) => (tag(a) < tag(b) ? -1 : tag(a) > tag(b) ? 1 : 0);
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
    state, KETTE, PRUEFUNG, auswerten, bewerten,
    sortierungen, sortierung, vergleicher, gewichtet,
    entfernungVon, nachEuro, waehrungFuerLand, WAEHRUNG_ZEICHEN: ZEICHEN, KURSE,
  });
})();
