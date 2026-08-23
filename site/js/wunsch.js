/* Gemerkte Suchen — und was seit dem letzten Besuch dazugekommen ist.

   Alles bleibt auf dem Gerät. Gespeichert wird im Anwendungsspeicher des
   Browsers, verglichen wird hier; nichts davon geht an einen Server, und es
   gibt kein Konto. Wer eine Suche aufs zweite Gerät bringen will, nimmt den
   Link: Der Filter steht darin.

   Bands werden als Namen gemerkt, nicht als Nummern. Die Nummern in data.js
   vergibt der Bau bei jedem Lauf neu, in der Reihenfolge des Auftretens — eine
   gemerkte 4711 meinte morgen eine andere Band. Genauso bei den Genres: dort
   steht der Schlüssel, nicht die Spaltennummer.

   `neu.json` bringt mit, was in den letzten dreißig Tagen dazugekommen ist:
   ganze Festivals und einzeln bestätigte Bands. Geprüft wird damit über
   `FF.PRUEFUNG` — dieselben Regeln wie für die Liste, nur mit dem gemerkten
   Filter statt dem eingestellten. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { $, t, zahl, D, BANDS, GENRES, SPALTE, state, PRUEFUNG } = FF;

  const SPEICHER = 'ff.listen.v1';
  //: So viele Suchen darf man merken — mehr verwaltet niemand
  const HOECHSTENS = 20;

  /* ---------------- Ablage ----------------
     Der Anwendungsspeicher kann fehlen: privates Fenster, abgeschaltet, voll.
     Dann gibt es eben keine gemerkten Suchen — die Seite läuft trotzdem. */

  function lesen() {
    try {
      const listen = JSON.parse(localStorage.getItem(SPEICHER) || '[]');
      return Array.isArray(listen) ? listen : [];
    } catch (_) {
      return [];
    }
  }

  function schreiben(listen) {
    try {
      localStorage.setItem(SPEICHER, JSON.stringify(listen));
      return true;
    } catch (_) {
      return false;
    }
  }

  function verfuegbar() {
    try {
      localStorage.setItem(SPEICHER + '.probe', '1');
      localStorage.removeItem(SPEICHER + '.probe');
      return true;
    } catch (_) {
      return false;
    }
  }

  /* ---------------- Filter ein- und auspacken ---------------- */

  const bandNr = new Map(BANDS.map((n, i) => [n, i]));
  const genreNr = new Map(GENRES.map((k, i) => [k, i]));

  function einpacken() {
    return {
      v: 1,
      home: state.home && { lat: state.home.lat, lon: state.home.lon,
                            label: state.home.label, land: state.home.land },
      zeit: { von: state.zeit.von, bis: state.zeit.bis,
              ohneTermin: state.zeit.ohneTermin, abgesagte: state.zeit.abgesagte },
      entfernung: { an: state.entfernung.an, von: state.entfernung.von,
                    bis: state.entfernung.bis,
                    ohneKoordinate: state.entfernung.ohneKoordinate },
      preis: { an: state.preis.an, von: state.preis.von, bis: state.preis.bis,
               waehrung: state.preis.waehrung, ohnePreis: state.preis.ohnePreis },
      bands: { an: state.bands.an,
               namen: [...state.bands.auswahl].map(([i, w]) => [BANDS[i], w]) },
      genre: { an: state.genre.an, ohneGenre: state.genre.ohneGenre,
               keys: [...state.genre.auswahl].map((i) => GENRES[i]) },
    };
  }

  /** Ein gemerkter Filter in der Form, die `FF.PRUEFUNG` erwartet.

      Namen, die es nicht mehr gibt, fallen weg: Eine Band kann aus allen
      Quellen verschwinden. Bliebe ihre Nummer `undefined` stehen, träfe die
      Prüfung nie zu, und die Suche wäre stumm, ohne dass jemand sähe, warum. */
  function auspacken(f) {
    const auswahl = new Map();
    for (const [name, gewicht] of (f.bands && f.bands.namen) || []) {
      const nr = bandNr.get(name);
      if (nr !== undefined) auswahl.set(nr, gewicht || 1);
    }
    const genres = new Set();
    for (const key of (f.genre && f.genre.keys) || []) {
      const nr = genreNr.get(key);
      if (nr !== undefined) genres.add(nr);
    }
    return {
      home: f.home || null,
      zeit: { von: '', bis: '', ohneTermin: false, abgesagte: false, ...f.zeit },
      entfernung: { an: false, von: null, bis: null, ohneKoordinate: false,
                    ...f.entfernung },
      preis: { an: false, von: null, bis: null, waehrung: 'EUR', ohnePreis: true,
               ...f.preis },
      bands: { an: !!(f.bands && f.bands.an), auswahl },
      genre: { an: !!(f.genre && f.genre.an), auswahl: genres,
               ohneGenre: !!(f.genre && f.genre.ohneGenre) },
    };
  }

  /** Eine gemerkte Suche wieder einstellen. */
  function anwenden(eintrag) {
    const f = auspacken(eintrag.filter);
    state.home = f.home;
    Object.assign(state.zeit, f.zeit);
    Object.assign(state.entfernung, f.entfernung);
    Object.assign(state.preis, f.preis);
    state.bands.an = f.bands.an;
    state.bands.auswahl = f.bands.auswahl;
    state.genre.an = f.genre.an;
    state.genre.auswahl = f.genre.auswahl;
    state.genre.ohneGenre = f.genre.ohneGenre;
    // Alles beantwortet: Wer eine gemerkte Suche öffnet, will das Ergebnis
    // sehen und nicht sechs Fragen noch einmal durchklicken.
    for (const schritt of FF.KETTE) state.antwort[schritt] = true;
    state.offen = null;
  }

  /* ---------------- Teilen ---------------- */

  const nachText = (s) => btoa(unescape(encodeURIComponent(s)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const ausText = (s) => decodeURIComponent(escape(
    atob(s.replace(/-/g, '+').replace(/_/g, '/'))));

  function alsLink(eintrag) {
    return location.origin + location.pathname + '#l='
      + nachText(JSON.stringify({ n: eintrag.name, f: eintrag.filter }));
  }

  /** Eine geteilte Suche aus dem Adressfeld — oder nichts. */
  function ausLink() {
    const treffer = (location.hash || '').match(/[#&]l=([A-Za-z0-9_-]+)/);
    if (!treffer) return null;
    try {
      const kern = JSON.parse(ausText(treffer[1]));
      if (!kern || !kern.f) return null;
      return { name: String(kern.n || '').slice(0, 60) || t('lists.shared'),
               filter: kern.f, gesehen: FF.heute() };
    } catch (_) {
      return null;                  // beschädigter Link, kein Grund zum Absturz
    }
  }

  /* ---------------- Was ist dazugekommen? ---------------- */

  let neuigkeiten = null;

  /** `neu.json` holen. Fehlt sie oder stammt sie aus einem anderen Lauf,
      bleibt es bei nichts: Ihre Genre-Nummern gälten sonst für eine andere
      data.js, und die Meldung wäre schlicht falsch. */
  async function laden() {
    if (neuigkeiten) return neuigkeiten;
    try {
      const res = await fetch('neu.json', { cache: 'no-cache' });
      const inhalt = res.ok ? await res.json() : null;
      neuigkeiten = inhalt && inhalt.stand === D.generated
        ? (inhalt.eintraege || []) : [];
    } catch (_) {
      neuigkeiten = [];             // offline oder per file:// geöffnet
    }
    return neuigkeiten;
  }

  /** Die Neuzugänge, auf die eine gemerkte Suche zutrifft.

      Die Bandregel ist hier eine andere als in der Liste, und das mit Absicht:
      Bei einem Festival, das gestern schon dastand, zählt nur, wer seither
      dazukam — sonst meldete Wacken jeden Tag aufs Neue dieselbe Band. Ein
      ganz neues Festival dagegen ist auch ohne Bandauswahl eine Meldung wert;
      es erfüllt ja die übrigen Bedingungen. */
  function treffer(eintrag, alle) {
    const f = auspacken(eintrag.filter);
    const seit = eintrag.gesehen || '';
    const gewuenscht = new Set([...f.bands.auswahl.keys()].map((nr) => BANDS[nr]));
    const nachBands = f.bands.an && gewuenscht.size;

    return (alle || neuigkeiten || []).filter((e) => {
      if (e.seit <= seit) return false;
      if (e.g === 'lineup' && !nachBands) return false;
      if (nachBands && !e.b.some((name) => gewuenscht.has(name))) return false;
      return PRUEFUNG.zeit(f, e.z) && PRUEFUNG.entfernung(f, e.z)
          && PRUEFUNG.preis(f, e.z) && PRUEFUNG.genre(f, e.z);
    });
  }

  /* ---------------- Verwalten ---------------- */

  const alle = lesen;

  function merken(name) {
    const listen = lesen().filter((l) => l.name !== name);
    if (listen.length >= HOECHSTENS) return false;
    listen.unshift({ name, filter: einpacken(), gesehen: FF.heute() });
    return schreiben(listen);
  }

  function uebernehmen(eintrag) {
    const listen = lesen().filter((l) => l.name !== eintrag.name);
    if (listen.length >= HOECHSTENS) return false;
    listen.unshift(eintrag);
    return schreiben(listen);
  }

  function loeschen(name) {
    return schreiben(lesen().filter((l) => l.name !== name));
  }

  /** „Alles bis hier kenne ich" — der Ausgangspunkt fürs nächste Mal. */
  function gesehen(name) {
    const listen = lesen();
    const eintrag = listen.find((l) => l.name === name);
    if (!eintrag) return false;
    eintrag.gesehen = FF.heute();
    return schreiben(listen);
  }

  /* ---------------- Anzeige ---------------- */

  function knopf(schluessel, tun) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'ghost small';
    b.textContent = t(schluessel);
    b.addEventListener('click', tun);
    return b;
  }

  /** Ein Neuzugang mit Termin und Ort — wer nachsieht, will beides mitlesen. */
  function neuzeile(e) {
    const li = document.createElement('li');
    const name = document.createElement('b');
    name.textContent = e.z[SPALTE.NAME];
    const wo = [FF.termin(e.z),
                [e.z[SPALTE.STADT], e.z[SPALTE.LAND]].filter(Boolean).join(', ')]
      .filter(Boolean).join(' · ');
    const rest = document.createElement('span');
    rest.textContent = wo ? ' — ' + wo : '';
    li.append(name, rest);
    if (e.b.length) {
      const bands = document.createElement('div');
      bands.className = 'hint';
      bands.textContent = t(e.g === 'neu' ? 'lists.withBands' : 'lists.newBands',
                            { bands: e.b.slice(0, 8).join(', ') });
      li.append(bands);
    }
    return li;
  }

  function eintragZeichnen(l, neu) {
    const li = document.createElement('li');
    const kopf = document.createElement('div');
    kopf.className = 'wunsch-kopf';

    const name = document.createElement('b');
    name.textContent = l.name;
    kopf.append(name);

    if (neu.length) {
      const marke = document.createElement('span');
      marke.className = 'marke';
      marke.textContent = neu.length === 1 ? t('lists.newOne')
        : t('lists.newMany', { n: zahl(neu.length) });
      kopf.append(marke);
    }

    const knoepfe = document.createElement('div');
    knoepfe.className = 'wunsch-knoepfe';
    knoepfe.append(
      knopf('lists.open', () => {
        anwenden(l);
        FF.zeichnen();
        $('s-ergebnis').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }),
      knopf('lists.share', async (ev) => {
        try {
          await navigator.clipboard.writeText(alsLink(l));
          ev.target.textContent = t('lists.copied');
          setTimeout(() => { ev.target.textContent = t('lists.share'); }, 2000);
        } catch (_) {
          prompt(t('lists.share'), alsLink(l));   // ohne Zwischenablage
        }
      }),
      knopf('lists.delete', () => {
        loeschen(l.name);
        zeichnen();
      }));
    kopf.append(knoepfe);
    li.append(kopf);

    if (neu.length) {
      const liste = document.createElement('ul');
      liste.className = 'wunsch-neu';
      for (const e of neu.slice(0, 25)) liste.append(neuzeile(e));
      li.append(liste, knopf('lists.read', () => {
        gesehen(l.name);
        zeichnen();
      }));
    }
    return li;
  }

  /** Die ganze Liste neu aufbauen, samt Kopfmeldung. */
  function zeichnen() {
    const listen = lesen();
    const abschnitt = $('s-wunsch');
    abschnitt.hidden = !listen.length;
    const ziel = $('wunsch-liste');
    ziel.innerHTML = '';

    let gesamt = 0;
    for (const l of listen) {
      const neu = treffer(l);
      gesamt += neu.length;
      ziel.append(eintragZeichnen(l, neu));
    }

    const kopf = $('wunsch-stat');
    kopf.textContent = !listen.length ? ''
      : gesamt === 0 ? t('lists.nothingNew')
      : gesamt === 1 ? t('lists.bannerOne')
      : t('lists.banner', { n: zahl(gesamt) });
    kopf.className = 'stat' + (gesamt ? ' ok' : '');
    merkenZeichnen();
  }

  /** Der Knopf unter den Treffern: heißt „merken" oder „auffrischen". */
  function merkenZeichnen() {
    const feld = $('merk-name');
    if (!feld) return;
    const schon = lesen().some((l) => l.name === feld.value.trim());
    $('merk-speichern').textContent = t(schon ? 'lists.update' : 'lists.save');
  }

  function speichern() {
    const hinweis = $('merk-hint');
    const name = $('merk-name').value.trim();
    if (!verfuegbar()) {
      hinweis.className = 'hint err';
      hinweis.textContent = t('lists.noStore');
      return;
    }
    if (!name) {
      hinweis.className = 'hint err';
      hinweis.textContent = t('lists.needName');
      return;
    }
    if (!merken(name)) {
      hinweis.className = 'hint err';
      hinweis.textContent = t('lists.full', { n: zahl(HOECHSTENS) });
      return;
    }
    hinweis.className = 'hint ok';
    hinweis.textContent = t('lists.saved', { name });
    zeichnen();
  }

  /** Beim Laden: eine geteilte Suche übernehmen, dann alles zeichnen. */
  async function start() {
    $('merk-speichern').addEventListener('click', speichern);
    $('merk-name').addEventListener('input', merkenZeichnen);
    $('merk-name').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') speichern();
    });

    // Auch später noch: Wer den Link antippt, während die App schon offen
    // ist, bekommt keinen Seitenaufbau — nur ein neues Adressfeld.
    window.addEventListener('hashchange', geteiltesUebernehmen);
    geteiltesUebernehmen();
    await laden();
    zeichnen();
  }

  function geteiltesUebernehmen() {
    const geteilt = ausLink();
    if (!geteilt || !verfuegbar()) return;
    uebernehmen(geteilt);
    history.replaceState(null, '', location.pathname + location.search);
    anwenden(geteilt);
    FF.zeichnen();
    zeichnen();
  }

  Object.assign(FF, {
    wunsch: { start, zeichnen, alle, merken, loeschen, gesehen, anwenden,
              alsLink, ausLink, treffer, laden, verfuegbar, HOECHSTENS },
  });
})();
