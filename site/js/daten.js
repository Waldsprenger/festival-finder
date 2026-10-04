/* Die Daten und was sich unmittelbar aus ihnen ergibt.

   data.js setzt window.DATA; hier bekommt sie Namen für ihre Spalten und ein
   paar Register, die jede spätere Frage schnell beantworten. Alles Weitere
   hängt an FF — dem einen Namensraum, über den sich die Teile finden.

   Die Geodaten (Ortsverzeichnis, Postleitzahlen, Kartenumrisse) stehen in
   geo.js. Sie ändern sich fast nie und kommen erst nach dem ersten Bild —
   als geo.js?v=<Stand>, damit Browser und Service Worker sie behalten. */

window.FF = window.FF || {};

(() => {
  'use strict';

  const D = window.DATA;

  /* data.js ist mehrere Megabyte groß. Bleibt sie unterwegs hängen, sagt die
     Seite das, statt still leer zu bleiben. */
  if (!D || !Array.isArray(D.festivals)) {
    FF.keineDaten = true;
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

  /* Spaltennummern einer Festivalzeile — dieselbe Reihenfolge steht in
     festivalfinder/ausgabe/daten_js.py. */
  const SPALTE = {
    NAME: 0, VON: 1, BIS: 2, STADT: 3, LAND: 4, ORT: 5,
    EUR: 6, PREIS: 7, WEB: 8, LAT: 9, LON: 10, LINEUP: 11,
    HINWEIS: 12, ABGESAGT: 13, GENRES: 14, PREIS_START: 15,
  };

  const F = D.festivals;
  const BANDS = D.bands;
  const GENRES = D.genres || [];

  // Lineups als Set: „spielt Band X hier?" fällt beim Filtern ständig an
  const sets = F.map((r) => new Set(r[SPALTE.LINEUP]));

  const bandFreq = new Int32Array(BANDS.length);
  const genreFreq = new Int32Array(GENRES.length);
  for (const r of F) {
    for (const b of r[SPALTE.LINEUP]) bandFreq[b]++;
    for (const g of (r[SPALTE.GENRES] || [])) genreFreq[g]++;
  }

  /* ---------------- Geodaten ----------------
     Einmal angefordert, von allen geteilt. Als <script> statt fetch(), damit
     es auch per Doppelklick (file://) geht — dort kennt ein Dateipfad keinen
     Abfrageteil, deshalb notfalls ein zweiter Versuch ohne Kennung. Kommt gar
     nichts, gibt es null: Die Wohnortsuche fragt dann weiter draußen, die
     Karte zeichnet ohne Umrisse. */
  let geoVersprechen = null;

  function geo() {
    if (window.GEO) return Promise.resolve(window.GEO);
    if (geoVersprechen) return geoVersprechen;
    const stand = (D.versionen || {}).geo;
    geoVersprechen = new Promise((fertig) => {
      const laden = (src, sonst) => {
        const s = document.createElement('script');
        s.src = src;
        s.onload = () => fertig(window.GEO || null);
        s.onerror = sonst;
        document.head.append(s);
      };
      const ohne = () => laden('geo.js', () => fertig(null));
      if (stand) laden(`geo.js?v=${stand}`, ohne); else ohne();
    });
    return geoVersprechen;
  }

  Object.assign(FF, {
    D, F, BANDS, GENRES, SPALTE, sets, bandFreq, genreFreq, geo,
    $: (id) => document.getElementById(id),
  });
})();
