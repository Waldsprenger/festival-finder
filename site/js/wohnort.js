/* Von einer Eingabe zu einem Punkt auf der Erde.

   Vier Stufen: mitgelieferte Postleitzahlen, das mitgelieferte
   Ortsverzeichnis, das große nachgeladene Verzeichnis und erst ganz zuletzt
   Nominatim. Jede Stufe davor ist eine Eingabe, die das Gerät nicht verlässt.

   Postleitzahlen und Ortsverzeichnis stehen in geo.js; die Seite holt sie
   nach dem ersten Bild, meist also, bevor jemand „Suchen" drückt. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { D, fold } = FF;

  /* Das große Verzeichnis (Orte ab 1.000 Einwohnern, Postleitzahlen von 33
     weiteren Ländern) wird erst geholt, wenn die kleine Liste nichts hergibt.
     In der Einzelseite gibt es die Datei nicht; dort bleibt es beim kleinen. */
  let weltVerzeichnis = null;

  function grossesVerzeichnis() {
    if (!weltVerzeichnis) {
      const stand = (D.versionen || {}).orte;
      weltVerzeichnis = new Promise((fertig) => {
        if (window.ORTE_WELT) return fertig(window.ORTE_WELT);
        const laden = (src, sonst) => {
          const s = document.createElement('script');
          s.src = src;
          s.onload = () => fertig(window.ORTE_WELT || null);
          s.onerror = sonst;
          document.head.append(s);
        };
        const ohne = () => laden('orte.js', () => fertig(null));
        if (stand) laden(`orte.js?v=${stand}`, ohne); else ohne();
      });
    }
    return weltVerzeichnis;
  }

  /* Gefaltete Ortsnamen je Verzeichnis, einmal berechnet: Die Suche läuft
     über 116.000 Namen, im großen Verzeichnis über 260.000. */
  const gefaltet = new WeakMap();
  function namen(verzeichnis) {
    let liste = gefaltet.get(verzeichnis);
    if (!liste) {
      liste = verzeichnis.map((e) => fold(e[0]));
      gefaltet.set(verzeichnis, liste);
    }
    return liste;
  }

  /** Einen Ortsnamen suchen: genau, sonst am Wortanfang. Mehrdeutige Namen
      werden gemeldet statt stillschweigend geraten. */
  function ortSuchen(verzeichnis, gesucht) {
    const f = namen(verzeichnis);
    let genau = -1, anfang = -1, weitere = 0;
    for (let i = 0; i < f.length; i++) {
      if (f[i] === gesucht) {
        if (genau >= 0) weitere++; else genau = i;
      } else if (f[i].startsWith(gesucht)) {
        if (anfang >= 0) weitere++; else anfang = i;
      }
    }
    const nr = genau >= 0 ? genau : anfang;
    if (nr < 0) return null;
    const [name, lat, lon, cc] = verzeichnis[nr];
    const treffer = { lat, lon, land: cc, label: `${name} (${cc})` };
    if (genau >= 0 && anfang >= 0) weitere++;
    if (weitere) treffer.ambiguousName = weitere;
    return treffer;
  }

  const ausPlzListe = (liste, code, land) => {
    const treffer = liste.filter((p) => p[0] === code && (!land || fold(p[4]) === land));
    return treffer.length ? treffer : null;
  };

  function alsTreffer(liste, rest, genanntesLand) {
    let pick = liste[0];
    if (rest && !genanntesLand) pick = liste.find((p) => fold(p[1]).startsWith(rest)) || pick;
    const andere = liste.filter((p) => p[4] !== pick[4]).map((p) => p[4]);
    return {
      lat: pick[2], lon: pick[3], land: pick[4],
      label: `${pick[0]} ${pick[1]} (${pick[4]})`,
      ambiguous: andere.length ? andere : null,
    };
  }

  const laender = new Set((D.laender || []).map((c) => c.toLowerCase()));

  async function suchen(eingabe) {
    const q = eingabe.trim();
    if (!q) return null;
    const geo = (await FF.geo()) || {};

    // 1. Postleitzahl — die eindeutigste Eingabe: „97209", „97209
    //    Veitshöchheim", „1010 AT" zur Trennung von AT und CH.
    const pm = q.match(/^\s*(\d{4,5})\b\s*([A-Za-zÄÖÜäöü].*)?$/);
    if (pm) {
      const code = pm[1];
      const rest = fold(pm[2] || '');
      // „1012 NL" nennt ein Land, „1012 AB" ist eine niederländische
      // Postleitzahl, „97209 Veitshöchheim" nennt den Ort.
      const genanntesLand = laender.has(rest) ? rest : '';
      if (genanntesLand || !/^[a-z]{1,3}$/.test(rest)) {
        const nah = ausPlzListe(geo.plz || [], code, genanntesLand);
        if (nah) return alsTreffer(nah, rest, genanntesLand);
        const welt = await grossesVerzeichnis();
        const fern = ausPlzListe((welt && welt.plz) || [], code, genanntesLand);
        if (fern) return alsTreffer(fern, rest, genanntesLand);
      }
    }

    // 2. Ortsverzeichnis, nach Einwohnern sortiert — der erste Treffer ist der
    //    bekannteste Ort gleichen Namens. 3. Dasselbe im großen Verzeichnis.
    const gesucht = fold(q);
    const nah = geo.places && ortSuchen(geo.places, gesucht);
    if (nah) return nah;
    const welt = await grossesVerzeichnis();
    const fern = welt && welt.orte && ortSuchen(welt.orte, gesucht);
    if (fern) return fern;

    // 4. Nur wenn auch dort nichts passt: Nominatim. In der eingebetteten
    //    Fassung blockiert die Sicherheitsrichtlinie das.
    const treffer = await nominatim(q, pm);
    if (treffer) return treffer;
    // Wer eine Postleitzahl eingab, soll das auch hören.
    return pm ? { notFound: pm[1] } : null;
  }

  async function nominatim(q, pm) {
    // Eine Postleitzahl wird strukturiert gefragt: Als Freitext lieferte
    // „1012 NL" die Hausnummer „42-1012" irgendwo.
    const felder = new URLSearchParams({ format: 'jsonv2', limit: '1',
                                         'accept-language': FF.sprache() });
    if (pm) {
      const rest = (pm[2] || '').trim();
      if (laender.has(fold(rest))) {
        felder.set('postalcode', pm[1]);
        felder.set('countrycodes', fold(rest));
      } else if (/^[A-Za-z]{1,3}$/.test(rest)) {
        felder.set('postalcode', `${pm[1]} ${rest.toUpperCase()}`);   // „1012 AB"
      } else {
        felder.set('postalcode', pm[1]);
        if (rest) felder.set('city', rest);
      }
    } else {
      felder.set('q', q);
    }
    try {
      const res = await fetch('https://nominatim.openstreetmap.org/search?' + felder,
                              { headers: { Accept: 'application/json' } });
      const hits = res.ok ? await res.json() : [];
      if (!hits.length) return null;
      return {
        lat: parseFloat(hits[0].lat), lon: parseFloat(hits[0].lon), land: '',
        label: hits[0].display_name.split(',').slice(0, 2).join(',').trim(),
        online: true,
      };
    } catch (_) {
      return null;                    // offline oder blockiert
    }
  }

  FF.wohnortSuchen = suchen;
})();
