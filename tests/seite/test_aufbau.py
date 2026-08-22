"""Die Seite und ihr Skript müssen zueinander passen.

Python kann kein JavaScript ausführen, wohl aber lesen. Diese Prüfungen fangen
genau die Fehler ab, die im Browser erst beim ersten Klick auffallen — und dann
still: Das Skript bricht ab, und die Seite bleibt leer.
"""

import re

from festivalfinder.ausgabe.seitenteile import skripte, stile, vorrat
from festivalfinder.pfade import SITE

SEITE = (SITE / "index.html").read_text(encoding="utf-8")
JS = {p: (SITE / p).read_text(encoding="utf-8") for p in skripte()
      if (SITE / p).exists()}

#: Die Kette, in der Reihenfolge, in der sie gestellt wird
SCHRITTE = ("ort", "zeit", "entfernung", "preis", "bands", "genre")


class TestKette:
    def test_die_reihenfolge_steht_an_beiden_stellen_gleich(self):
        """Als Abschnitte in index.html und als Liste KETTE im Skript."""
        in_der_seite = tuple(re.findall(r'data-schritt="(\w+)"', SEITE))
        assert in_der_seite == SCHRITTE, f"index.html: {in_der_seite}"

        m = re.search(r"const KETTE = \[([^\]]+)\]", JS["js/zustand.js"])
        assert m, "zustand.js kennt keine KETTE"
        im_skript = tuple(re.findall(r"'(\w+)'", m.group(1)))
        assert im_skript == SCHRITTE, f"zustand.js: {im_skript}"

    def test_jeder_schritt_hat_seine_teile(self):
        for name in SCHRITTE:
            abschnitt = re.search(rf'data-schritt="{name}"(.*?)</section>', SEITE, re.S)
            assert abschnitt, f"Abschnitt für {name} fehlt"
            assert 'class="koerper"' in abschnitt.group(1), f"{name}: kein Körper"
        for name in ("entfernung", "preis", "bands", "genre"):
            assert f'data-wahl="{name}" data-wert="ja"' in SEITE, f"{name}: kein Ja"
            assert f'data-wahl="{name}" data-wert="nein"' in SEITE, f"{name}: kein Nein"
            assert f'id="{name}-inhalt" hidden' in SEITE, \
                f"{name}-inhalt fehlt oder startet sichtbar"

    def test_nur_der_erste_schritt_ist_zu_beginn_sichtbar(self):
        """Wären alle Abschnitte von Anfang an sichtbar, wäre es dieselbe lange
        Seite wie vorher, nur mit mehr Überschriften."""
        for name in SCHRITTE[1:]:
            assert re.search(rf'data-schritt="{name}"[^>]*\shidden', SEITE), \
                f"{name} ist von Anfang an sichtbar"
        assert not re.search(r'data-schritt="ort"[^>]*\shidden', SEITE)
        assert re.search(r'id="s-ergebnis"[^>]*\shidden', SEITE)
        assert re.search(r'id="karte-block"[^>]*\shidden', SEITE)


class TestFelder:
    def test_die_seite_greift_nur_nach_vorhandenen_feldern(self):
        """$('radius') auf ein Feld, das umbenannt wurde, wirft erst im Browser."""
        kennungen = set(re.findall(r'id="([\w-]+)"', SEITE))
        fehlt = set()
        for name, inhalt in JS.items():
            gesucht = re.findall(r"\$\('([\w-]+)'\)", inhalt)
            gesucht += re.findall(r"getElementById\('([\w-]+)'\)", inhalt)
            for kennung in gesucht:
                if kennung not in kennungen:
                    fehlt.add(f"{name}: #{kennung}")
        assert not fehlt, f"Felder fehlen in index.html: {fehlt}"


class TestSortierung:
    def test_reihenfolge_und_vorgabe(self):
        """Übereinstimmung, Entfernung, Datum, Preis — und die Vorgabe wandert
        mit. Als sie in einem festen Wert steckte, blieb sie auf „Datum"
        stehen, während die Prozentzahl danebenstand."""
        z = JS["js/zustand.js"]
        assert re.search(r"sortierung:\s*null", z)
        m = re.search(r"function sortierungen\(\) \{(.*?)\n  \}", z, re.S)
        assert m, "sortierungen() nicht gefunden"
        assert re.findall(r"'(match|distance|price|date)'", m.group(1)) == \
            ["match", "distance", "date", "price"]
        # Nur anbieten, was auch ordnen kann
        assert "if (gewichtet()) liste.push('match')" in z
        assert "if (state.home) liste.push('distance')" in z
        assert "state.sortierung && erlaubt.includes(state.sortierung)" in z


