/* Von einer Eingabe zu einem Punkt auf der Erde — aus jedem Land.

   Wer seinen Wohnort eingibt, schreibt ihn, wie man ihn dort schreibt:
   „97209 Veitshöchheim", „Austin, TX", „SW1A 1AA", „〒100-0001 東京都千代田区",
   „1600 Pennsylvania Ave NW, Washington, DC 20500". Die Eingabe wird deshalb
   zuerst zerlegt — Postleitzahl, Ort, Bundesstaat, Land; was übrig bleibt,
   ist Straße und Hausnummer und spielt für einen Umkreis in Kilometern keine
   Rolle. Dann wird sie gegen die Verzeichnisse gelegt:

   1. geo.js: Postleitzahlen von DE/AT/CH, Orte ab 15.000 Einwohnern.
   2. orte.js: Orte ab 1.000 Einwohnern, Zweitnamen großer Städte
      („Warszawa", „Москва", „東京").
   3. plz.js: Postleitzahlen aus 117 Ländern, auf fünf Kilometer verdichtet.
   4. Erst wenn nichts davon passt: Nominatim.

   Die ersten drei laufen im Browser; die Eingabe verlässt das Gerät dabei
   nicht. orte.js und plz.js werden nur geholt, wenn die Eingabe sie braucht —
   wer „97209" eingibt, lädt keine von beiden. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { D, fold } = FF;

  /* ---------------- Nachladen ---------------- */

  /* In der Einzelseite gibt es die Dateien nicht; dort bleibt es bei geo.js. */
  const geladen = {};
  function nachladen(datei, name) {
    if (!geladen[datei]) {
      const stand = (D.versionen || {})[datei];
      geladen[datei] = new Promise((fertig) => {
        if (window[name]) return fertig(window[name]);
        const laden = (src, sonst) => {
          const s = document.createElement('script');
          s.src = src;
          s.onload = () => fertig(window[name] || null);
          s.onerror = sonst;
          document.head.append(s);
        };
        const ohne = () => laden(`${datei}.js`, () => fertig(null));
        if (stand) laden(`${datei}.js?v=${stand}`, ohne); else ohne();
      });
    }
    return geladen[datei];
  }
  const grossesVerzeichnis = () => nachladen('orte', 'ORTE_WELT');
  const plzDerWelt = () => nachladen('plz', 'PLZ_WELT');

  /* ---------------- Entfernung ---------------- */

  function km(a, b) {
    const r = Math.PI / 180;
    const h = Math.sin((b.lat - a.lat) * r / 2) ** 2
      + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin((b.lon - a.lon) * r / 2) ** 2;
    return 12742 * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  /* ---------------- Länder ---------------- */

  const ISO = new Set(D.laender || []);

  /* Ländernamen in den Sprachen, in denen Adressen geschrieben werden. Der
     Browser kennt sie (Intl.DisplayNames) — mitgeliefert wird nichts. */
  const SPRACHEN = ['de', 'en', 'fr', 'es', 'it', 'nl', 'pl', 'pt', 'ru', 'tr', 'ja', 'zh',
    'ko', 'ar', 'sv', 'da', 'nb', 'fi', 'cs', 'sk', 'hu', 'ro', 'el', 'uk', 'he', 'hi', 'th',
    'vi', 'id', 'hr', 'sr', 'bg', 'sl', 'lt', 'lv', 'et', 'is', 'ca', 'fa', 'ms'];
  const LAND_NEBENNAMEN = {
    usa: 'US', 'u s a': 'US', 'u s': 'US', america: 'US', 'united states of america': 'US',
    uk: 'GB', 'u k': 'GB', 'great britain': 'GB', britain: 'GB', england: 'GB',
    scotland: 'GB', wales: 'GB', 'northern ireland': 'GB', holland: 'NL', uae: 'AE',
    'czech republic': 'CZ', turkey: 'TR', 'south korea': 'KR', korea: 'KR',
    'ivory coast': 'CI', burma: 'MM', vatican: 'VA', macedonia: 'MK', swaziland: 'SZ',
  };
  let landNamen = null;
  function laenderNamen() {
    if (landNamen) return landNamen;
    landNamen = new Map();
    const setze = (name, cc) => {
      const f = fold(name);
      if (f && !landNamen.has(f)) landNamen.set(f, cc);
    };
    for (const [name, cc] of Object.entries(LAND_NEBENNAMEN)) setze(name, cc);
    for (const sprache of SPRACHEN) {
      let namen;
      try { namen = new Intl.DisplayNames([sprache], { type: 'region' }); } catch (_) { continue; }
      for (const cc of ISO) {
        try { const n = namen.of(cc); if (n && n !== cc) setze(n, cc); } catch (_) { /* unbekannt */ }
      }
    }
    return landNamen;
  }

  /* Fahrzeug- und Landeskennzeichen vor Postleitzahlen: „D-97209", „CH-8001". */
  const KENNZEICHEN = { D: 'DE', A: 'AT', F: 'FR', I: 'IT', L: 'LU', B: 'BE', S: 'SE', N: 'NO',
    P: 'PT', E: 'ES', H: 'HU', M: 'MT', FIN: 'FI', SLO: 'SI', EST: 'EE', IRL: 'IE', AND: 'AD',
    FL: 'LI', RSM: 'SM', RUS: 'RU', SRB: 'RS', MNE: 'ME', BIH: 'BA', USA: 'US' };
  const kennzeichen = (k) => KENNZEICHEN[k] || (ISO.has(k) ? k : '');

  /* Woher die Seite kommt, verrät der Browser: „en-US", „pt-BR". Ohne Region
     zählt die Sprache — außer Englisch, das in zu vielen Ländern zu Hause ist. */
  const SPRACHLAND = { de: 'DE', fr: 'FR', es: 'ES', it: 'IT', nl: 'NL', pl: 'PL', pt: 'PT',
    ru: 'RU', tr: 'TR', ja: 'JP', ko: 'KR', zh: 'CN', sv: 'SE', da: 'DK', nb: 'NO', nn: 'NO',
    no: 'NO', fi: 'FI', cs: 'CZ', sk: 'SK', hu: 'HU', ro: 'RO', el: 'GR', uk: 'UA', he: 'IL',
    bg: 'BG', hr: 'HR', sl: 'SI', lt: 'LT', lv: 'LV', et: 'EE', is: 'IS', th: 'TH', vi: 'VN',
    id: 'ID' };
  function heimatLaender() {
    const liste = [];
    for (const tag of [...(navigator.languages || [navigator.language || '']), FF.sprache()]) {
      const [sprache, ...rest] = String(tag || '').split('-');
      const region = rest.find((t) => /^[A-Za-z]{2}$/.test(t));
      const cc = region ? region.toUpperCase() : SPRACHLAND[sprache.toLowerCase()];
      if (cc && !liste.includes(cc)) liste.push(cc);
    }
    return liste;
  }

  /* ---------------- Bundesstaaten ---------------- */

  /** fold(Kürzel oder Name) → Bundesstaaten. „WA" ist Washington und
      Western Australia, „NT" das Northern Territory und die Northwest
      Territories — beide bleiben im Rennen, der Ort entscheidet. */
  let staatNamen = null;
  function staatenTabelle(geo) {
    if (staatNamen) return staatNamen;
    staatNamen = new Map();
    for (const [cc, staaten] of Object.entries(geo.verwaltung || {})) {
      for (const [kuerzel, [lat, lon, name]] of Object.entries(staaten)) {
        const eintrag = { cc, kuerzel, lat, lon, name };
        for (const schluessel of [`k:${kuerzel}`, `n:${fold(name)}`]) {
          if (!staatNamen.has(schluessel)) staatNamen.set(schluessel, []);
          staatNamen.get(schluessel).push(eintrag);
        }
      }
    }
    return staatNamen;
  }

  /* ---------------- Postleitzahlen erkennen ---------------- */

  const L = '(?<![\\p{L}\\p{N}])', R = '(?![\\p{L}\\p{N}])';
  const muster = (quelle) => new RegExp(L + quelle + R, 'gu');

  /* Ganze Postleitzahlen, deren Verzeichnis nur den vorderen Teil kennt: In
     Großbritannien, Kanada und Irland führt GeoNames den Bezirk, in den
     Niederlanden die Ziffern, in den USA die fünfstellige ZIP. */
  const SONDERFORMEN = [
    { re: muster('([A-Z]{1,2}\\d[A-Z\\d]?)\\s?\\d[A-Z]{2}'), laender: ['GB', 'IM', 'JE', 'GG'] },
    { re: muster('([A-Z]\\d[A-Z])\\s?\\d[A-Z]\\d'), laender: ['CA'] },
    { re: muster('([AC-FHKNPRTV-Y]\\d{2}|D6W)\\s?[0-9AC-FHKNPRTV-Y]{4}'), laender: ['IE'] },
    { re: muster('(\\d{5})[-\\s]\\d{4}'), laender: ['US', 'PR', 'GU', 'VI'] },
    { re: muster('[A-Z](\\d{4})[A-Z]{3}'), laender: ['AR'] },
    { re: muster('([A-Z]{3})\\s?\\d{4}'), laender: ['MT'] },
  ];
  // Vier Ziffern und zwei Buchstaben: „1012 AB" in den Niederlanden — oder
  // eine Postleitzahl mit Land, „1010 AT", „2000 AU"
  const VIER_ZWEI = muster('(\\d{4})\\s?([A-Z]{2})');
  // Ziffern mit höchstens einem Trenner: „97209", „114 55", „100-0001", „01310-100"
  const ZIFFERN = muster('(\\d{2,7})(?:[-\\s](\\d{2,5}))?');
  // Mit Kennzeichen davor: „D-97209", „CH-8001", „LV-1050", „AD500"
  const MIT_KENNZEICHEN = muster('([A-Z]{1,3})-?\\s?(\\d{3,6})');
  // Ein Bezirk allein: „SW1A", „M5V", „D02"
  const BEZIRK = muster('([A-Z]{1,2}\\d[A-Z\\d]?)');

  const formVon = (code) => code.replace(/[A-Z]/g, 'A').replace(/\d/g, '9')
    .replace(/[\s.-]+/g, '-');
  // Gesetzt von `suchen`, sobald geo.js da ist
  let formenTabelle = {};
  const schluessel = (code) => code.replace(/[^0-9A-Z]/g, '');

  /** Alle Stellen eines Textstücks, die eine Postleitzahl sein könnten —
      und die Länder, die dabei genannt sind („2000 AU", „D-97209"). */
  function plzKandidaten(text, teil) {
    const gross = text.toUpperCase();
    const gefunden = [];
    const laender = [];
    const kuerzel = [];
    const dazu = (roh, code, nurIn, rang, index, formPruefen = false) => gefunden.push({
      roh: roh.trim(), schluessel: schluessel(code), form: formVon(code.trim()),
      laender: nurIn, rang, teil, index, formPruefen,
    });
    for (const { re, laender: nurIn } of SONDERFORMEN) {
      for (const m of gross.matchAll(re)) dazu(m[0], m[1], nurIn, 0, m.index);
    }
    for (const m of gross.matchAll(VIER_ZWEI)) {
      if (ISO.has(m[2])) {
        laender.push(m[2]);
        dazu(m[1], m[1], [m[2]], 0, m.index, true);
      }
      dazu(m[0], m[1], ['NL'], 0, m.index);
    }
    for (const m of gross.matchAll(MIT_KENNZEICHEN)) {
      const cc = kennzeichen(m[1]);
      // „IN 46201" ist Indiana, keine indische Postleitzahl: Die Form muss passen
      if (cc) dazu(m[0], m[2], [cc], 0, m.index, true);
      // Das Kürzel davor ist ein Land oder ein Bundesstaat: „D-97209", „IL 62701"
      if (KENNZEICHEN[m[1]]) laender.push(KENNZEICHEN[m[1]]); else kuerzel.push(m[1]);
    }
    for (const m of gross.matchAll(ZIFFERN)) {
      dazu(m[0], m[0], null, 1, m.index);
      // „12 28013": vielleicht Hausnummer und Postleitzahl. Nicht aber
      // „01310-100" — das ist als Ganzes eine brasilianische Postleitzahl.
      if (m[2] && !(formenTabelle[formVon(m[0])] || []).length) {
        if (m[1].length >= 3) dazu(m[1], m[1], null, 2, m.index);
        if (m[2].length >= 3) dazu(m[2], m[2], null, 2, m.index + m[0].lastIndexOf(m[2]));
      }
    }
    for (const m of gross.matchAll(BEZIRK)) dazu(m[0], m[1], ['GB', 'IM', 'JE', 'GG', 'IE', 'CA'], 3, m.index);
    return { kandidaten: gefunden, laender, kuerzel };
  }

  /** Wo eine Postleitzahl liegt — in jedem Land, in dem es sie gibt. */
  function plzNachschlagen(k, geo, welt) {
    const formen = geo.plzFormen || {};
    let laender = k.laender || formen[k.form] || [];
    if (k.formPruefen) laender = laender.filter((cc) => (formen[k.form] || []).includes(cc));
    const treffer = [];
    for (const cc of laender) {
      if (cc === 'DE' || cc === 'AT' || cc === 'CH') {
        const p = (geo.plz || []).find((e) => e[0] === k.schluessel && e[4] === cc);
        if (p) treffer.push({ cc, lat: p[2], lon: p[3], ort: p[1], k });
        continue;
      }
      const tabelle = welt && welt[cc];
      if (!tabelle) continue;
      // Der längste bekannte Anfang: Verdichtet ist auf fünf Kilometer
      let p = null;
      for (let n = k.schluessel.length; !p && n >= Math.max(1, k.schluessel.length - 2); n--) {
        p = tabelle[k.schluessel.slice(0, n)];
      }
      // Brasilien führt nur je Stadt einen Code („01000-000" für São Paulo).
      // Passt die Form nur zu einem Land, genügt der ähnlichste Code dort.
      if (!p && laender.length === 1) p = aehnlichsterCode(tabelle, k.schluessel);
      if (p) treffer.push({ cc, lat: p[0], lon: p[1], ort: '', k });
    }
    return treffer;
  }

  /** Der Code mit dem längsten gemeinsamen Anfang, mindestens zwei Zeichen. */
  const sortiert = new WeakMap();
  function aehnlichsterCode(tabelle, code) {
    let schluessel = sortiert.get(tabelle);
    if (!schluessel) { schluessel = Object.keys(tabelle).sort(); sortiert.set(tabelle, schluessel); }
    let lo = 0, hi = schluessel.length;
    while (lo < hi) { const mitte = (lo + hi) >> 1; if (schluessel[mitte] < code) lo = mitte + 1; else hi = mitte; }
    const gemeinsam = (s) => { let n = 0; while (n < s.length && s[n] === code[n]) n++; return n; };
    const nachbarn = [schluessel[lo - 1], schluessel[lo]].filter(Boolean);
    const bester = nachbarn.sort((a, b) => gemeinsam(b) - gemeinsam(a))[0];
    return bester && gemeinsam(bester) >= 2 ? tabelle[bester] : null;
  }

  /* ---------------- Ortsnamen ---------------- */

  /* Gefaltete Namen je Verzeichnis, einmal berechnet: name → Einträge. */
  const verzeichnisse = new WeakMap();
  function register(liste) {
    let reg = verzeichnisse.get(liste);
    if (!reg) {
      reg = new Map();
      for (const e of liste) {
        const f = fold(e[0]);
        if (!f) continue;
        if (!reg.has(f)) reg.set(f, []);
        reg.get(f).push(e);
      }
      verzeichnisse.set(liste, reg);
    }
    return reg;
  }

  // Schriften ohne Leerzeichen zwischen den Wörtern: „東京都千代田区"
  const OHNE_LEERZEICHEN = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}\p{Script=Thai}]/u;

  /** Alle Orte eines Namens, ohne Doppelte. Vorn steht, was auch mit
      Akzenten gleich geschrieben ist — wer „Åbo" schreibt, meint Turku, nicht
      das „Abo" in Osttimor —, dann der größere: „München" ist die Stadt mit
      1,5 Millionen Einwohnern, nicht das Dorf in Brandenburg. */
  function orteNamens(text, listen) {
    const f = fold(text);
    if (!f) return [];
    const genau = text.normalize('NFC').toLocaleLowerCase();
    const ordnen = (roh) => {
      const orte = roh.map((e) => ({ name: e[0], lat: e[1], lon: e[2], cc: e[3], ew: e[4] || 0 }));
      orte.sort((a, b) => ((b.name.toLocaleLowerCase() === genau) - (a.name.toLocaleLowerCase() === genau))
                          || b.ew - a.ew);
      const ergebnis = [];
      for (const o of orte) if (!ergebnis.some((x) => x.cc === o.cc && km(x, o) < 5)) ergebnis.push(o);
      return ergebnis;
    };
    const treffer = listen.flatMap((liste) => register(liste).get(f) || []);
    if (treffer.length || !OHNE_LEERZEICHEN.test(f)) return ordnen(treffer);
    // Japanisch, Chinesisch, Koreanisch, Thai: Die Adresse beginnt mit dem
    // größten Gebiet — der längste bekannte Anfang ist der Ort.
    for (const wort of f.split(' ')) {
      for (let n = wort.length; n >= 2; n--) {
        const anfang = listen.flatMap((liste) => register(liste).get(wort.slice(0, n)) || []);
        if (anfang.length) return ordnen(anfang);
      }
    }
    return [];
  }

  /** Bei einem Namen, der mehrfach vorkommt: das genannte Land, sonst der
      Ort, der dem genannten Bundesstaat am nächsten liegt, sonst der größte. */
  function auswaehlen(orte, hinweise) {
    if (!orte.length) return null;
    let auswahl = orte;
    const imLand = orte.filter((o) => hinweise.laender.includes(o.cc));
    if (imLand.length) auswahl = imLand;
    let bester = null;
    for (const s of hinweise.staaten) {
      for (const o of auswahl) {
        if (o.cc !== s.cc) continue;
        const d = km(o, s);
        if (!bester || d < bester.d) bester = { o, d, s };
      }
    }
    // Nur der nächstgelegene — ob er wirklich im Staat liegt, weiß hier keiner;
    // das Kürzel bekommt nur ein Treffer aus `ortImStaat`.
    if (bester) return { ...bester.o, weitere: 0 };
    return { ...auswahl[0], weitere: imLand.length ? 0 : auswahl.length - 1 };
  }

  /* ---------------- Zerlegen ---------------- */

  /* Woran man eine Straße erkennt, nachdem die Hausnummer schon als
     mögliche Postleitzahl herausgenommen ist: „1600 Pennsylvania Ave NW".
     Angehängt zählen nur die deutschen und nordischen Endungen
     („Hauptstraße", „Storgatan"); „St." fehlt, das ist meist Sankt. */
  const STRASSE = new RegExp('\\b(?:street|avenue|ave|road|rd|boulevard|blvd|drive|lane|'
    + 'highway|hwy|parkway|pkwy|calle|avenida|avda|rua|rue|chemin|via|viale|piazza|corso|'
    + 'ulica|ul|laan|straat|plein|utca|ulitsa)\\b'
    + '|(?:strasse|str|weg|gasse|platz|allee|gatan|vagen|vej|gade|katu|tie)\\b', 'u');

  /** Land oder Bundesstaat? Ein ganzes Stück oder seine letzten Wörter.
      Kürzel zählen am Ende nur in Großbuchstaben: „Austin TX", aber nicht
      das „de" in „Rio de Janeiro". */
  function hinweisVon(roh, ganz, geo) {
    const f = fold(roh);
    const gefunden = { laender: [], staaten: [] };
    const kurz = /^[A-Za-z]{2,3}$/.test(roh) && (ganz || roh === roh.toUpperCase());
    const land = laenderNamen().get(f) || (kurz && ISO.has(roh.toUpperCase()) ? roh.toUpperCase() : '');
    if (land) gefunden.laender.push(land);
    const staaten = staatenTabelle(geo);
    gefunden.staaten.push(...(staaten.get(`n:${f}`) || []));
    if (kurz) gefunden.staaten.push(...(staaten.get(`k:${roh.toUpperCase()}`) || []));
    return gefunden.laender.length || gefunden.staaten.length ? gefunden : null;
  }

  /** Eine Eingabe in ihre Teile: Postleitzahlen, Ortsangaben, Hinweise. */
  function zerlegen(eingabe, geo) {
    const hinweise = { laender: [], staaten: [] };
    const merke = (h) => {
      for (const cc of h.laender) if (!hinweise.laender.includes(cc)) hinweise.laender.push(cc);
      hinweise.staaten.push(...h.staaten);
    };
    const stuecke = eingabe.split(/[,;\n]+/).map((s) => s.trim()).filter(Boolean);
    const plz = [];
    const orte = [];
    stuecke.forEach((stueck, nr) => {
      let { kandidaten, laender, kuerzel } = plzKandidaten(stueck, nr);
      for (const k of kuerzel) { const h = hinweisVon(k, true, geo); if (h) merke(h); }
      // In einer Straße ist eine kurze Zahl die Hausnummer — „Avenida Paulista
      // 1578" liegt nicht in Sydney —, ebenso die Zahl vorn („1600 Pennsylvania
      // Ave"). Postleitzahlen stehen meist hinter einem Komma.
      if (STRASSE.test(fold(stueck))) {
        kandidaten = kandidaten.filter((k) => k.rang === 0 || k.rang === 3
          || (k.schluessel.length > 4 && !(k.index === 0 && /\d\s+\p{L}/u.test(stueck))));
      }
      plz.push(...kandidaten);
      merke({ laender, staaten: [] });
      // Postleitzahlen aus dem Text nehmen, der Rest ist Ort oder Straße
      let text = stueck;
      for (const k of kandidaten) {
        if (k.rang <= 1) text = text.replace(new RegExp(k.roh.replace(/[-\s]/g, '[-\\s]?'), 'i'), ' ');
      }
      text = text.replace(/〒/g, ' ').replace(/\s+/g, ' ').trim();
      if (!text) return;
      // „Paris, France", „75001 FR": ein Stück, das nur Land oder Staat nennt
      if (stuecke.length > 1 || kandidaten.length) {
        const h = hinweisVon(text, true, geo);
        if (h) { merke(h); orte.push({ text, nr, hinweis: true, plz: kandidaten.length > 0 }); return; }
      }
      // Hinweise am Ende: „Sydney NSW", „Paris France", „Portland Maine"
      let woerter = text.split(' ');
      for (let ende = true; ende && woerter.length > 1;) {
        ende = false;
        for (let n = Math.min(4, woerter.length - 1); n >= 1; n--) {
          const h = hinweisVon(woerter.slice(-n).join(' '), false, geo);
          if (h) { merke(h); woerter = woerter.slice(0, -n); ende = true; break; }
        }
      }
      text = woerter.join(' ');
      orte.push({ text, nr, strasse: /\d/.test(text) || STRASSE.test(fold(text)),
                  plz: kandidaten.length > 0 });
    });
    // Der Ort steht meist neben der Postleitzahl, die Straße davor
    const reihe = (o) => (o.hinweis ? 3 : o.strasse ? 2 : o.plz ? 0 : 1);
    orte.sort((a, b) => reihe(a) - reihe(b) || a.nr - b.nr);
    return { plz, orte, hinweise };
  }

  /* ---------------- Suchen ---------------- */

  /** Den Ort zur Eingabe finden: jedes Stück, dann ohne die letzten Wörter. */
  function ortFinden(teile, hinweise, listen) {
    for (const teil of teile) {
      const woerter = teil.text.split(' ');
      for (let n = woerter.length; n >= 1; n--) {
        const text = woerter.slice(0, n).join(' ');
        const kandidaten = orteNamens(text, listen);
        if (kandidaten.length) return { kandidaten, ort: auswaehlen(kandidaten, hinweise), text };
        if (teil.strasse) break;      // in einer Straße steckt kein Ortsname
      }
    }
    return null;
  }

  /** „Springfield, IL": unter den Orten mit Bundesstaat der genannte. */
  function ortImStaat(teile, hinweise, listen) {
    if (!hinweise.staaten.length) return null;
    for (const teil of teile) {
      const woerter = teil.text.split(' ');
      for (let n = woerter.length; n >= 1; n--) {
        const f = fold(woerter.slice(0, n).join(' '));
        for (const liste of listen) {
          const e = (register(liste).get(f) || [])
            .find((x) => hinweise.staaten.some((s) => s.cc === x[3] && s.kuerzel === x[4]));
          if (e) {
            const ort = { name: e[0], lat: e[1], lon: e[2], cc: e[3], staat: e[4], weitere: 0 };
            return { kandidaten: [ort], ort };
          }
        }
        if (teil.strasse) break;
      }
    }
    return null;
  }

  /** Ein Ort, der zu den Hinweisen passt — oder es gibt keine Hinweise. */
  function passtZuHinweisen(ort, hinweise) {
    if (!hinweise.laender.length && !hinweise.staaten.length) return true;
    return hinweise.laender.includes(ort.cc) || hinweise.staaten.some((s) => s.cc === ort.cc);
  }

  /** Wie heißt die Gegend einer Postleitzahl? Der größte Ort in acht
      Kilometern — „Tokyo" statt des Viertels —, sonst der nächste in 25. */
  function ortBei(p, liste) {
    let naechster = null;
    for (const e of liste || []) {
      if (e[3] !== p.cc || Math.abs(e[1] - p.lat) > 0.3) continue;
      const d = km(p, { lat: e[1], lon: e[2] });
      if (d < 8) return e[0];            // die Liste ist nach Einwohnern sortiert
      if (d < 25 && (!naechster || d < naechster.d)) naechster = { name: e[0], d };
    }
    return naechster ? naechster.name : '';
  }

  async function suchen(eingabe) {
    const q = eingabe.trim();
    if (!q) return null;
    const geo = (await FF.geo()) || {};
    formenTabelle = geo.plzFormen || {};
    const z = zerlegen(q, geo);
    const heimat = heimatLaender();

    // Was als Land oder Staat erkannt ist, kann trotzdem der Ort sein —
    // „Washington, DC", „New York, NY" —, wird aber zuletzt gesucht. Kürzel
    // nur, wenn sonst nichts dasteht: Das „AU" in „2000 AU" ist kein Ort,
    // obwohl es in Österreich Orte namens Au gibt.
    let teile = z.orte.filter((o) => !o.hinweis || o.text.length > 3);
    if (!teile.length && !z.plz.some((k) => k.rang <= 1)) teile = z.orte;

    // Ort: zuerst im kleinen Verzeichnis, das große nur bei Bedarf
    let gefunden = ortImStaat(teile, z.hinweise, [geo.staatOrte || []])
      || ortFinden(teile, z.hinweise, [geo.places || [], geo.zweitnamen || []]);
    // „Paris, TN" ist zu klein für geo.js — erst orte.js kennt es. „Toronto,
    // CA" dagegen ist schon gefunden: CA ist hier Kanada, nicht Kalifornien.
    const staatOffen = z.hinweise.staaten.length && !(gefunden && (gefunden.ort.staat
      || z.hinweise.laender.includes(gefunden.ort.cc)));
    // „Göteborg" passt in der kleinen Liste nur als „Goteborg" — die richtige
    // Schreibweise steht unter den Zweitnamen im großen Verzeichnis.
    const nurOhneAkzente = gefunden && gefunden.text && /[^\x00-\x7F]/.test(gefunden.text)
      && !gefunden.kandidaten.some((o) => o.name.toLocaleLowerCase()
                                          === gefunden.text.toLocaleLowerCase());
    if (teile.length && (!gefunden || staatOffen || nurOhneAkzente
                         || !passtZuHinweisen(gefunden.ort, z.hinweise))) {
      const welt = await grossesVerzeichnis();
      if (welt) {
        const gross = ortImStaat(teile, z.hinweise, [geo.staatOrte || [], welt.staatOrte || []])
          || ortFinden(teile, z.hinweise,
                       [geo.places || [], geo.zweitnamen || [], welt.orte || [], welt.zweitnamen || []]);
        if (gross && (!gefunden || gross.ort.staat || passtZuHinweisen(gross.ort, z.hinweise))) {
          gefunden = gross;
        }
      }
    }

    // Postleitzahl: in welchen Ländern es sie gibt, und welches gemeint ist
    const vorzug = [...z.hinweise.laender, ...z.hinweise.staaten.map((s) => s.cc), ...heimat,
                    'DE', 'AT', 'CH'];
    const rangVon = (cc) => { const i = vorzug.indexOf(cc); return i < 0 ? 999 : i; };
    const amOrt = (t) => !!gefunden && gefunden.kandidaten.some((o) => o.cc === t.cc && km(o, t) < 40);
    const imOrtsland = (t) => !!gefunden && gefunden.kandidaten.some((o) => o.cc === t.cc);
    const ordnen = (liste) => liste.sort((a, b) =>
      (amOrt(b) - amOrt(a)) || (imOrtsland(b) - imOrtsland(a)) || (a.k.rang - b.k.rang)
      || (rangVon(a.cc) - rangVon(b.cc)) || (b.k.teil - a.k.teil) || (b.k.index - a.k.index)
      || a.cc.localeCompare(b.cc));

    let treffer = ordnen(z.plz.flatMap((k) => plzNachschlagen(k, geo, null)));
    // Die Welttabelle nur, wenn DE/AT/CH nicht schon die gemeinte Antwort ist:
    // Wer in Würzburg „97209" eingibt, lädt keine zwei Megabyte Postleitzahlen.
    const DACH = ['DE', 'AT', 'CH'];
    const eindeutig = (t) => amOrt(t) || z.hinweise.laender.includes(t.cc)
      || (t.k.laender && t.k.laender.length === 1);
    const erstesFremdes = vorzug.findIndex((cc) => !DACH.includes(cc));
    const brauchtWelt = z.plz.some((k) => (k.laender || (geo.plzFormen || {})[k.form] || [])
      .some((cc) => !DACH.includes(cc)));
    if (brauchtWelt && !(treffer.length && (eindeutig(treffer[0])
        || erstesFremdes < 0 || rangVon(treffer[0].cc) < erstesFremdes))) {
      const welt = await plzDerWelt();
      if (welt) treffer = ordnen(z.plz.flatMap((k) => plzNachschlagen(k, geo, welt)));
    }

    // „34000 İstanbul": Kennt die Tabelle den Code nur aus anderen Ländern,
    // gilt der genannte Ort — die Postleitzahl war dann nicht zu finden.
    if (treffer.length && gefunden && !eindeutig(treffer[0]) && !imOrtsland(treffer[0])) {
      treffer = [];
    }

    if (treffer.length) {
      const t = treffer[0];
      // Wer nichts zum Land gesagt hat, soll hören, wo es den Code noch gibt
      const andere = [...new Set(treffer.filter((x) => x.k === t.k && x.cc !== t.cc)
        .map((x) => x.cc))].slice(0, 8);
      const ort = t.ort || (amOrt(t) && gefunden.ort.cc === t.cc ? gefunden.ort.name : '')
        || ortBei(t, geo.places);
      return {
        lat: t.lat, lon: t.lon, land: t.cc,
        label: `${t.k.roh}${ort ? ' ' + ort : ''} (${t.cc})`,
        ambiguous: !eindeutig(t) && andere.length ? andere : null,
      };
    }

    if (gefunden) {
      const o = gefunden.ort;
      const ergebnis = { lat: o.lat, lon: o.lon, land: o.cc,
                         label: `${o.name}${o.staat ? ', ' + o.staat : ''} (${o.cc})` };
      if (o.weitere) ergebnis.ambiguousName = o.weitere;
      return ergebnis;
    }

    // Ein angefangener Name: „Veitshöch". Nur bei einer schlichten Eingabe —
    // in einer Adresse wäre ein Wortanfang geraten.
    if (z.orte.length === 1 && !z.plz.length) {
      const anfang = await namensAnfang(fold(z.orte[0].text), geo);
      if (anfang) return anfang;
    }

    // Nur wenn auch das nicht passt: Nominatim. In der Einzelseite blockiert
    // die Sicherheitsrichtlinie den Abruf.
    const online = await nominatim(q);
    if (online) return online;
    const plz = z.plz.find((k) => k.rang <= 1);
    return plz ? { notFound: plz.roh } : null;
  }

  async function namensAnfang(f, geo) {
    if (f.length < 3) return null;
    const welt = await grossesVerzeichnis();
    for (const liste of [geo.places || [], (welt && welt.orte) || []]) {
      const reg = register(liste);
      let erster = null, weitere = 0;
      for (const [name, eintraege] of reg) {
        if (!name.startsWith(f)) continue;
        if (!erster) erster = eintraege[0]; else weitere += eintraege.length;
      }
      if (erster) {
        const [name, lat, lon, cc] = erster;
        const t = { lat, lon, land: cc, label: `${name} (${cc})` };
        if (weitere) t.ambiguousName = weitere;
        return t;
      }
    }
    return null;
  }

  async function nominatim(q) {
    const felder = new URLSearchParams({ format: 'jsonv2', limit: '1', addressdetails: '1',
                                         'accept-language': FF.sprache(), q });
    try {
      const res = await fetch('https://nominatim.openstreetmap.org/search?' + felder,
                              { headers: { Accept: 'application/json' } });
      const hits = res.ok ? await res.json() : [];
      if (!hits.length) return null;
      const land = ((hits[0].address || {}).country_code || '').toUpperCase();
      return {
        lat: parseFloat(hits[0].lat), lon: parseFloat(hits[0].lon), land,
        label: hits[0].display_name.split(',').slice(0, 2).join(',').trim()
          + (land ? ` (${land})` : ''),
        online: true,
      };
    } catch (_) {
      return null;                    // offline oder blockiert
    }
  }

  FF.wohnortSuchen = suchen;
})();
