"""Die Sprachdatei der Webseite: Ein Tippfehler nimmt die ganze Seite mit.

Ein einziges nicht geschütztes Apostroph in einer Zeichenkette ("Avrupa'nın")
beendet sie mitten im Satz - der Browser bricht die Datei ab, und statt der
Oberfläche stehen die Schlüsselnamen auf der Seite. Python kann kein
JavaScript ausführen, wohl aber die Form prüfen: Was hier nicht als
Zeichenkette durchgeht, geht auch dort nicht durch.
"""

import re

from gemeinsam import SITE

I18N = (SITE / "i18n.js").read_text(encoding="utf-8")

#: 'so' oder "so", geschützte Zeichen eingeschlossen
KETTE = r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\""
#: de: 'Text' - Sprachkürzel und Wert
EINTRAG = re.compile(rf"\b([a-z]{{2}}):\s*({KETTE})")
#: 'app.tagline': { - Beginn eines Textblocks, allein oder mit Einträgen dahinter
BEGINN = re.compile(rf"^\s*({KETTE}):\s*\{{")


def zeilen() -> list[tuple[int, str, str]]:
    """Je Zeile: Nummer, der hier beginnende Schlüssel, der Rest der Zeile."""
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", I18N, flags=re.S)
    heraus = []
    for nr, zeile in enumerate(ohne_kommentare.splitlines(), 1):
        beginn = BEGINN.match(zeile)
        if beginn:
            heraus.append((nr, beginn.group(1)[1:-1], zeile[beginn.end():]))
        elif re.match(r"^\s+[a-z]{2}:", zeile):
            heraus.append((nr, "", zeile))
    return heraus


def texte() -> dict[str, dict[str, str]]:
    """Die Tabelle TEXTE als Wörterbuch: Schlüssel -> Sprache -> Text."""
    tabelle: dict[str, dict[str, str]] = {}
    aktuell = ""
    for _nr, schluessel, rest in zeilen():
        if schluessel:
            aktuell = schluessel
            tabelle.setdefault(aktuell, {})
        if not aktuell:
            continue
        for sprache, wert in EINTRAG.findall(rest):
            tabelle[aktuell][sprache] = wert[1:-1]
    return tabelle


def sprachen() -> set[str]:
    block = I18N.split("SPRACHEN: {", 1)[1].split("},", 1)[0]
    return {s for s, _ in EINTRAG.findall(block)}


def test_jede_zeile_bleibt_in_ihren_anfuehrungszeichen():
    """Nach Abzug der Einträge darf nur Beiwerk übrig bleiben.

    Endet eine Zeichenkette zu früh, bleibt der Rest des Satzes stehen — und
    genau daran ist der Fehler zu erkennen, ohne JavaScript auszuführen.
    """
    kaputt = [f"Zeile {nr}: {rest.strip()[:90]}"
              for nr, _schluessel, rest in zeilen()
              if not re.fullmatch(r"[\s,{}]*", EINTRAG.sub("", rest))]
    assert not kaputt, "Zeichenkette endet zu früh:\n" + "\n".join(kaputt)


def test_jeder_text_kennt_alle_sprachen():
    alle = sprachen()
    assert len(alle) == 10
    fehlt = {k: sorted(alle - set(v)) for k, v in texte().items() if alle - set(v)}
    assert not fehlt, f"unübersetzt: {fehlt}"


def test_platzhalter_stehen_in_jeder_sprache():
    """{n} in der deutschen Fassung heißt {n} in allen anderen."""
    abweichung = {}
    for schluessel, uebersetzt in texte().items():
        soll = set(re.findall(r"\{(\w+)\}", uebersetzt.get("de", "")))
        for sprache, wert in uebersetzt.items():
            if set(re.findall(r"\{(\w+)\}", wert)) != soll:
                abweichung[f"{schluessel}/{sprache}"] = wert
    assert not abweichung, f"Platzhalter passen nicht: {abweichung}"


def test_die_seite_ruft_nur_vorhandene_schluessel():
    """Ein fehlender Schlüssel steht als Rohtext auf der Seite."""
    vorhanden = set(texte())
    fehlt = set()
    for datei in ("app.js", "index.html", "karte.js"):
        inhalt = (SITE / datei).read_text(encoding="utf-8")
        for s in re.findall(r"\bt\(\s*'([\w.]+)'", inhalt):
            # t('genre.' + key) wird erst zur Laufzeit vollständig
            if not s.endswith(".") and s not in vorhanden:
                fehlt.add(f"{datei}: {s}")
    assert not fehlt, f"unbekannte Textschlüssel: {fehlt}"


