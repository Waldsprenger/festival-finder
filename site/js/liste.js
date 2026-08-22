/* Die Treffer: Satz, Liste, Karten.

   Nur die ersten Treffer werden gezeichnet und auf Wunsch nachgelegt. Alle 300
   auf einmal ergaben am Telefon eine Seite von 109.000 Pixeln Höhe — über
   hundert Bildschirme, die niemand durchwischt, und jede Karte kostet
   Aufbauzeit. */

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
    FF.ketteZeichnen();
    if ($('s-ergebnis').hidden) return;

    // Was zu ordnen ist, ändert sich mit der Auswahl — die Liste also auch.
    sortierungZeichnen();

    const pool = FF.gefiltert();
    statZeichnen(pool.length);

    const bewertet = pool.map(FF.bewerten);
    bewertet.sort(FF.vergleicher());

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
    const aktiv = FF.sortierung();
    wahl.innerHTML = '';
    for (const key of FF.sortierungen()) {
      const o = document.createElement('option');
      o.value = key;
      o.textContent = t('sort.' + key);
      wahl.append(o);
    }
    wahl.value = aktiv;
  }

  function nachlegen() {
    const liste = $('festival-list');
    const bisher = liste.querySelectorAll('.fest').length;
    const mehrKnopf = liste.querySelector('.mehr');
    if (mehrKnopf) mehrKnopf.remove();

    const frag = document.createDocumentFragment();
    for (let n = bisher; n < Math.min(gezeigt, treffer.length); n++) {
      frag.append(karte(treffer[n]));
    }
    liste.append(frag);

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

  /** Preisangabe einer Karte — heutiger Stand, davor der Startpreis. */
  function preis(row) {
    const start = (row[SPALTE.PREIS_START] || '').trim();
    const seit = start ? ` (${t('card.priceStart')} ${start})` : '';
    if (row[SPALTE.EUR] === 0) return t('card.free') + seit;

    const roh = (row[SPALTE.PREIS] || '').trim();
    if (row[SPALTE.EUR] == null) return (roh || t('card.priceUnknown')) + seit;

    const eur = `${row[SPALTE.EUR].toLocaleString(FF.sprache(),
                                                  { minimumFractionDigits: 2 })} €`;
    // Fremde Währung: umgerechnet zeigen, den Originalpreis dahinter.
    if (FF.FREMDWAEHRUNG.test(roh)) return `${t('card.from')} ${eur} (${roh})` + seit;
    // Sonst den Quelltext nur zeigen, wenn er mehr sagt als die Zahl selbst.
    return (FF.preisZusatz(roh) ? roh : `${t('card.from')} ${eur}`) + seit;
  }

  function karte(s) {
    const row = s.row;
    const li = document.createElement('li');
    li.className = 'fest' + (s.pct !== null && s.pct >= 50 ? ' top' : '') +
                   (row[SPALTE.ABGESAGT] ? ' cancelled' : '');
    li.id = s.eintragId;
    li.append(kopf(s), fakten(s), treffernamen(s), lineup(s));
    return li;
  }

  function titel(row) {
    const h3 = document.createElement('h3');
    if (row[SPALTE.WEB]) {
      const a = document.createElement('a');
      a.href = row[SPALTE.WEB]; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = row[SPALTE.NAME];
      a.title = t('card.websiteTitle', { name: row[SPALTE.NAME] });
      h3.append(a);
    } else {
      h3.textContent = row[SPALTE.NAME];
    }
    return h3;
  }

  function kopf(s) {
    const row = s.row;
    const head = document.createElement('div');
    head.className = 'fest-head';

    const kasten = document.createElement('div');
    if (row[SPALTE.ABGESAGT]) {
      const flagge = document.createElement('span');
      flagge.className = 'flag';
      flagge.textContent = t('card.cancelled');
      flagge.title = t('card.cancelledTitle');
      kasten.append(flagge);
    }
    kasten.append(titel(row));
    head.append(kasten);

    if (s.pct !== null) {
      const pct = document.createElement('div');
      pct.className = 'pct';
      pct.textContent = `${s.pct.toFixed(0)} %`;
      const klein = document.createElement('small');
      klein.textContent = t('card.match');
      pct.append(klein);
      head.append(pct);
    }
    return head;
  }

  function fakten(s) {
    const row = s.row;
    const ul = document.createElement('ul');
    ul.className = 'facts';
    const platz = [row[SPALTE.ORT], row[SPALTE.STADT], row[SPALTE.LAND]]
      .filter(Boolean).join(', ');
    const zeilen = [
      [t('card.date'), termin(row)],
      [t('card.price'), preis(row)],
      [t('card.place'), platz || t('card.unknownPlace')],
      [t('card.distance'), s.dist === null
        ? (state.home ? t('card.unknownPlace') : t('card.noHomeSet'))
        : `${zahl(s.dist)} km`],
    ];
    for (const [k, v] of zeilen) {
      const el = document.createElement('li');
      el.innerHTML = `${k}: <b></b>`;
      el.querySelector('b').textContent = v;
      ul.append(el);
    }

    // Genre-Oberbegriffe des Festivals; die gewählten sind hervorgehoben.
    const genres = row[SPALTE.GENRES] || [];
    if (genres.length) {
      const el = document.createElement('li');
      el.className = 'genre-line';
      el.append(document.createTextNode(t('card.genre') + ': '));
      const getroffen = new Set(s.gHits);
      genres.forEach((g, n) => {
        const span = document.createElement(getroffen.has(g) ? 'mark' : 'b');
        span.textContent = FF.genreName(g);
        el.append(span);
        if (n < genres.length - 1) el.append(document.createTextNode(' · '));
      });
      ul.append(el);
    }

    if (row[SPALTE.WEB]) {
      const el = document.createElement('li');
      const a = document.createElement('a');
      a.href = row[SPALTE.WEB]; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = t('card.website');
      a.title = t('card.websiteTitle', { name: row[SPALTE.NAME] });
      el.append(a);
      ul.append(el);
    }
    return ul;
  }

  function treffernamen(s) {
    const p = document.createElement('p');
    p.className = 'hits';
    if (!s.hits.length) { p.hidden = true; return p; }
    const namen = s.hits.sort((a, b) => b[1] - a[1] ||
      BANDS[a[0]].localeCompare(BANDS[b[0]], FF.sprache()));
    p.append(document.createTextNode(t('card.yourBands')));
    namen.forEach(([b, w], n) => {
      const span = document.createElement('span');
      span.className = 'hit' + (w === 2 ? ' dbl' : '');
      span.textContent = BANDS[b];
      span.title = t(w === 2 ? 'card.bandDouble' : 'card.bandSingle',
                     { band: BANDS[b] });
      p.append(span);
      if (n < namen.length - 1) p.append(document.createTextNode(', '));
    });
    return p;
  }

  function lineup(s) {
    const row = s.row;
    const det = document.createElement('details');
    det.className = 'lineup';
    const kopfzeile = document.createElement('summary');
    kopfzeile.textContent = t('card.lineup', { n: row[SPALTE.LINEUP].length });
    kopfzeile.title = t('card.lineupTitle');

    const alle = document.createElement('div');
    alle.className = 'all';
    const gewaehlt = new Set(s.hits.map((h) => h[0]));
    const namen = row[SPALTE.LINEUP].map((b) => [BANDS[b], gewaehlt.has(b)])
      .sort((a, b) => a[0].localeCompare(b[0], FF.sprache()));
    namen.forEach(([n, istTreffer], k) => {
      const el = document.createElement(istTreffer ? 'mark' : 'span');
      el.textContent = n;
      alle.append(el);
      if (k < namen.length - 1) alle.append(document.createTextNode(' · '));
    });
    if (!namen.length) alle.textContent = t('card.noLineup');

    det.append(kopfzeile, alle);
    return det;
  }

  Object.assign(FF, { zeichnen, eintragZeigen, sortierungZeichnen });
})();
