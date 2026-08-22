/* Die Kette: eine Frage nach der anderen.

   Sechs Schritte bauen sich nacheinander auf. Jeder beantwortete klappt zu
   einer Zeile zusammen, bevor der nächste erscheint — sechs offene Panels
   übereinander wären dieselbe lange Seite wie vorher, nur langsamer
   aufgedeckt. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { $, t, zahl, state, KETTE, uebrig } = FF;

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
        if (z.von && z.bis) return an(t('s2.sum', { von: FF.datum(z.von),
                                                    bis: FF.datum(z.bis) }));
        if (z.von) return an(t('s2.sumFrom', { von: FF.datum(z.von) }));
        if (z.bis) return an(t('s2.sumTo', { bis: FF.datum(z.bis) }));
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
        const w = FF.WAEHRUNG_ZEICHEN[p.waehrung] || p.waehrung;
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
        FF.zeichnen();
        sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      kurz.append(text, knopf);
      sec.querySelector('h2').append(kurz);
    }
    const { text, aktiv } = zusammenfassung(name);
    const feld = kurz.querySelector('.kurz-text');
    feld.textContent = text;
    feld.className = 'kurz-text' + (aktiv ? '' : ' aus');
    const knopf = kurz.querySelector('button');
    knopf.textContent = t('s.change');
    knopf.title = t('s.changeTitle');
    return kurz;
  }

  /** Baut die Kette neu auf: was sichtbar ist, was offen, was zusammengeklappt. */
  function zeichnen() {
    let davorBeantwortet = true;
    for (const name of KETTE) {
      const sec = sektion(name);
      const beantwortet = !!state.antwort[name];
      sec.hidden = !davorBeantwortet;
      // Aufgeklappt ist, was offen gewählt wurde — und alles noch
      // Unbeantwortete, damit nie ein Schritt ohne Inhalt dasteht.
      const offen = name === state.offen || !beantwortet;
      sec.classList.toggle('erledigt', !offen);
      sec.classList.toggle('dran', offen && davorBeantwortet && !beantwortet);
      sec.querySelector('.koerper').hidden = !offen;
      kurzzeile(sec, name).hidden = offen;

      if (!sec.hidden) {
        const rest = sec.querySelector('[data-rest]');
        if (rest) {
          rest.innerHTML = t('s.rest', { n: '<b>' + zahl(uebrig(name)) + '</b>',
                                         gesamt: zahl(FF.F.length) });
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
    FF.zeichnen();
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
    if (!state.antwort[name]) {
      if (an) {
        // „Ja" beantwortet die Frage auch — der Inhalt bleibt aber offen,
        // damit man ihn gleich ausfüllen kann.
        state.antwort[name] = true;
        state.offen = name;
        FF.zeichnen();
        return;
      }
      beantworten(name);
      return;
    }
    FF.zeichnen();
  }

  Object.assign(FF, { ketteZeichnen: zeichnen, beantworten, wahlSetzen, sektion });
})();
