/* Was um die Kette herum liegt: Hilfetexte, Installation, Zählung,
   Rückmeldung, Rechtstexte.

   Alles davon ist für sich genommen klein und hat mit dem Suchen nichts zu
   tun — zusammen war es ein Drittel der alten app.js. */

(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);

  /* ---------------- Hilfetexte ----------------
     Auf Touchgeräten gibt es kein Mouseover, deshalb öffnet ein Klick auf das
     Fragezeichen den Text in einem Feld. Am Rechner bleibt zusätzlich der
     native Tooltip erhalten. */

  function hilfe() {
    // Der Zustand gehört an den Knopf, sonst kündigt ein Screenreader das
    // Aufklappen nicht an.
    for (const btn of document.querySelectorAll('button.help')) {
      btn.setAttribute('aria-expanded', 'false');
    }
    const box = document.createElement('div');
    box.className = 'help-box';
    box.hidden = true;
    box.setAttribute('role', 'status');
    document.body.append(box);

    let offen = null;

    function schliessen() {
      box.hidden = true;
      if (offen) {
        offen.classList.remove('on');
        offen.setAttribute('aria-expanded', 'false');
      }
      offen = null;
    }

    function oeffnen(btn) {
      box.textContent = btn.getAttribute('title') || '';
      box.hidden = false;
      btn.classList.add('on');
      btn.setAttribute('aria-expanded', 'true');
      offen = btn;

      // unter dem Fragezeichen platzieren, aber im Fenster halten
      const r = btn.getBoundingClientRect();
      const breite = Math.min(320, window.innerWidth - 24);
      box.style.width = breite + 'px';
      let links = r.left + window.scrollX + r.width / 2 - breite / 2;
      links = Math.max(12, Math.min(links, window.innerWidth - breite - 12));
      box.style.left = links + 'px';
      box.style.top = (r.bottom + window.scrollY + 8) + 'px';
    }

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('button.help');
      if (btn) {
        e.preventDefault();
        e.stopPropagation();
        if (offen === btn) schliessen(); else oeffnen(btn);
        return;
      }
      if (!e.target.closest('.help-box')) schliessen();
    });

    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') schliessen(); });
    window.addEventListener('resize', schliessen);
    window.addEventListener('scroll', schliessen, { passive: true });
  }

  /* ---------------- Installierbarkeit ----------------
     Der Service Worker legt die Seite ab, damit sie vom Startbildschirm auch
     ohne Netz startet. Er verlangt eine eigene Adresse über HTTPS; in der
     eingebetteten Fassung ist das gesperrt, deshalb die Prüfungen. */

  function pwa() {
    const eigenstaendig = window.top === window.self;
    const sicher = location.protocol === 'https:' || location.hostname === 'localhost';
    if ('serviceWorker' in navigator && eigenstaendig && sicher) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('sw.js')
          .catch(() => { /* ohne ist es auch nutzbar */ });
      });
    }

    const knopf = $('install');
    if (!knopf) return;

    // Android und Desktop-Chrome melden sich, wenn eine Installation möglich ist
    let angebot = null;
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      angebot = e;
      knopf.hidden = false;
    });

    knopf.addEventListener('click', async () => {
      if (!angebot) return;
      angebot.prompt();
      await angebot.userChoice;
      angebot = null;
      knopf.hidden = true;
    });

    window.addEventListener('appinstalled', () => { knopf.hidden = true; });

    // iOS kennt kein Installationsangebot — dort führt der Weg über das
    // Teilen-Menü, deshalb dort ein Hinweis statt eines Knopfes.
    const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const installiert = window.matchMedia('(display-mode: standalone)').matches ||
                        navigator.standalone === true;
    if (iOS && !installiert && eigenstaendig) {
      const hinweis = $('install-hint');
      if (hinweis) hinweis.hidden = false;
    }
  }

  /* ---------------- Zugriffszählung ----------------
     Eine statische Seite kann sich nicht selbst zählen. Ist in config.js eine
     GoatCounter-Kennung hinterlegt, meldet die Seite den Aufruf dorthin — ohne
     Cookies, ohne Zugriff auf den Gerätespeicher. Ohne Kennung passiert gar
     nichts.

     Die Seite selbst zeigt keinen Zählerstand, auch nicht auf Umwegen: Der
     Stand steht ausschließlich im GoatCounter-Konto hinter der Anmeldung. */

  function zaehler() {
    const code = ((window.CONFIG && window.CONFIG.zaehler) || '').trim();
    const eigenstaendig = window.top === window.self;
    const echteAdresse = location.protocol === 'https:' &&
                         location.hostname !== 'localhost';
    // Eingebettet sperrt die Sicherheitsrichtlinie den Aufruf, lokal zählt
    // GoatCounter ohnehin nicht - dann unterbleibt auch der Hinweis.
    const zaehlt = Boolean(code) && eigenstaendig && echteAdresse;

    const hinweis = $('zaehler-hinweis');
    if (hinweis) hinweis.hidden = !zaehlt;
    if (!zaehlt) return;

    const s = document.createElement('script');
    s.async = true;
    s.src = 'https://gc.zgo.at/count.js';
    s.dataset.goatcounter = `https://${code}.goatcounter.com/count`;
    document.head.append(s);
  }

  /* ---------------- Rückmeldung ----------------
     Die veröffentlichte Fassung darf keine fremden Server aufrufen, ein
     Formularversand scheidet damit aus. Der Text wird lokal zusammengesetzt
     und an das E-Mail-Programm übergeben; abgeschickt wird erst dort. */

  const MAIL = 'waldsprenger@gmail.com';

  function rueckmeldung(t, datenstand) {
    if (!$('fb-send')) return;
    const status = $('fb-status');

    const text = () => {
      const art = $('fb-art').value;
      const nachricht = $('fb-text').value.trim();
      const kontakt = $('fb-kontakt').value.trim();
      const zeilen = [nachricht];
      if (kontakt) zeilen.push('', `Rückmeldeadresse: ${kontakt}`);
      zeilen.push('', `— Datenstand ${datenstand()}`);
      return { betreff: `Festival Finder: ${art}`, koerper: zeilen.join('\n'),
               nachricht };
    };

    const pruefen = () => {
      if (text().nachricht) return true;
      status.className = 'hint err';
      status.textContent = t('fb.needText');
      $('fb-text').focus();
      return false;
    };

    // Ein echter Link statt eines Sprungs per Skript: In der eingebetteten
    // Fassung wird eine gesetzte Adresse geblockt, ein Klick auf mailto nicht.
    const linkSetzen = () => {
      const { betreff, koerper } = text();
      $('fb-send').href = `mailto:${MAIL}` +
        `?subject=${encodeURIComponent(betreff)}&body=${encodeURIComponent(koerper)}`;
    };

    $('fb-send').addEventListener('click', (e) => {
      if (!pruefen()) { e.preventDefault(); return; }
      linkSetzen();
      status.className = 'hint ok';
      status.textContent = t('fb.opened');
    });

    for (const id of ['fb-art', 'fb-text', 'fb-kontakt']) {
      $(id).addEventListener('input', linkSetzen);
      $(id).addEventListener('change', linkSetzen);
    }
    linkSetzen();

    $('fb-copy').addEventListener('click', async () => {
      if (!pruefen()) return;
      const { betreff, koerper } = text();
      try {
        await navigator.clipboard.writeText(
          `An: ${MAIL}\nBetreff: ${betreff}\n\n${koerper}`);
        status.className = 'hint ok';
        status.textContent = t('fb.copied', { mail: MAIL });
      } catch (_) {
        status.className = 'hint err';
        status.textContent = t('fb.copyFailed');
      }
    });

    for (const id of ['fb-text', 'fb-kontakt']) {
      $(id).addEventListener('input', () => {
        if (status.textContent) { status.className = 'hint'; status.textContent = ''; }
      });
    }
  }

  /* ---------------- Rechtstexte ----------------
     Nur die gebündelte Einzelseite enthält Impressum und Datenschutz als
     Abschnitte. Dort bleiben sie eingeklappt, bis der Fußlink sie öffnet. In
     der lokalen Fassung sind es eigene Dateien — dann tut das hier nichts. */

  function rechtstexte(t) {
    const ids = ['impressum', 'datenschutz'];
    const abschnitte = ids.map((id) => $(id)).filter(Boolean);
    if (!abschnitte.length) return;

    for (const sec of abschnitte) {
      sec.hidden = true;
      const zurueck = document.createElement('button');
      zurueck.type = 'button';
      zurueck.className = 'ghost small legal-close';
      // Der Rechtstext bleibt deutsch, der Weg zurück ist Oberfläche — die
      // Auszeichnung sorgt dafür, dass ein Sprachwechsel ihn mitnimmt.
      zurueck.dataset.i18n = 'legal.back';
      zurueck.dataset.i18nTitle = 'legal.backTitle';
      zurueck.textContent = t('legal.back');
      zurueck.title = t('legal.backTitle');
      zurueck.addEventListener('click', () => zeigen(null));
      sec.append(zurueck);
    }

    function zeigen(id) {
      for (const sec of abschnitte) sec.hidden = sec.id !== id;
      const main = document.querySelector('main');
      const fuss = document.querySelector('.site-footer');
      if (main) main.hidden = !!id;
      if (fuss) fuss.hidden = !!id;
      if (id) $(id).scrollIntoView({ block: 'start' });
      else window.scrollTo({ top: 0 });
    }

    for (const a of document.querySelectorAll('.site-footer nav a')) {
      const id = (a.getAttribute('href') || '').replace('#', '');
      if (!ids.includes(id)) continue;
      a.addEventListener('click', (e) => { e.preventDefault(); zeigen(id); });
    }
  }

  window.FF = window.FF || {};
  FF.oberflaeche = { hilfe, pwa, zaehler, rueckmeldung, rechtstexte };
})();
