/* Namen zusammenfassen und Angaben darstellen.

   `fold` muss genauso arbeiten wie `fold()` im Sammler, sonst findet die Suche
   nicht, was in den Daten steht. Beide hatten früher ihre eigene Tabelle und
   sind auseinandergelaufen: bei 5.172 von 40.538 Bandnamen. Wer „2 Engel and
   Charlie" tippte, fand „2 Engel & Charlie" nicht.

   Jetzt steht die Tabelle in data/faltung.json, reist in data.js mit und wird
   hier gelesen. Auseinanderlaufen können sie nicht mehr. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const regeln = FF.D.faltung || {};
  const SONDERZEICHEN = regeln.sonderzeichen || [];
  const ERSATZ = regeln.ersatz || [];
  const VERBINDER = new RegExp('\\b(' + (regeln.verbinder || []).join('|') + ')\\b', 'g');
  const ARTIKEL = new RegExp('^(' + (regeln.artikel || []).join('|') + ') ');
  const ZUSATZ = new RegExp(' (' + (regeln.zusatz || []).join('|') + ')$');

  const gemerkt = new Map();

  /** Aggressiver Schlüssel für den Namensvergleich. */
  function fold(s) {
    let v = gemerkt.get(s);
    if (v !== undefined) return v;
    v = String(s).toLowerCase().normalize('NFKD').replace(/\p{M}+/gu, '');
    for (const [a, b] of SONDERZEICHEN) v = v.split(a).join(b);
    for (const [a, b] of ERSATZ) v = v.split(a).join(b);
    v = v.replace(VERBINDER, ' and ')
         .replace(/[^\p{L}\p{N}]+/gu, ' ')
         .replace(/\s+/g, ' ').trim()
         .replace(ARTIKEL, '')
         .replace(ZUSATZ, '');
    gemerkt.set(s, v);
    return v;
  }

  /* ---------------- Darstellung ---------------- */

  /** „2026-08-19" → „19.08.2026" */
  const datum = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}.${m}.${y}`;
  };

  /** Datenstand mit Uhrzeit: „10.08.2026 um 14:32 Uhr" */
  function stand(stempel, t) {
    if (!stempel) return 'unbekannt';
    const m = String(stempel).match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
    if (!m) return stempel;
    const tag = `${m[3]}.${m[2]}.${m[1]}`;
    return m[4] ? t('stand.at', { datum: tag, zeit: `${m[4]}:${m[5]}` }) : tag;
  }

  /** Was bleibt vom Preistext, wenn Betrag, Währung und „ab" weg sind?

      „ab 12,90 Eur" sagt nichts, was die Zahl nicht schon sagt — angezeigt
      wurde daraus „ab 12,90 € (ab 12,90 Eur)", zweimal dasselbe. „VVK 22,50 €
      | AK 24 €" dagegen trägt zwei Preise und gehört im Wortlaut auf die
      Karte. */
  function preisZusatz(roh) {
    return roh
      .replace(/\d+(?:[.,]\d+)?/g, ' ')
      .replace(/€|\bEUR\b|\bab\b|\bfrom\b/gi, ' ')
      .replace(/[^\p{L}]+/gu, ' ')
      .trim();
  }

  /** „Zeitraum, Entfernung und Preis" — in der Sprache, die gerade gilt. */
  function aufzaehlen(teile, sprache) {
    try {
      return new Intl.ListFormat(sprache, { style: 'long', type: 'conjunction' })
        .format(teile);
    } catch (_) {
      return teile.join(', ');   // aeltere Browser bekommen die Kommafassung
    }
  }

  //: Währungen, die erst umgerechnet vergleichbar sind
  const FREMDWAEHRUNG = /\b(CHF|GBP|USD|DKK|SEK|NOK|PLN|CZK|HUF)\b|£|\$/i;

  Object.assign(FF, { fold, datum, stand, preisZusatz, aufzaehlen, FREMDWAEHRUNG });
})();
