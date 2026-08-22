/* Bands suchen und wählen, Genres anklicken.

   Die Bandsuche läuft über 86.000 Namen und muss beim Tippen mithalten;
   deshalb die vorgefalteten Namen aus daten.js und ein Abbruch nach 400
   Treffern am Wortanfang. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { $, t, zahl, state, D, BANDS, GENRES, bandFreq, genreFreq, fold } = FF;

  const bandsGefaltet = BANDS.map(fold);

  /* Kürzel und Zweitschreibweisen: In den Daten steht der ausgeschriebene
     Name, gesucht wird aber auch nach der Abkürzung. „TBS" führt deshalb zu
     The Butcher Sisters — angezeigt wird immer der ausgeschriebene Name, mit
     dem Kürzel als Hinweis dahinter. */
  const ALIAS = (D.bandAlias || []).map(([text, i]) => [fold(text), text, i]);
  const aliasVonBand = new Map();
  for (const [, text, i] of ALIAS) {
    if (!aliasVonBand.has(i)) aliasVonBand.set(i, []);
    aliasVonBand.get(i).push(text);
  }

  const genreName = (i) => t('genre.' + GENRES[i]);

  /* ---------------- Bandsuche ---------------- */

  function treffer(term) {
    const anfang = [], enthalten = [];
    for (let i = 0; i < bandsGefaltet.length; i++) {
      const pos = bandsGefaltet[i].indexOf(term);
      if (pos === 0) anfang.push(i);
      else if (pos > 0) enthalten.push(i);
      if (anfang.length > 400) break;
    }
    // Kürzel zählen wie ein Namenstreffer, doppelte fallen weg
    for (const [gefaltet, , i] of ALIAS) {
      const pos = gefaltet.indexOf(term);
      if (pos < 0) continue;
      if (!anfang.includes(i) && !enthalten.includes(i)) {
        (pos === 0 ? anfang : enthalten).push(i);
      }
    }
    const alle = anfang.concat(enthalten);
    alle.sort((a, b) => bandFreq[b] - bandFreq[a] ||
                        BANDS[a].localeCompare(BANDS[b], FF.sprache()));
    return alle;
  }

  function bandtrefferZeichnen() {
    const term = fold($('band-search').value.trim());
    const liste = $('band-results');
    const hinweis = $('band-hint');
    liste.innerHTML = '';

    if (term.length < 2) {
      hinweis.textContent = t('bands.hintMin', { n: zahl(BANDS.length) });
      return;
    }

    const alle = treffer(term);
    const zeigen = alle.slice(0, 80);
    hinweis.textContent = alle.length
      ? t('bands.hintHits', {
          n: alle.length,
          rest: alle.length > zeigen.length
            ? t('bands.hintShown', { m: zeigen.length }) : '',
        })
      : t('bands.hintNone');

    const frag = document.createDocumentFragment();
    for (const i of zeigen) frag.append(bandZeile(i));
    liste.append(frag);
  }

  function bandZeile(i) {
    const li = document.createElement('li');
    const label = document.createElement('span');
    label.textContent = BANDS[i];
    if (aliasVonBand.has(i)) {
      const kurz = document.createElement('span');
      kurz.className = 'alias';
      kurz.textContent = t('bands.alsoKnown', { kurz: aliasVonBand.get(i).join(', ') });
      label.append(kurz);
    }
    const anzahl = document.createElement('span');
    anzahl.className = 'cnt';
    anzahl.textContent = bandFreq[i] === 1
      ? t('bands.festival1') : t('bands.festivals', { n: bandFreq[i] });

    const btn = document.createElement('button');
    const gewaehlt = state.bands.auswahl.has(i);
    btn.textContent = gewaehlt ? t('bands.chosenBtn') : t('bands.choose');
    btn.disabled = gewaehlt;
    btn.className = gewaehlt ? 'ghost' : '';
    btn.title = t(gewaehlt ? 'bands.chosenTitle' : 'bands.chooseTitle',
                  { band: BANDS[i] });
    btn.addEventListener('click', () => {
      state.bands.auswahl.set(i, 1);
      // Feld leeren, damit sich die nächste Band ohne Umweg tippen lässt
      const feld = $('band-search');
      feld.value = '';
      feld.focus();
      bandtrefferZeichnen();
      bandauswahlZeichnen();
      FF.zeichnen();
    });

    const links = document.createElement('div');
    links.append(label, document.createTextNode(' '), anzahl);
    li.append(links, btn);
    return li;
  }

  function bandauswahlZeichnen() {
    const liste = $('chosen-list');
    liste.innerHTML = '';
    $('chosen-count').textContent = state.bands.auswahl.size;

    if (!state.bands.auswahl.size) {
      const li = document.createElement('li');
      li.className = 'hint';
      li.textContent = t('bands.empty');
      liste.append(li);
      return;
    }

    const eintraege = [...state.bands.auswahl.entries()]
      .sort((a, b) => BANDS[a[0]].localeCompare(BANDS[b[0]], FF.sprache()));

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
        bandauswahlZeichnen(); FF.zeichnen();
      });

      const x = document.createElement('button');
      x.className = 'x';
      x.textContent = '×';
      x.title = t('bands.remove');
      x.addEventListener('click', () => {
        state.bands.auswahl.delete(i);
        bandauswahlZeichnen(); bandtrefferZeichnen(); FF.zeichnen();
      });

      li.append(name, w, x);
      liste.append(li);
    }
  }

  /* ---------------- Genres ----------------
     Die Quellen schreiben das Genre als Freitext (1.544 Schreibweisen).
     kern/genres.py fasst das zu Oberbegriffen zusammen; hier stehen nur noch
     deren Spaltennummern. */

  function genresZeichnen() {
    const liste = $('genre-list');
    if (!liste) return;
    liste.innerHTML = '';

    const reihe = GENRES.map((_, i) => i)
      .sort((a, b) => genreName(a).localeCompare(genreName(b), FF.sprache()));

    const frag = document.createDocumentFragment();
    for (const i of reihe) {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      const an = state.genre.auswahl.has(i);
      btn.className = 'genre-chip' + (an ? ' on' : '');
      btn.setAttribute('aria-pressed', an ? 'true' : 'false');
      btn.title = t(an ? 'genre.removeTitle' : 'genre.addTitle',
                    { genre: genreName(i) });
      const name = document.createElement('span');
      name.textContent = genreName(i);
      const anzahl = document.createElement('span');
      anzahl.className = 'cnt';
      anzahl.textContent = zahl(genreFreq[i]);
      btn.append(name, anzahl);
      btn.addEventListener('click', () => {
        if (state.genre.auswahl.has(i)) state.genre.auswahl.delete(i);
        else state.genre.auswahl.add(i);
        genresZeichnen();
        FF.zeichnen();
      });
      li.append(btn);
      frag.append(li);
    }
    liste.append(frag);

    $('genre-hint').textContent = !state.genre.auswahl.size ? t('genre.empty')
      : state.genre.auswahl.size === 1 ? t('genre.chosen1')
      : t('genre.chosen', { n: state.genre.auswahl.size });
  }

  Object.assign(FF, { bandtrefferZeichnen, bandauswahlZeichnen, genresZeichnen,
                      genreName, aliasVonBand });
})();
