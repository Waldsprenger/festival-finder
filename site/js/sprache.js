/* Zehn Sprachen, eine Funktion.

   Die Texte stehen in i18n.js. Fehlt eine Übersetzung, greift Deutsch; die
   Seite bleibt damit auch bei unvollständiger Sprachdatei benutzbar. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

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

      Eine Zahl im Hilfetext veraltet still: „rund 450 Festivals ohne Preis"
      stand in zehn Sprachen da, während es längst dreimal so viele waren. */
  function hilfszahlen() {
    const { F, SPALTE } = FF;
    return {
      ohnePreis: zahl(F.reduce((n, r) => n + (r[SPALTE.EUR] === null ? 1 : 0), 0)),
      ohneGenre: zahl(F.reduce((n, r) => n + ((r[SPALTE.GENRES] || []).length ? 0 : 1), 0)),
    };
  }

  /** Trägt alle ausgezeichneten Texte im Dokument neu ein. */
  function anwenden() {
    document.documentElement.lang = sprache;
    const zahlen = hilfszahlen();
    const setzen = (attribut, wie) => {
      for (const el of document.querySelectorAll(`[${attribut}]`)) {
        wie(el, el.getAttribute(attribut));
      }
    };
    setzen('data-i18n', (el, k) => { el.textContent = t(k); });
    setzen('data-i18n-html', (el, k) => { el.innerHTML = t(k); });
    setzen('data-i18n-title', (el, k) => { el.title = t(k, zahlen); });
    setzen('data-i18n-ph', (el, k) => { el.placeholder = t(k); });
    setzen('data-i18n-aria', (el, k) => { el.setAttribute('aria-label', t(k)); });

    const titel = t('html.title');
    if (titel) document.title = titel;

    // Rechtstexte bleiben auf Deutsch - der Hinweis erscheint nur, wenn nötig
    const hinweis = FF.$('legal-note');
    if (hinweis) hinweis.hidden = !t('legal.germanOnly');
  }

  /** Baut die Sprachauswahl; `beiWechsel` zeichnet neu, was Text enthält. */
  function auswahlBauen(beiWechsel) {
    const wahl = FF.$('lang');
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
      anwenden();
      beiWechsel();
    });
    anwenden();
  }

  Object.assign(FF, {
    t, zahl, anwenden, auswahlBauen,
    sprache: () => sprache,
  });
})();
