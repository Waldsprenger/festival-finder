/* Die Karte: Umrisse, Suchbereich, Pins — auf Canvas selbst gezeichnet.

   Kartenkacheln fremder Server sind in der veröffentlichten Fassung durch die
   Sicherheitsrichtlinie blockiert, und eine eigene Zeichnung verrät niemandem,
   wo jemand sucht. Die Umrisse liegen als Vektorringe in data.js.

   Nach außen gibt es vier Handgriffe:
     KARTE.start(einstellungen)  einmalig verdrahten
     KARTE.zeichnen()            neu zeichnen
     KARTE.setzePins(liste)      Treffer anzeigen ([{lat, lon, name, pct, dist, eintragId}])
     KARTE.zentrieren()          Ausschnitt wieder am Wohnort ausrichten           */

window.KARTE = (() => {
  'use strict';

  const ZOOM_MAX = 60;

  //: Halbe Höhe der Erde in Kilometern (Pol zu Pol sind 20.036 km).
  //: Weiter herauszuzoomen ergibt kein Bild mehr, sondern nur noch Rand.
  const WELT_HALB_KM = 10018;
  const KM_JE_GRAD = 111.32;

  // Am Finger gibt es kein Mausrad; der Hinweis unter der Karte richtet sich
  // danach, womit die Seite gerade bedient wird.
  const tippgeraet = window.matchMedia('(pointer: coarse)').matches;

  const karte = {
    canvas: null, ctx: null, view: null, pins: [], hover: -1,
    zoom: 1, center: null, drag: null, moved: false,
  };

  //: wird von start() gefüllt: Texte, Wohnort, Bereich, Umrisse, Klickziel
  let cfg = null;

  /* ---------------- Projektion ---------------- */

  // Umschließendes Rechteck je Polygonring, einmal berechnet und gemerkt
  const rahmen = new WeakMap();
  function ringRahmen(ring) {
    let r = rahmen.get(ring);
    if (r) return r;
    let lon0 = Infinity, lon1 = -Infinity, lat0 = Infinity, lat1 = -Infinity;
    for (const [lon, lat] of ring) {
      if (lon < lon0) lon0 = lon;
      if (lon > lon1) lon1 = lon;
      if (lat < lat0) lat0 = lat;
      if (lat > lat1) lat1 = lat;
    }
    r = { lon0, lon1, lat0, lat1, mitte: (lon0 + lon1) / 2 };
    rahmen.set(ring, r);
    return r;
  }

  /** Längenunterschied über die Datumsgrenze hinweg: immer der kurze Weg.

      Bei 180 Grad springt die Länge auf -180. Wer in Suva sitzt (178 Ost),
      hätte Honolulu (158 West) sonst 336 Grad entfernt statt 24 — der Pin
      läge weit außerhalb des Bildes, obwohl er in der Liste 5.090 km
      entfernt steht. */
  function lonAbstand(lon, mitteLon) {
    let d = lon - mitteLon;
    while (d > 180) d -= 360;
    while (d < -180) d += 360;
    return d;
  }

  const aufsRund = (lon) => {
    let l = lon;
    while (l > 180) l -= 360;
    while (l < -180) l += 360;
    return l;
  };

  /* Mittabstandstreue Zylinderprojektion, an der Bildmitte ausgerichtet.

     Wichtig: `x` rechnet die Länge ohne Umbruch um. Früher faltete sie jeden
     Punkt auf den kurzen Weg zur Bildmitte — bei einem Polygonring, der die
     Datumsgrenze überquert, sprangen dadurch zwei benachbarte Punkte von der
     einen Bildkante zur anderen, und quer über die Karte lief ein Strich.
     Verschoben wird jetzt der ganze Ring auf einmal, nicht der einzelne
     Punkt. */
  function sicht(mitteLat, mitteLon, spanneKm, w, h) {
    const kmProGradLon = KM_JE_GRAD * Math.cos(mitteLat * Math.PI / 180);
    const halbKmY = spanneKm, halbKmX = spanneKm * (w / h);
    const sx = (w / 2) / halbKmX, sy = (h / 2) / halbKmY;
    return {
      w, h,
      x: (lon) => w / 2 + (lon - mitteLon) * kmProGradLon * sx,
      y: (lat) => h / 2 - (lat - mitteLat) * KM_JE_GRAD * sy,
      lon: (px) => mitteLon + (px - w / 2) / (kmProGradLon * sx),
      lat: (py) => mitteLat - (py - h / 2) / (KM_JE_GRAD * sy),
      kmZuPxY: (km) => km * sy,
      //: Punkte auf dem kurzen Weg zur Bildmitte — für Pins und Wohnort
      xKurz: (lon) => w / 2 + lonAbstand(lon, mitteLon) * kmProGradLon * sx,
    };
  }

  /* Ohne Wohnort zeigt die Karte, wo die Daten liegen. Früher stand dort fest
     Mitteleuropa; seit die Sammlung weltweit ist, käme das einer Karte gleich,
     die neun Zehntel ihres Inhalts verschweigt. */
  const datenRahmen = () => (cfg.datenRahmen && cfg.datenRahmen()) || null;

  /** Sichtbare Höhe in Kilometern ohne Zoom: um den Wohnort der Bereich,
      sonst der ganze Datenbestand. */
  function grundspanne() {
    const wohnort = cfg.wohnort();
    if (wohnort && cfg.umkreisAktiv()) {
      const bis = cfg.umkreisBis();
      if (bis) return Math.max(30, bis * 1.35);
    }
    if (wohnort) return 2100;
    const box = datenRahmen();
    // 111 km je Breitengrad, ein Zehntel Rand
    return box ? Math.max(2100, (box[1] - box[0]) * KM_JE_GRAD * 1.1) : 2100;
  }

  /** Die tatsächlich gezeigte Höhe: nie mehr als die ganze Erde.

      Ohne diese Grenze reichte der kleinste Zoom bis 105.000 km halber Höhe —
      das Fünffache des Erddurchmessers. Zu sehen war dann eine
      briefmarkengroße Welt inmitten von Nichts, und weil die Projektion
      Breitengrade jenseits der Pole weiterrechnet, zogen die Umrisse
      Schlieren. */
  function spanne() {
    return Math.min(WELT_HALB_KM, grundspanne() / karte.zoom);
  }

  /** Weiter herauszoomen als bis zur ganzen Erde bringt nichts.

      Die Untergrenze haengt davon ab, wie gross der Ausschnitt ohne Zoom
      schon ist: Bei einem Bereich von 250 km ist mehr Weg zurueckzulegen als
      bei einer Weltansicht. */
  const zoomMin = () => Math.min(1, grundspanne() / WELT_HALB_KM);

  function mittelpunkt() {
    if (karte.center) return karte.center;
    const wohnort = cfg.wohnort();
    if (wohnort) return { lat: wohnort.lat, lon: wohnort.lon };
    const box = datenRahmen();
    return box ? { lat: (box[0] + box[1]) / 2, lon: (box[2] + box[3]) / 2 }
               : { lat: 52.5, lon: 12.0 };
  }

  /** Der Mittelpunkt, so weit verschoben, dass die Pole im Bild bleiben.

      Sonst schiebt ein Zug nach unten die Karte ins Leere und man sieht
      Umrisse, die es unterhalb des Südpols nicht gibt. */
  function mittelpunktImBild(spanneKm) {
    const m = mittelpunkt();
    const halbGrad = spanneKm / KM_JE_GRAD;
    const grenze = Math.max(0, 90 - halbGrad);
    return { lat: Math.max(-grenze, Math.min(grenze, m.lat)), lon: aufsRund(m.lon) };
  }

  /* ---------------- Zeichnen ---------------- */

  function zeichnen() {
    const cv = karte.canvas;
    if (!cv || !cv.clientWidth) return;
    const ctx = karte.ctx;
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth;
    // Am Telefon ist das Bild schmal und hoch: Ein 16:7-Streifen wäre dort
    // 120 Pixel hoch und zeigte vom Bereich nichts Brauchbares.
    const h = Math.round(w * (w < 520 ? 0.95 : w < 760 ? 0.65 : 0.44));
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
      cv.style.height = h + 'px';
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const sichtbar = spanne();
    const m = mittelpunktImBild(sichtbar);
    const v = sicht(m.lat, m.lon, sichtbar, w, h);
    karte.view = v;

    ctx.fillStyle = '#080b10';                 // Wasser
    ctx.fillRect(0, 0, w, h);

    umrisseZeichnen(ctx, v, m, w, h, sichtbar);
    bereichZeichnen(ctx, v);
    pinsZeichnen(ctx, v);
    wohnortZeichnen(ctx, v);
    massstab(ctx, v, h, sichtbar);
    beschriftung();
  }

  /** Land und Küstenlinien.

      Jeder Ring wird als Ganzes verschoben, damit er zusammenhängend bleibt —
      und bei weiter Sicht mehrfach gezeichnet, weil die Erde sich wiederholt.
      Ringe außerhalb des Ausschnitts bleiben liegen: Die Weltkarte hat rund
      90.000 Punkte, beim Hineinzoomen liegt das meiste davon weit weg. */
  function umrisseZeichnen(ctx, v, m, w, h, sichtbar) {
    const fenster = {
      lon0: v.lon(-40), lon1: v.lon(w + 40),
      lat0: v.lat(h + 40), lat1: v.lat(-40),
    };

    // Nah dran die feinen Umrisse, sonst die grobe Weltkarte: In der
    // Weltansicht kostet jeder Punkt Zeichenzeit, in der Nahansicht fiele
    // jede Vereinfachung als Kante auf.
    const box = cfg.fineBox;
    const nah = sichtbar <= 1200;
    const imFeinen = box && fenster.lon0 >= box[0] && fenster.lon1 <= box[1]
                         && fenster.lat0 >= box[2] && fenster.lat1 <= box[3];
    const umrisse = (nah && imFeinen && cfg.weltFein && cfg.weltFein.length)
      ? cfg.weltFein : (cfg.welt || []);

    ctx.beginPath();
    for (const ring of umrisse) {
      const r = ringRahmen(ring);
      if (r.lat1 < fenster.lat0 || r.lat0 > fenster.lat1) continue;
      // Grundversatz: den Ring auf die Erdumrundung schieben, die der
      // Bildmitte am nächsten liegt.
      const basis = -360 * Math.round((r.mitte - m.lon) / 360);
      for (const zusatz of [-360, 0, 360]) {
        const versatz = basis + zusatz;
        if (r.lon1 + versatz < fenster.lon0 || r.lon0 + versatz > fenster.lon1) continue;
        let begonnen = false;
        for (const [lon, lat] of ring) {
          const px = v.x(lon + versatz), py = v.y(lat);
          if (!begonnen) { ctx.moveTo(px, py); begonnen = true; } else ctx.lineTo(px, py);
        }
        ctx.closePath();
      }
    }
    ctx.fillStyle = '#39424f';                 // Land, deutlich heller als Wasser
    ctx.fill('evenodd');
    ctx.strokeStyle = '#7d8899';               // Küstenlinie
    ctx.lineWidth = 0.9;
    ctx.stroke();
  }

  /** Der Suchbereich als Ring: von der inneren bis zur äußeren Grenze.

      Die Projektion ist in beiden Achsen maßstabsgleich, ein Bildschirmkreis
      entspricht also einer echten Luftlinie. */
  function bereichZeichnen(ctx, v) {
    const wohnort = cfg.wohnort();
    if (!wohnort || !cfg.umkreisAktiv()) return;
    const bis = cfg.umkreisBis();
    const von = cfg.umkreisVon() || 0;
    const hx = v.xKurz(wohnort.lon), hy = v.y(wohnort.lat);
    const aussen = bis === null || bis === undefined ? null : v.kmZuPxY(bis);
    const innen = von > 0 ? v.kmZuPxY(von) : 0;
    // Ein Kreis, der zwanzigmal so gross ist wie das Bild, kostet nur Zeit.
    const zuGross = (r) => r > 20 * (v.w + v.h);

    if (aussen !== null && !zuGross(aussen)) {
      ctx.beginPath();
      ctx.ellipse(hx, hy, aussen, aussen, 0, 0, Math.PI * 2);
      if (innen > 0 && innen < aussen) {
        ctx.moveTo(hx + innen, hy);
        ctx.ellipse(hx, hy, innen, innen, 0, 0, Math.PI * 2);
      }
      ctx.fillStyle = 'rgba(226,35,26,.16)';
      ctx.fill('evenodd');
    }

    ctx.strokeStyle = '#ff3b30';
    ctx.lineWidth = 2.2;
    ctx.setLineDash([6, 5]);
    for (const r of [innen, aussen]) {
      if (!r || zuGross(r)) continue;
      ctx.beginPath();
      ctx.ellipse(hx, hy, r, r, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }

  function pinsZeichnen(ctx, v) {
    for (const p of karte.pins) {
      p.px = v.xKurz(p.lon);
      p.py = v.y(p.lat);
    }
    karte.pins.forEach((p, i) => {
      ctx.beginPath();
      ctx.arc(p.px, p.py, i === karte.hover ? 7 : 4.5, 0, Math.PI * 2);
      ctx.fillStyle = p.pct >= 50 ? '#ffb703' : '#f2f0ec';
      ctx.fill();
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = '#0b0b0d';
      ctx.stroke();
    });
  }

  /** Wohnort als Kreuz. */
  function wohnortZeichnen(ctx, v) {
    const wohnort = cfg.wohnort();
    if (!wohnort) return;
    const hx = v.xKurz(wohnort.lon), hy = v.y(wohnort.lat);
    ctx.strokeStyle = '#6ec36e';
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.moveTo(hx - 7, hy); ctx.lineTo(hx + 7, hy);
    ctx.moveTo(hx, hy - 7); ctx.lineTo(hx, hy + 7);
    ctx.stroke();
  }

  /** Maßstabsbalken, passend zum sichtbaren Ausschnitt. */
  function massstab(ctx, v, h, sichtbar) {
    const schritt = sichtbar >= 4000 ? 2000 : sichtbar >= 800 ? 500
                  : sichtbar >= 300 ? 100 : sichtbar >= 80 ? 25
                  : sichtbar >= 25 ? 10 : 2;
    ctx.strokeStyle = '#9a978f';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(14, h - 16); ctx.lineTo(14 + v.kmZuPxY(schritt), h - 16);
    ctx.stroke();
    ctx.fillStyle = '#9a978f';
    ctx.font = '11px system-ui, sans-serif';
    ctx.fillText(`${schritt} km`, 14, h - 22);
  }

  /** „0–200 km", „ab 300 km", „bis 200 km" — der eingestellte Bereich. */
  function bereichText() {
    const t = cfg.t;
    const zahl = (n) => Number(n).toLocaleString(cfg.sprache());
    const von = cfg.umkreisVon() || 0;
    const bis = cfg.umkreisBis();
    if (bis === null || bis === undefined) return t('map.rangeFrom', { von: zahl(von) });
    if (!von) return t('map.rangeTo', { bis: zahl(bis) });
    return t('map.range', { von: zahl(von), bis: zahl(bis) });
  }

  /** Text unter der Karte: was gerade zu sehen ist. */
  function beschriftung() {
    const cap = document.getElementById('map-caption');
    if (!cap) return;
    const t = cfg.t;
    const wohnort = cfg.wohnort();
    const zoomInfo = karte.zoom !== 1 || karte.center
      ? t('map.view', { zoom: karte.zoom.toFixed(karte.zoom < 1 ? 2 : 1) })
      : t(tippgeraet ? 'map.zoomHintTouch' : 'map.zoomHint');
    const zeiger = karte.hover >= 0 ? karte.pins[karte.hover] : null;
    const n = karte.pins.length;

    if (zeiger) {
      cap.textContent = `${zeiger.name} — `
        + (zeiger.pct === null ? '' : `${zeiger.pct.toFixed(0)} % ${t('card.match')}`)
        + (zeiger.dist === null ? '' : `, ${zeiger.dist.toLocaleString(cfg.sprache())} km`);
      return;
    }
    if (!wohnort) {
      cap.textContent = t('map.captionNoHome') + zoomInfo;
      return;
    }
    if (!cfg.umkreisAktiv()) {
      // Ohne Entfernungsfilter wäre „im Umkreis von 200 km" eine Behauptung,
      // die nicht stimmt — die Liste reicht dann weiter.
      const schluessel = n === 0 ? 'map.captionOhneUmkreisLeer'
                       : n === 1 ? 'map.captionOhneUmkreis1'
                                 : 'map.captionOhneUmkreis';
      cap.textContent = t(schluessel, { n, ort: wohnort.label }) + zoomInfo;
      return;
    }
    const spanneText = bereichText();
    const schluessel = n === 0 ? 'map.captionBereichLeer'
                     : n === 1 ? 'map.captionBereich1'
                               : 'map.captionBereich';
    cap.textContent = t(schluessel, { n, spanne: spanneText, ort: wohnort.label })
      + zoomInfo;
  }

  /* ---------------- Bedienung ---------------- */

  /** Nächster Pin zu einem Punkt im Bild, oder -1. */
  function pinBei(mx, my, radius) {
    let treffer = -1, best = radius * radius;
    karte.pins.forEach((p, i) => {
      const d = (p.px - mx) ** 2 + (p.py - my) ** 2;
      if (d < best) { best = d; treffer = i; }
    });
    return treffer;
  }

  const begrenzt = (z) => Math.min(ZOOM_MAX, Math.max(zoomMin(), z));

  function zuruecksetzen() {
    karte.zoom = 1;
    karte.center = null;
    zeichnen();
  }

  /** Mittelpunkt setzen — die Länge bleibt dabei im üblichen Bereich. */
  function zentrumSetzen(lat, lon) {
    karte.center = { lat: Math.max(-89.9, Math.min(89.9, lat)), lon: aufsRund(lon) };
  }

  function verdrahten() {
    const cv = karte.canvas;

    // Zoom am Mauszeiger: der Punkt unter dem Cursor bleibt liegen
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      const v = karte.view;
      if (!v) return;
      const r = cv.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const lon0 = v.lon(mx), lat0 = v.lat(my);

      const naechster = begrenzt(karte.zoom * Math.exp(-e.deltaY * 0.0015));
      if (naechster === karte.zoom) return;
      karte.zoom = naechster;

      const sichtbar = spanne();
      const m = mittelpunktImBild(sichtbar);
      const v2 = sicht(m.lat, m.lon, sichtbar, cv.clientWidth, cv.clientHeight);
      zentrumSetzen(m.lat + (lat0 - v2.lat(my)), m.lon + (lon0 - v2.lon(mx)));
      zeichnen();
    }, { passive: false });

    cv.addEventListener('mousedown', (e) => {
      karte.drag = { x: e.clientX, y: e.clientY, center: mittelpunktImBild(spanne()) };
      karte.moved = false;
      cv.style.cursor = 'grabbing';
    });

    window.addEventListener('mouseup', () => {
      if (!karte.drag) return;
      karte.drag = null;
      cv.style.cursor = karte.hover >= 0 ? 'pointer' : 'default';
    });

    cv.addEventListener('dblclick', zuruecksetzen);

    cv.addEventListener('mousemove', (e) => {
      const r = cv.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;

      if (karte.drag && karte.view) {
        const v = karte.view;
        const dLon = v.lon(mx) - v.lon(mx - (e.clientX - karte.drag.x));
        const dLat = v.lat(my) - v.lat(my - (e.clientY - karte.drag.y));
        zentrumSetzen(karte.drag.center.lat - dLat, karte.drag.center.lon - dLon);
        if (Math.abs(e.clientX - karte.drag.x) + Math.abs(e.clientY - karte.drag.y) > 3) {
          karte.moved = true;
        }
        zeichnen();
        return;
      }

      const treffer = pinBei(mx, my, 12);
      if (treffer !== karte.hover) {
        karte.hover = treffer;
        cv.style.cursor = treffer >= 0 ? 'pointer' : 'default';
        zeichnen();
      }
    });

    cv.addEventListener('mouseleave', () => {
      if (karte.hover !== -1) { karte.hover = -1; zeichnen(); }
    });

    cv.addEventListener('click', () => {
      if (karte.moved) { karte.moved = false; return; }   // war ein Verschieben
      if (karte.hover < 0) return;
      cfg.aufPinKlick(karte.pins[karte.hover].eintragId);
    });

    const stufe = (faktor) => { karte.zoom = begrenzt(karte.zoom * faktor); zeichnen(); };
    document.getElementById('zoom-in').addEventListener('click', () => stufe(1.5));
    document.getElementById('zoom-out').addEventListener('click', () => stufe(1 / 1.5));
    document.getElementById('zoom-reset').addEventListener('click', zuruecksetzen);

    // Zwei Finger zoomen und verschieben. Bewusst nicht ein Finger: Die Karte
    // steht mitten im Seitenfluss, und wer mit dem Daumen weiterscrollen will,
    // bliebe sonst darauf hängen. Ein Fingertipp wählt weiterhin einen Pin.
    let fingerspanne = 0, mitte = null;
    const abstand = (t) => Math.hypot(t[0].clientX - t[1].clientX,
                                      t[0].clientY - t[1].clientY);
    const zentrum = (t) => ({ x: (t[0].clientX + t[1].clientX) / 2,
                              y: (t[0].clientY + t[1].clientY) / 2 });

    cv.addEventListener('touchstart', (e) => {
      if (e.touches.length === 2) {
        fingerspanne = abstand(e.touches);
        mitte = zentrum(e.touches);
        return;
      }
      // Ein Tipp wählt den nächsten Pin - am Telefon gibt es kein Zeigen.
      if (e.touches.length !== 1 || !karte.pins.length) return;
      const r = cv.getBoundingClientRect();
      const treffer = pinBei(e.touches[0].clientX - r.left,
                             e.touches[0].clientY - r.top, 26);  // großzügiger als die Maus
      if (treffer !== karte.hover) { karte.hover = treffer; zeichnen(); }
    }, { passive: true });

    cv.addEventListener('touchmove', (e) => {
      if (e.touches.length !== 2 || !fingerspanne || !karte.view) return;
      e.preventDefault();
      const jetztAbstand = abstand(e.touches);
      karte.zoom = begrenzt(karte.zoom * (jetztAbstand / fingerspanne));
      fingerspanne = jetztAbstand;

      const jetzt = zentrum(e.touches);
      const v = karte.view, m = mittelpunktImBild(spanne());
      zentrumSetzen(m.lat + (v.lat(mitte.y) - v.lat(jetzt.y)),
                    m.lon + (v.lon(mitte.x) - v.lon(jetzt.x)));
      mitte = jetzt;
      zeichnen();
    }, { passive: false });

    cv.addEventListener('touchend', () => { fingerspanne = 0; mitte = null; });

    window.addEventListener('resize', zeichnen);
  }

  return {
    /** einstellungen: {t, sprache, wohnort, umkreisAktiv, umkreisVon, umkreisBis,
        datenRahmen, welt, weltFein, fineBox, aufPinKlick} */
    start(einstellungen) {
      cfg = einstellungen;
      karte.canvas = document.getElementById('map');
      if (!karte.canvas) return;
      karte.ctx = karte.canvas.getContext('2d');
      verdrahten();
      zeichnen();
    },
    zeichnen,
    setzePins(liste) {
      karte.pins = liste;
      karte.hover = -1;
    },
    zentrieren() {
      karte.center = null;
    },
  };
})();
