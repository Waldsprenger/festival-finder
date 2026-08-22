/* Von einer Eingabe zu einem Punkt auf der Erde.

   Vier Stufen, in dieser Reihenfolge: mitgelieferte Postleitzahlen, das
   mitgelieferte Ortsverzeichnis, das große nachgeladene Verzeichnis und erst
   ganz zuletzt Nominatim. Jede Stufe davor ist eine Anfrage weniger an einen
   fremden Server — und eine Eingabe, die das Gerät nicht verlässt. */

(() => {
  'use strict';
  if (FF.keineDaten) return;

  const { D, fold } = FF;

  /* Das mitgelieferte Verzeichnis deckt DE/AT/CH vollständig ab und die
     übrige Welt ab 15.000 Einwohnern. Alles darunter steht in site/orte.js und
     wird erst geholt, wenn jemand danach sucht — als <script>, damit es auch
     beim Öffnen per Doppelklick (file://) funktioniert, wo fetch() scheitert.
     In der gebündelten Einzelseite gibt es die Datei nicht; dort bleibt es
     beim kleinen Verzeichnis. */
  let weltVerzeichnis = null;

  function grossesVerzeichnis() {
    if (weltVerzeichnis) return weltVerzeichnis;
    weltVerzeichnis = new Promise((fertig) => {
      if (window.ORTE_WELT) return fertig(window.ORTE_WELT);
      const skript = document.createElement('script');
      skript.src = 'orte.js';
      skript.onload = () => fertig(window.ORTE_WELT || null);
      skript.onerror = () => fertig(null);
      document.head.append(skript);
    });
    return weltVerzeichnis;
  }

  /** Einen Ortsnamen in einem Verzeichnis suchen: genau, sonst am Wortanfang. */
  function ortSuchen(verzeichnis, gesucht) {
    let genau = null, anfang = null, weitere = 0;
    for (const [name, lat, lon, cc] of verzeichnis) {
      const f = fold(name);
      if (f === gesucht) {
        if (genau) { weitere++; continue; }
        genau = { lat, lon, land: cc, label: `${name} (${cc})` };
      } else if (f.startsWith(gesucht)) {
        if (anfang) { weitere++; continue; }
        anfang = { lat, lon, land: cc, label: `${name} (${cc})` };
      }
    }
    const treffer = genau || anfang;
    if (!treffer) return null;
    // Ortsnamen sind mehrdeutig - darauf hinweisen statt stillschweigend raten
    if (genau && anfang) weitere++;
    if (weitere) treffer.ambiguousName = weitere;
    return treffer;
  }

  function ausPlzListe(liste, code, land) {
    const treffer = liste.filter((p) => p[0] === code && (!land || fold(p[4]) === land));
    if (!treffer.length) return null;
    return treffer;
  }

  function alsTreffer(liste, rest, genanntesLand) {
    let pick = liste[0];
    if (rest && !genanntesLand) {
      pick = liste.find((p) => fold(p[1]).startsWith(rest)) || pick;
    }
    const andere = liste.filter((p) => p[4] !== pick[4]).map((p) => p[4]);
    return {
      lat: pick[2], lon: pick[3], land: pick[4],
      label: `${pick[0]} ${pick[1]} (${pick[4]})`,
      ambiguous: andere.length ? andere : null,
    };
  }

  async function suchen(eingabe) {
    const q = eingabe.trim();
    if (!q) return null;

    // 1. Postleitzahl — die eindeutigste Eingabe. Erlaubt sind „97209",
    //    „97209 Veitshöchheim" und „1010 AT" zur Trennung von AT und CH.
    const pm = q.match(/^\s*(\d{4,5})\b\s*([A-Za-zÄÖÜäöü].*)?$/);
    if (pm) {
      const code = pm[1];
      const rest = fold(pm[2] || '');
      // „1012 NL" nennt ein Land, „1012 AB" ist eine niederländische
      // Postleitzahl, „97209 Veitshöchheim" nennt den Ort.
      const laender = new Set((D.laender || []).map((c) => c.toLowerCase()));
      const genanntesLand = laender.has(rest) ? rest : '';
      const buchstabenteil = !genanntesLand && /^[a-z]{1,3}$/.test(rest);

      if (!buchstabenteil) {
        const nah = ausPlzListe(D.plz || [], code, genanntesLand);
        if (nah) return alsTreffer(nah, rest, genanntesLand);
        // Mitgeliefert sind DE/AT/CH. Für die übrigen 33 Länder liegt die
        // Tabelle in orte.js und wird jetzt nachgeladen.
        const welt = await grossesVerzeichnis();
        const fern = ausPlzListe((welt && welt.plz) || [], code, genanntesLand);
        if (fern) return alsTreffer(fern, rest, genanntesLand);
      }
    }

    // 2. Ortsverzeichnis (GeoNames), nach Einwohnerzahl sortiert — der erste
    //    Treffer ist also der bekannteste Ort gleichen Namens.
    const gesucht = fold(q);
    const nah = ortSuchen(D.places, gesucht);
    if (nah) return nah;

    // 3. Kleinerer Ort irgendwo auf der Welt: dieselbe Suche im großen Verzeichnis.
    const welt = await grossesVerzeichnis();
    if (welt && welt.orte) {
      const fern = ortSuchen(welt.orte, gesucht);
      if (fern) return fern;
    }

    // 4. Nur wenn auch dort nichts passt: Nominatim (OpenStreetMap). In der
    //    eingebetteten Fassung blockiert die Sicherheitsrichtlinie externe
    //    Aufrufe — dann bleibt es bei den Schritten davor.
    const treffer = await nominatim(q, pm);
    if (treffer) return treffer;

    // Wer eine Postleitzahl eingegeben hat, soll das auch hören — „Ort nicht
    // gefunden" führt sonst auf die falsche Fährte.
    return pm ? { notFound: pm[1] } : null;
  }

  async function nominatim(q, pm) {
    // Eine Postleitzahl wird strukturiert gefragt: Als Freitext lieferte
    // „1012 NL" die Hausnummer „42-1012" irgendwo.
    const felder = new URLSearchParams({ format: 'jsonv2', limit: '1',
                                         'accept-language': FF.sprache() });
    if (pm) {
      const rest = (pm[2] || '').trim();
      const laender = new Set((FF.D.laender || []).map((c) => c.toLowerCase()));
      if (laender.has(fold(rest))) {
        felder.set('postalcode', pm[1]);
        felder.set('countrycodes', fold(rest));
      } else if (/^[A-Za-z]{1,3}$/.test(rest)) {
        // Der Buchstabenteil gehört zur Postleitzahl („1012 AB", „SW1A 1AA")
        felder.set('postalcode', `${pm[1]} ${rest.toUpperCase()}`);
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
      if (!res.ok) return null;
      const hits = await res.json();
      if (!hits.length) return null;
      return {
        lat: parseFloat(hits[0].lat),
        lon: parseFloat(hits[0].lon),
        land: '',
        label: hits[0].display_name.split(',').slice(0, 2).join(',').trim(),
        online: true,
      };
    } catch (_) {
      return null;                    // offline oder blockiert
    }
  }

  FF.wohnortSuchen = suchen;
})();
