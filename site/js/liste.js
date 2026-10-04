/* Die Treffer: Satz, Liste, Karten.

   Nur die ersten Treffer werden gezeichnet und auf Wunsch nachgelegt: Alle 300
   auf einmal ergaben am Telefon eine Seite von 109.000 Pixeln Höhe. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { $, t, zahl, state, F, BANDS, SPALTE } = FF;

  //: So viele Treffer bekommen überhaupt eine Karte
  const HOECHSTENS = 300;

  const stapel = () => (window.innerWidth < 620 ? 25 : 50);
  let treffer = [];
  let gezeigt = stapel();

  /* ---------------- Ein Durchgang ---------------- */

  function zeichnen() {
    const { rest, treffer: pool } = FF.auswerten();
    FF.ketteZeichnen(rest);
    if ($('s-ergebnis').hidden) return;

    // Was zu ordnen ist, ändert sich mit der Auswahl — die Liste also auch.
    sortierungZeichnen();
    statZeichnen(pool.length);

    const bewertet = pool.map(FF.bewerten).sort(FF.vergleicher());
    $('result-stat').textContent = !bewertet.length ? t('res.none')
      : bewertet.length === 1 ? t('res.one')
      : t('res.many', { n: zahl(bewertet.length) });

    treffer = bewertet.slice(0, HOECHSTENS);
    treffer.forEach((s, n) => { s.eintragId = `fest-${n}`; });
    gezeigt = stapel();
    $('festival-list').innerHTML = '';
    nachlegen();

    if (bewertet.length > HOECHSTENS) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = t('res.more', { n: zahl(bewertet.length - HOECHSTENS) });
      $('festival-list').append(li);
    }

    KARTE.setzePins(treffer
      .filter((s) => s.row[SPALTE.LAT] != null)
      .map((s) => ({
        lat: s.row[SPALTE.LAT], lon: s.row[SPALTE.LON], name: s.row[SPALTE.NAME],
        pct: s.pct, dist: s.dist, eintragId: s.eintragId, px: 0, py: 0,
      })));
    if (state.karte) KARTE.zeichnen();
  }

  /** „105 von 13.339 Festivals passen — gefiltert wird nach …" */
  function statZeichnen(n) {
    const kriterien = [t('filter.critDate')];
    if (state.entfernung.an && state.home) kriterien.push(t('filter.critRadius'));
    if (state.preis.an) kriterien.push(t('filter.critPrice'));
    if (state.bands.an && state.bands.auswahl.size) kriterien.push(t('filter.critBands'));
    if (state.genre.an && state.genre.auswahl.size) kriterien.push(t('filter.critGenre'));
    $('filter-stat').innerHTML = t('filter.stat', {
      n: zahl(n), gesamt: zahl(F.length),
      kriterien: FF.aufzaehlen(kriterien, FF.sprache()),
    });
  }

  function sortierungZeichnen() {
    const wahl = $('sort');
    if (!wahl) return;
    wahl.innerHTML = '';
    for (const key of FF.sortierungen()) {
      const o = document.createElement('option');
      o.value = key;
      o.textContent = t('sort.' + key);
      wahl.append(o);
    }
    wahl.value = FF.sortierung();
  }

  function nachlegen() {
    const liste = $('festival-list');
    const bisher = liste.querySelectorAll('.fest').length;
    liste.querySelector('.mehr')?.remove();

    const frag = document.createDocumentFragment();
    for (let n = bisher; n < Math.min(gezeigt, treffer.length); n++) frag.append(karte(treffer[n]));
    liste.append(frag);

    if (gezeigt < treffer.length) {
      const li = document.createElement('li');
      li.className = 'mehr';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ghost';
      btn.textContent = t('res.showMore', {
        n: Math.min(stapel(), treffer.length - gezeigt), rest: treffer.length - gezeigt,
      });
      btn.addEventListener('click', () => { gezeigt += stapel(); nachlegen(); });
      li.append(btn);
      liste.append(li);
    }
  }

  /** Sorgt dafür, dass ein Eintrag gezeichnet ist — etwa nach einem Klick auf
      einen Kartenpin, dessen Eintrag noch im Nachschub steckt. */
  function eintragZeigen(eintragId) {
    const stelle = treffer.findIndex((s) => s.eintragId === eintragId);
    if (stelle >= gezeigt) {
      gezeigt = Math.ceil((stelle + 1) / stapel()) * stapel();
      nachlegen();
    }
    return $(eintragId);
  }

  /* ---------------- Eine Karte ---------------- */

  function termin(row) {
    if (!row[SPALTE.VON]) return row[SPALTE.HINWEIS] || t('card.dateOpen');
    return row[SPALTE.BIS] && row[SPALTE.BIS] !== row[SPALTE.VON]
      ? `${FF.datum(row[SPALTE.VON])} – ${FF.datum(row[SPALTE.BIS])}`
      : FF.datum(row[SPALTE.VON]);
  }

  /** Preisangabe einer Karte — heutiger Stand, dahinter der Startpreis. */
  function preis(row) {
    const start = (row[SPALTE.PREIS_START] || '').trim();
    const seit = start ? ` (${t('card.priceStart')} ${start})` : '';
    if (row[SPALTE.EUR] === 0) return t('card.free') + seit;

    const roh = (row[SPALTE.PREIS] || '').trim();
    if (row[SPALTE.EUR] == null) return (roh || t('card.priceUnknown')) + seit;

    const eur = `${row[SPALTE.EUR].toLocaleString(FF.sprache(),
                                                  { minimumFractionDigits: 2 })} €`;
    // Fremde Währung: umgerechnet zeigen, den Originalpreis dahinter. Sonst den
    // Quelltext nur, wenn er mehr sagt als die Zahl selbst.
    if (FF.FREMDWAEHRUNG.test(roh)) return `${t('card.from')} ${eur} (${roh})` + seit;
    return (FF.preisZusatz(roh) ? roh : `${t('card.from')} ${eur}`) + seit;
  }

  const element = (tag, klasse, text) => {
    const el = document.createElement(tag);
    if (klasse) el.className = klasse;
    if (text !== undefined) el.textContent = text;
    return el;
  };

  function link(row, text) {
    const a = element('a', '', text);
    a.href = row[SPALTE.WEB]; a.target = '_blank'; a.rel = 'noopener';
    a.title = t('card.websiteTitle', { name: row[SPALTE.NAME] });
    return a;
  }

  function karte(s) {
    const li = element('li', 'fest' + (s.pct !== null && s.pct >= 50 ? ' top' : '') +
                             (s.row[SPALTE.ABGESAGT] ? ' cancelled' : ''));
    li.id = s.eintragId;
    li.append(kopf(s), fakten(s), treffernamen(s), lineup(s));
    return li;
  }

  function kopf(s) {
    const row = s.row;
    const head = element('div', 'fest-head');
    const kasten = element('div');
    if (row[SPALTE.ABGESAGT]) {
      const flagge = element('span', 'flag', t('card.cancelled'));
      flagge.title = t('card.cancelledTitle');
      kasten.append(flagge);
    }
    const h3 = element('h3');
    if (row[SPALTE.WEB]) h3.append(link(row, row[SPALTE.NAME]));
    else h3.textContent = row[SPALTE.NAME];
    kasten.append(h3);
    head.append(kasten);

    if (s.pct !== null) {
      const p = element('div', 'pct', `${s.pct.toFixed(0)} %`);
      p.append(element('small', '', t('card.match')));
      head.append(p);
    }
    return head;
  }

  function fakten(s) {
    const row = s.row;
    const ul = element('ul', 'facts');
    const platz = [row[SPALTE.ORT], row[SPALTE.STADT], row[SPALTE.LAND]].filter(Boolean).join(', ');
    const zeilen = [
      [t('card.date'), termin(row)],
      [t('card.price'), preis(row)],
      [t('card.place'), platz || t('card.unknownPlace')],
      [t('card.distance'), s.dist === null
        ? (state.home ? t('card.unknownPlace') : t('card.noHomeSet'))
        : `${zahl(s.dist)} km`],
    ];
    for (const [k, v] of zeilen) {
      const li = element('li');
      li.append(`${k}: `, element('b', '', v));
      ul.append(li);
    }

    // Genre-Oberbegriffe des Festivals; die gewählten sind hervorgehoben.
    const genres = row[SPALTE.GENRES] || [];
    if (genres.length) {
      const li = element('li', 'genre-line');
      li.append(t('card.genre') + ': ');
      const getroffen = new Set(s.gHits);
      genres.forEach((g, n) => {
        li.append(element(getroffen.has(g) ? 'mark' : 'b', '', FF.genreName(g)));
        if (n < genres.length - 1) li.append(' · ');
      });
      ul.append(li);
    }

    if (row[SPALTE.WEB]) {
      const li = element('li');
      li.append(link(row, t('card.website')));
      ul.append(li);
    }
    return ul;
  }

  function treffernamen(s) {
    const p = element('p', 'hits');
    if (!s.hits.length) { p.hidden = true; return p; }
    const namen = s.hits.sort((a, b) => b[1] - a[1] ||
                                        FF.sammler().compare(BANDS[a[0]], BANDS[b[0]]));
    p.append(t('card.yourBands'));
    namen.forEach(([b, w], n) => {
      const span = element('span', 'hit' + (w === 2 ? ' dbl' : ''), BANDS[b]);
      span.title = t(w === 2 ? 'card.bandDouble' : 'card.bandSingle', { band: BANDS[b] });
      p.append(span);
      if (n < namen.length - 1) p.append(', ');
    });
    return p;
  }

  function lineup(s) {
    const row = s.row;
    const det = element('details', 'lineup');
    const kopfzeile = element('summary', '', t('card.lineup', { n: row[SPALTE.LINEUP].length }));
    kopfzeile.title = t('card.lineupTitle');
    const alle = element('div', 'all');
    const gewaehlt = new Set(s.hits.map((h) => h[0]));
    const ordnung = FF.sammler();
    const namen = row[SPALTE.LINEUP].map((b) => [BANDS[b], gewaehlt.has(b)])
      .sort((a, b) => ordnung.compare(a[0], b[0]));
    if (!namen.length) alle.textContent = t('card.noLineup');
    namen.forEach(([n, istTreffer], k) => {
      alle.append(element(istTreffer ? 'mark' : 'span', '', n));
      if (k < namen.length - 1) alle.append(' · ');
    });
    det.append(kopfzeile, alle);
    return det;
  }

  Object.assign(FF, { zeichnen, eintragZeigen, sortierungZeichnen, termin });
})();