def test_auch_die_umwegigen_schluessel_gibt_es():
    """Nicht jeder Schlüssel steht direkt in t() - manche über eine Variable.

    Die Kartenbeschriftung wählt ihren Schlüssel je nach Zahl der Pins aus
    drei Möglichkeiten aus; keine davon fände die Prüfung darüber. Also alle
    Zeichenketten nehmen, die aussehen wie ein Schlüssel: Was mit einem
    bekannten Namensraum beginnt ('map.', 'card.', …), muss es auch geben.
    """
    vorhanden = set(texte())
    raeume = {s.split(".", 1)[0] for s in vorhanden}
    fehlt = set()
    for datei in ("app.js", "index.html", "karte.js"):
        inhalt = (SITE / datei).read_text(encoding="utf-8")
        for s in re.findall(r"'([a-z][A-Za-z0-9]*\.[A-Za-z0-9.]+)'", inhalt):
            if s.split(".", 1)[0] in raeume and s not in vorhanden:
                fehlt.add(f"{datei}: {s}")
    assert not fehlt, f"unbekannte Textschlüssel: {fehlt}"


def test_die_seite_greift_nur_nach_vorhandenen_feldern():
    """$('radius') auf ein Feld, das umbenannt wurde, wirft erst im Browser.

    Beim Verstecken der Regler hinter Schaltern sind Felder umgezogen. Ein
    Tippfehler in einer der Kennungen bliebe still: Das Skript bricht beim
    ersten Zugriff ab, und die Seite bleibt leer.
    """
    seite = (SITE / "index.html").read_text(encoding="utf-8")
    kennungen = set(re.findall(r"id=\"([\w-]+)\"", seite))
    fehlt = set()
    for datei in ("app.js", "karte.js"):
        inhalt = (SITE / datei).read_text(encoding="utf-8")
        gesucht = re.findall(r"\$\('([\w-]+)'\)", inhalt)
        gesucht += re.findall(r"getElementById\('([\w-]+)'\)", inhalt)
        for kennung in gesucht:
            if kennung not in kennungen:
                fehlt.add(f"{datei}: #{kennung}")
    assert not fehlt, f"Felder fehlen in index.html: {fehlt}"


#: Die Kette, in der Reihenfolge, in der sie gestellt wird
SCHRITTE = ("ort", "zeit", "entfernung", "preis", "bands", "genre")


def test_die_kette_steht_in_der_richtigen_reihenfolge():
    """Erst der Ort, dann der Zeitraum, dann die drei Filterfragen.

    Die Reihenfolge steht an zwei Stellen: als Abschnitte in index.html und als
    Liste KETTE in app.js. Laufen sie auseinander, erscheint ein Schritt, den
    das Skript nicht kennt - oder umgekehrt.
    """
    seite = (SITE / "index.html").read_text(encoding="utf-8")
    skript = (SITE / "app.js").read_text(encoding="utf-8")

    in_der_seite = tuple(re.findall(r'data-schritt="(\w+)"', seite))
    assert in_der_seite == SCHRITTE, f"index.html: {in_der_seite}"

    m = re.search(r"const KETTE = \[([^\]]+)\]", skript)
    assert m, "app.js kennt keine KETTE"
    im_skript = tuple(re.findall(r"'(\w+)'", m.group(1)))
    assert im_skript == SCHRITTE, f"app.js: {im_skript}"


def test_jeder_schritt_hat_seine_teile():
    """Ein Schritt ohne Koerper klappt weder auf noch zu.

    Die drei Filterfragen brauchen ausserdem ihr Ja/Nein und den Kasten, den
    das Ja hervorholt - dessen Kennung leitet das Skript aus dem Namen ab
    ("entfernung" -> "entfernung-inhalt").
    """
    seite = (SITE / "index.html").read_text(encoding="utf-8")
    for name in SCHRITTE:
        abschnitt = re.search(
            rf'data-schritt="{name}"(.*?)</section>', seite, re.S)
        assert abschnitt, f"Abschnitt fuer {name} fehlt"
        assert 'class="koerper"' in abschnitt.group(1), f"{name}: kein Koerper"
    for name in ("entfernung", "preis", "bands", "genre"):
        assert f'data-wahl="{name}" data-wert="ja"' in seite, f"{name}: kein Ja"
        assert f'data-wahl="{name}" data-wert="nein"' in seite, f"{name}: kein Nein"
        assert f'id="{name}-inhalt" hidden' in seite, \
            f"{name}-inhalt fehlt oder startet sichtbar"


def test_nur_der_erste_schritt_ist_zu_beginn_sichtbar():
    """Die Kette baut sich auf - sie liegt nicht fertig da.

    Waeren alle Abschnitte von Anfang an sichtbar, waere es dieselbe lange
    Seite wie vorher, nur mit mehr Ueberschriften.
    """
    seite = (SITE / "index.html").read_text(encoding="utf-8")
    for name in SCHRITTE[1:]:
        assert re.search(rf'data-schritt="{name}"[^>]*\shidden', seite), \
            f"{name} ist von Anfang an sichtbar"
    assert not re.search(r'data-schritt="ort"[^>]*\shidden', seite), \
        "Schritt 1 ist versteckt - dann beginnt gar nichts"
    assert re.search(r'id="s-ergebnis"[^>]*\shidden', seite), \
        "Die Treffer stehen schon da, bevor gefragt wurde"
    assert re.search(r'id="karte-block"[^>]*\shidden', seite), \
        "Die Karte ist eingeblendet, obwohl sie nur auf Wunsch kommt"