class TestKarte:
    def test_sie_kennt_den_bereich_statt_eines_umkreises(self):
        """Ein einzelner Kreis würde eine untere Grenze verschweigen."""
        karte = JS["js/karte.js"]
        for handgriff in ("umkreisVon", "umkreisBis", "umkreisAktiv"):
            assert f"cfg.{handgriff}()" in karte
            assert f"{handgriff}:" in JS["js/start.js"]

    def test_sie_zoomt_nicht_ueber_die_erde_hinaus(self):
        """Der kleinste Zoom reichte bis 105.000 km halber Höhe, das Fünffache
        des Erddurchmessers. Sichtbar war das als Streifenmuster, sobald der
        Maßstabsbalken über 500 km sprang."""
        karte = JS["js/karte.js"]
        assert "WELT_HALB_KM" in karte
        assert re.search(r"Math\.min\(WELT_HALB_KM,", karte)
        assert "mittelpunktImBild" in karte

    def test_ein_ring_wird_als_ganzes_verschoben(self):
        """Wurde jeder Punkt einzeln gefaltet, sprangen bei einem Ring über die
        Datumsgrenze zwei Nachbarn von einer Bildkante zur anderen."""
        karte = JS["js/karte.js"]
        assert "const basis = -360 * Math.round" in karte
        assert "xKurz" in karte, "die Pins brauchen weiter den kurzen Weg"


class TestModule:
    def test_jedes_modul_wird_eingebunden(self):
        vorhanden = {f"js/{p.name}" for p in (SITE / "js").glob("*.js")}
        eingebunden = set(skripte())
        assert vorhanden <= eingebunden, \
            f"nicht eingebunden: {sorted(vorhanden - eingebunden)}"

    def test_die_daten_kommen_vor_den_modulen(self):
        """daten.js liest window.DATA — data.js muss vorher geladen sein."""
        reihe = skripte()
        assert reihe.index("data.js") < reihe.index("js/daten.js")
        assert reihe.index("js/daten.js") < reihe.index("js/text.js")
        assert reihe.index("js/zustand.js") < reihe.index("js/liste.js")
        assert reihe.index("js/start.js") == len(reihe) - 1, "start.js gehört zuletzt"

    def test_der_service_worker_haelt_alles_vor(self):
        """Fehlt eine Datei im Vorrat, startet die App offline nur halb."""
        v = vorrat()
        for datei in skripte():
            if datei == "orte.js":       # wird nur bei Bedarf nachgeladen
                continue
            assert f"./{datei}" in v, f"nicht im Vorrat: {datei}"
        for datei in stile():
            assert f"./{datei}" in v


class TestFaltung:
    def test_die_seite_bringt_keine_eigene_tabelle_mit(self):
        """Als Sammler und Suche je eine pflegten, sind sie auseinandergelaufen
        — bei 5.172 von 40.538 Bandnamen."""
        text_js = JS["js/text.js"]
        assert "FF.D.faltung" in text_js, "text.js liest die Regeln nicht aus den Daten"
        # Keine eigene Ersatztabelle mehr im Skript
        assert "'ß', 'ss'" not in text_js and '"ß"' not in text_js

    def test_die_regeln_reisen_mit(self):
        from festivalfinder.ausgabe import daten_js
        quelle = (SITE.parent / "festivalfinder" / "ausgabe" / "daten_js.py") \
            .read_text(encoding="utf-8")
        assert '"faltung": REGELN' in quelle


def test_keine_steuerzeichen_in_ausgelieferten_dateien():
    """Ein Steuerzeichen im Quelltext sieht man nicht — es wirkt trotzdem.

    In app.js stand einmal eine Prüfung auf „EUR" mit zwei Rückschrittzeichen
    statt der Wortgrenzen, weil ein Patch die Backslashes gefressen hatte. Die
    Prüfung traf nie, und jeder Preis erschien doppelt.
    """
    erlaubt = set("\t\n\r")
    wurzel = SITE.parent
    kaputt = []
    for ordner, muster in ((SITE, "*.*"), (SITE / "js", "*.js"),
                           (wurzel / "festivalfinder", "**/*.py"),
                           (wurzel / "tests", "**/*.py")):
        for datei in sorted(ordner.glob(muster)):
            if datei.is_dir() or datei.suffix in (".gz", ".png", ".webmanifest"):
                continue
            try:
                inhalt = datei.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                kaputt.append(f"{datei.name}: nicht als UTF-8 lesbar")
                continue
            if inhalt.startswith("﻿"):
                kaputt.append(f"{datei.name}: beginnt mit einer Byte-Reihenfolge-Marke")
            for nr, zeile in enumerate(inhalt.splitlines(), 1):
                schlimm = {z for z in zeile if ord(z) < 32 and z not in erlaubt}
                if schlimm:
                    zeichen = ", ".join(f"U+{ord(z):04X}" for z in sorted(schlimm))
                    kaputt.append(f"{datei.name}:{nr}: {zeichen}")
    assert not kaputt, "Steuerzeichen gefunden:\n" + "\n".join(kaputt)
