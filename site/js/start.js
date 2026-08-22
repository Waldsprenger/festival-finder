/* Die Verdrahtung: was welcher Handgriff auslöst.

   Alles Übrige steht in den Modulen davor. Diese Datei kennt nur die Felder
   der Seite und ruft an, wer zuständig ist. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { $, t, zahl, state } = FF;
  const heute = new Date().toISOString().slice(0, 10);

  /* ---------------- Schritt 1: Ort ---------------- */

  async function ortSetzen() {
    const status = $('home-status');
    const eingabe = $('home').value;
    if (!eingabe.trim()) {
      status.className = 'hint err';
      status.textContent = t('home.statusStart');
      return;
    }
    status.className = 'hint';
    status.textContent = t('home.statusSearching');

    const treffer = await FF.wohnortSuchen(eingabe);
    if (!treffer || treffer.notFound) {
      state.home = null;
      status.className = 'hint err';
      status.textContent = treffer && treffer.notFound
        ? t('home.statusPlzUnknown', { code: treffer.notFound })
        : t('home.statusNotFound');
      FF.zeichnen();
      return;
    }

    state.home = treffer;
    status.className = 'hint ok';
    status.textContent = t('home.statusActive', { ort: treffer.label })
      + (treffer.ambiguous
          ? t('home.ambiguousPlz', {
              laender: treffer.ambiguous.join(', '),
              beispiel: `${eingabe.trim().split(/\s+/)[0]} ${treffer.ambiguous[0]}`,
            })
          : '')
      + (treffer.ambiguousName
          ? t('home.ambiguousName', { n: treffer.ambiguousName }) : '');

    // Die Währung folgt dem Wohnort, solange niemand selbst gewählt hat.
    if (!state.preis.gewaehlt) {
      state.preis.waehrung = FF.waehrungFuerLand(treffer.land);
      $('preis-waehrung').value = state.preis.waehrung;
      preisHinweis();
    }
    KARTE.zentrieren();
    FF.beantworten('ort');
  }

  /* ---------------- Schritt 2: Zeitraum ---------------- */

  /** Erklärt, warum ein Datum zurückgezogen wurde, und warnt vor
      Zeiträumen in der Vergangenheit. */
  function datumsHinweis(zuFrueh) {
    const el = $('date-hint');
    const z = state.zeit;
    const vergangen = (z.von && z.von < heute) || (z.bis && z.bis < heute);
    if (zuFrueh) {
      el.className = 'hint err';
      el.textContent = t('date.tooEarly', { datum: FF.datum(z.minDate) });
    } else if (vergangen) {
      el.className = 'hint warn';
      el.textContent = t('date.past');
    } else {
      el.className = 'hint';
      el.textContent = '';
    }
  }

  /* ---------------- Schritt 4: Preis ---------------- */

  /** Was die Grenzen in Euro bedeuten — bei fremder Währung nicht offensichtlich. */
  function preisHinweis() {
    const el = $('preis-hint');
    const p = state.preis;
    if (p.waehrung === 'EUR' || (p.von === null && p.bis === null)) {
      el.className = 'hint';
      el.textContent = '';
      return;
    }
    const inEuro = (v) => v === null ? '∞'
      : FF.nachEuro(v).toLocaleString(FF.sprache(), { maximumFractionDigits: 0 }) + ' €';
    el.className = 'hint';
    el.textContent = t('s4.inEuro', { von: inEuro(p.von ?? 0), bis: inEuro(p.bis) });
  }

  /* ---------------- Karte ----------------
     Sie kommt erst auf Wunsch: Sie zeigt das Ergebnis, nicht die Frage — und
     ein Canvas, das niemand ansieht, würde bei jeder Änderung mitgezeichnet. */

  let karteGestartet = false;

  function karteUmschalten(an) {
    state.karte = an;
    $('karte-block').hidden = !an;
    const knopf = $('karte-schalter');
    knopf.setAttribute('aria-expanded', String(an));
    knopf.textContent = t(an ? 'map.hide' : 'map.show');
    knopf.title = t(an ? 'map.hideTitle' : 'map.showTitle');
    if (!an) return;
    if (!karteGestartet) {
      karteStarten();
      karteGestartet = true;
    }
    // Erst jetzt hat das Canvas eine Breite - vorher wäre es 0 Pixel breit.
    KARTE.zeichnen();
  }

  function karteStarten() {
    KARTE.start({
      t,
      sprache: FF.sprache,
      wohnort: () => state.home,
      umkreisAktiv: () => state.entfernung.an && !!state.home,
      umkreisVon: () => state.entfernung.von ?? 0,
      umkreisBis: () => state.entfernung.bis,
      datenRahmen: () => FF.D.dataBox || null,
      welt: FF.D.world,
      weltFein: FF.D.worldFine,
      fineBox: FF.D.fineBox,
      // Ein Klick auf einen Pin springt zum Eintrag - notfalls muss die Karte
      // dafuer erst nachgezeichnet werden.
      aufPinKlick: (eintragId) => {
        const eintrag = FF.eintragZeigen(eintragId);
        if (!eintrag) return;
        eintrag.scrollIntoView({ behavior: 'smooth', block: 'center' });
        eintrag.classList.add('flash');
        setTimeout(() => eintrag.classList.remove('flash'), 1600);
      },
    });
  }

  /* ---------------- Kleinkram ---------------- */

  const datenstand = () => FF.stand(FF.D.generated, t);

  function datenstandZeigen() {
    $('build-info').textContent = t('footer.build', {
      stand: datenstand(),
      f: zahl(FF.F.length),
      a: zahl(FF.BANDS.length),
    });
  }

  /** Zahl aus einem Feld; leer heißt „keine Grenze". */
  function feldZahl(el) {
    const roh = el.value.trim();
    if (!roh) return null;
    const wert = Number(roh);
    return Number.isFinite(wert) && wert >= 0 ? wert : null;
  }

  /* ---------------- Verdrahtung ---------------- */

  function init() {
    // Untergrenze des Kalenders: Monatsanfang des frühesten Festivals im
    // Datenbestand. Voreingestellt bleibt heute, sofern das darin liegt.
    const minDate = FF.D.minDate || '';
    state.zeit.minDate = minDate;
    if (minDate) { $('from').min = minDate; $('to').min = minDate; }
    state.zeit.von = minDate && heute < minDate ? minDate : heute;
    $('from').value = state.zeit.von;

    // Währungen, für die ein Kurs vorliegt. Ohne Kurs wäre eine Grenze in
    // dieser Währung eine Zahl ohne Bedeutung.
    const wahl = $('preis-waehrung');
    for (const code of Object.keys(FF.KURSE).sort()) {
      const o = document.createElement('option');
      o.value = code;
      o.textContent = code;
      wahl.append(o);
    }
    wahl.value = state.preis.waehrung;

    // --- Schritt 1: Ort
    $('locate').addEventListener('click', ortSetzen);
    $('home').addEventListener('keydown', (e) => { if (e.key === 'Enter') ortSetzen(); });
    $('ort-skip').addEventListener('click', () => {
      state.home = null;
      $('home-status').className = 'hint';
      $('home-status').textContent = t('s1.sumNone');
      FF.beantworten('ort');
    });

    // --- Schritt 2: Zeitraum. Die Felder begrenzen sich gegenseitig, damit
    //     kein leerer Zeitraum entstehen kann.
    const klemme = (wert) => (state.zeit.minDate && wert && wert < state.zeit.minDate)
      ? state.zeit.minDate : wert;

    $('from').addEventListener('change', (e) => {
      const eingabe = e.target.value;
      e.target.value = klemme(eingabe);
      state.zeit.von = e.target.value;
      $('to').min = state.zeit.von || state.zeit.minDate || '';
      if (state.zeit.bis && state.zeit.von && state.zeit.bis < state.zeit.von) {
        state.zeit.bis = state.zeit.von;
        $('to').value = state.zeit.bis;
      }
      datumsHinweis(eingabe && eingabe !== e.target.value);
      FF.zeichnen();
    });

    $('to').addEventListener('change', (e) => {
      const eingabe = e.target.value;
      e.target.value = klemme(eingabe);
      state.zeit.bis = e.target.value;
      $('from').max = state.zeit.bis || '';
      if (state.zeit.von && state.zeit.bis && state.zeit.von > state.zeit.bis) {
        state.zeit.von = state.zeit.bis;
        $('from').value = state.zeit.von;
      }
      datumsHinweis(eingabe && eingabe !== e.target.value);
      FF.zeichnen();
    });

    $('date-unknown').addEventListener('change', (e) => {
      state.zeit.ohneTermin = e.target.checked; FF.zeichnen();
    });
    $('show-cancelled').addEventListener('change', (e) => {
      state.zeit.abgesagte = e.target.checked; FF.zeichnen();
    });

    // --- Ja/Nein aller Filterfragen
    for (const btn of document.querySelectorAll('[data-wahl]')) {
      btn.addEventListener('click', () => {
        FF.wahlSetzen(btn.dataset.wahl, btn.dataset.wert === 'ja');
      });
    }
    for (const btn of document.querySelectorAll('[data-weiter]')) {
      btn.addEventListener('click', () => FF.beantworten(btn.dataset.weiter));
    }

    // --- Schritt 3: Entfernung
    const kmLesen = () => {
      state.entfernung.von = feldZahl($('km-von'));
      state.entfernung.bis = feldZahl($('km-bis'));
      const e = state.entfernung;
      const el = $('km-hint');
      if (e.von !== null && e.bis !== null && e.von > e.bis) {
        el.className = 'hint err';
        el.textContent = t('s.rangeSwapped');
      } else {
        el.className = 'hint';
        el.textContent = state.home ? '' : t('s3.needHome');
      }
      FF.zeichnen();
    };
    $('km-von').addEventListener('input', kmLesen);
    $('km-bis').addEventListener('input', kmLesen);
    $('geo-unknown').addEventListener('change', (e) => {
      state.entfernung.ohneKoordinate = e.target.checked; FF.zeichnen();
    });

    // --- Schritt 4: Preis
    const preisLesen = () => {
      state.preis.von = feldZahl($('preis-von'));
      state.preis.bis = feldZahl($('preis-bis'));
      preisHinweis();
      FF.zeichnen();
    };
    $('preis-von').addEventListener('input', preisLesen);
    $('preis-bis').addEventListener('input', preisLesen);
    $('preis-waehrung').addEventListener('change', (e) => {
      state.preis.waehrung = e.target.value;
      state.preis.gewaehlt = true;      // ab jetzt nicht mehr vom Ort überschreiben
      preisHinweis();
      FF.zeichnen();
    });
    $('price-unknown').addEventListener('change', (e) => {
      state.preis.ohnePreis = e.target.checked; FF.zeichnen();
    });

    // --- Schritt 5: Bands
    let sucheTimer = null;
    $('band-search').addEventListener('input', () => {
      clearTimeout(sucheTimer);
      sucheTimer = setTimeout(FF.bandtrefferZeichnen, 120);
    });
    $('clear-bands').addEventListener('click', () => {
      state.bands.auswahl.clear();
      FF.bandauswahlZeichnen(); FF.bandtrefferZeichnen(); FF.zeichnen();
    });

    // --- Schritt 6: Genre
    $('clear-genres').addEventListener('click', () => {
      state.genre.auswahl.clear(); FF.genresZeichnen(); FF.zeichnen();
    });
    $('genre-unknown').addEventListener('change', (e) => {
      state.genre.ohneGenre = e.target.checked; FF.zeichnen();
    });

    // --- Ergebnis
    $('sort').addEventListener('change', (e) => {
      state.sortierung = e.target.value;
      FF.zeichnen();
    });
    $('karte-schalter').addEventListener('click', () => karteUmschalten(!state.karte));

    // --- Sprache: alles neu zeichnen, was Text aus dem Skript enthält
    FF.auswahlBauen(() => {
      FF.bandtrefferZeichnen();
      FF.bandauswahlZeichnen();
      FF.genresZeichnen();
      karteUmschalten(state.karte);
      datenstandZeigen();
      datumsHinweis(false);
      FF.zeichnen();
    });

    datenstandZeigen();
    datumsHinweis(false);
    FF.oberflaeche.hilfe();
    FF.oberflaeche.pwa();
    FF.oberflaeche.zaehler();
    FF.oberflaeche.rueckmeldung(t, datenstand);
    FF.oberflaeche.rechtstexte(t);
    FF.bandtrefferZeichnen();
    FF.bandauswahlZeichnen();
    FF.genresZeichnen();
    FF.zeichnen();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