def test_die_karte_kennt_den_bereich_statt_eines_umkreises():
    """Entfernung ist jetzt von-bis; die Karte zeichnet einen Ring.

    Ein einzelner Kreis wuerde eine untere Grenze verschweigen: Wer 300 bis
    600 km sucht, saehe einen Kreis um sich herum, der auch die naechsten
    300 km einschliesst.
    """
    karte = (SITE / "karte.js").read_text(encoding="utf-8")
    for handgriff in ("umkreisVon", "umkreisBis", "umkreisAktiv"):
        assert f"cfg.{handgriff}()" in karte, f"karte.js fragt {handgriff} nicht"
    app = (SITE / "app.js").read_text(encoding="utf-8")
    for handgriff in ("umkreisVon", "umkreisBis", "umkreisAktiv"):
        assert f"{handgriff}:" in app, f"app.js liefert {handgriff} nicht"


def test_die_sortierung_folgt_dem_filter():
    """Übereinstimmung, Entfernung, Preis, Datum — und die Vorgabe wandert mit.

    Die Vorgabe muss dem folgen, was eingestellt ist. Als sie in einem festen
    Wert steckte, stand dort vor der Bandauswahl „Datum"; kam danach eine Band
    dazu, blieb „Datum" stehen, weil es weiter erlaubt war — die Liste ordnete
    nach Termin, während die Prozentzahl danebenstand.
    """
    skript = (SITE / "app.js").read_text(encoding="utf-8")

    assert re.search(r"sortierung:\s*null", skript), \
        "die Sortierung startet mit einem festen Wert statt mit der Vorgabe"

    m = re.search(r"const sortierungen = \(\) => \{(.*?)\n  \};", skript, re.S)
    assert m, "sortierungen() nicht gefunden"
    reihenfolge = re.findall(r"'(match|distance|price|date)'", m.group(1))
    assert reihenfolge == ["match", "distance", "price", "date"], reihenfolge

    # Nur anbieten, was auch ordnen kann
    assert "if (gewichtet()) liste.push('match')" in skript
    assert "if (state.home) liste.push('distance')" in skript

    # Die eigene Wahl schlägt die Vorgabe, aber nur wenn es eine gibt
    assert "state.sortierung && erlaubt.includes(state.sortierung)" in skript


def test_die_karte_zoomt_nicht_ueber_die_erde_hinaus():
    """Jenseits der Pole rechnet die Projektion weiter - und zieht Schlieren.

    Der kleinste Zoom reichte bis 105.000 km halber Hoehe, das Fuenffache des
    Erddurchmessers. Sichtbar war das als wanderndes Streifenmuster, sobald
    der Massstabsbalken ueber 500 km sprang.
    """
    karte = (SITE / "karte.js").read_text(encoding="utf-8")
    assert "WELT_HALB_KM" in karte, "keine Obergrenze fuer den Ausschnitt"
    assert re.search(r"Math\.min\(WELT_HALB_KM,", karte), \
        "die Obergrenze wird nirgends angewandt"
    assert "mittelpunktImBild" in karte, "der Mittelpunkt wird nicht geklemmt"


def test_keine_steuerzeichen_in_ausgelieferten_dateien():
    """Ein Steuerzeichen im Quelltext sieht man nicht - es wirkt trotzdem.

    In app.js stand einmal eine Pruefung auf "EUR" mit zwei Rueckschritt-
    zeichen statt der Wortgrenzen, weil ein Patch die Backslashes gefressen
    hatte. Die Pruefung traf nie, und jeder Preis erschien doppelt.
    """
    erlaubt = set("\t\n\r")
    wurzel = SITE.parent
    kaputt = []
    for ordner, muster in ((SITE, "*.*"), (wurzel / "scraper", "*.py"),
                           (wurzel / "tests", "*.py")):
        for datei in sorted(ordner.glob(muster)):
            if datei.is_dir() or datei.suffix in (".gz", ".png", ".webmanifest"):
                continue
            try:
                inhalt = datei.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                kaputt.append(f"{datei.name}: nicht als UTF-8 lesbar")
                continue
            if inhalt.startswith("\ufeff"):
                kaputt.append(f"{datei.name}: beginnt mit einer Byte-Reihenfolge-Marke")
            for nr, zeile in enumerate(inhalt.splitlines(), 1):
                schlimm = {z for z in zeile if ord(z) < 32 and z not in erlaubt}
                if schlimm:
                    zeichen = ", ".join(f"U+{ord(z):04X}" for z in sorted(schlimm))
                    kaputt.append(f"{datei.name}:{nr}: {zeichen}")
    assert not kaputt, "Steuerzeichen gefunden:\n" + "\n".join(kaputt)
