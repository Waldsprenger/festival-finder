/* Die Daten und was sich unmittelbar aus ihnen ergibt.

   data.js setzt window.DATA; hier bekommt sie Namen für ihre Spalten und ein
   paar Register, die jede spätere Frage schnell beantworten. Alles Weitere
   hängt an FF — dem einen Namensraum, über den sich die Teile der Seite
   finden. */

window.FF = window.FF || {};

(() => {
  'use strict';

  const D = window.DATA;

  /* data.js ist neun Megabyte gross. Bleibt sie unterwegs haengen, stand hier
     bisher ein Absturz in der zweiten Zeile - die Seite blieb leer, ohne ein
     Wort dazu. Jetzt sagt sie, was los ist. */
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

  /* Spaltennummern einer Festivalzeile. Dieselbe Reihenfolge steht in
     festivalfinder/ausgabe/daten_js.py - wird dort etwas eingefügt, gehört es
     auch hierher. */
  const SPALTE = {
    NAME: 0, VON: 1, BIS: 2, STADT: 3, LAND: 4, ORT: 5,
    EUR: 6, PREIS: 7, WEB: 8, LAT: 9, LON: 10, LINEUP: 11,
    HINWEIS: 12, ABGESAGT: 13, GENRES: 14, PREIS_START: 15,
  };

  const F = D.festivals;
  const BANDS = D.bands;
  const GENRES = D.genres || [];

  // Lineups als Set: die Frage „spielt Band X hier?" kommt millionenfach
  const sets = F.map((r) => new Set(r[SPALTE.LINEUP]));

  // Wie oft kommt eine Band insgesamt vor? (für die Suchergebnisse)
  const bandFreq = new Int32Array(BANDS.length);
  for (const r of F) for (const b of r[SPALTE.LINEUP]) bandFreq[b]++;

  // Wie viele Festivals hat ein Oberbegriff? (für die Genreliste)
  const genreFreq = new Int32Array(GENRES.length);
  for (const r of F) for (const g of (r[SPALTE.GENRES] || [])) genreFreq[g]++;

  Object.assign(FF, {
    D, F, BANDS, GENRES, SPALTE, sets, bandFreq, genreFreq,
    $: (id) => document.getElementById(id),
  });
})();
