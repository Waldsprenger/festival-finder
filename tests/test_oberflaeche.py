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


def test_umkreis_und_preis_filtern_nur_auf_wunsch():
    """Voreingestellt zeigt die Seite, was es gibt - nicht, was nahe liegt.

    Zwei von drei Festivals nennen keinen Preis, und ein Umkreis von 200 km
    verbirgt weltweit fast alles. Beides bleibt deshalb aus, bis jemand den
    Schalter umlegt.
    """
    seite = (SITE / "index.html").read_text(encoding="utf-8")
    skript = (SITE / "app.js").read_text(encoding="utf-8")
    for schalter, teil in (("radius-on", "radius-teil"), ("price-on", "price-teil")):
        marke = re.search(rf"<input type=\"checkbox\" id=\"{schalter}\"([^>]*)>", seite)
        assert marke, f"Schalter #{schalter} fehlt"
        assert "checked" not in marke.group(1), f"#{schalter} ist voreingestellt an"
        assert re.search(rf"id=\"{teil}\" hidden", seite), f"#{teil} startet sichtbar"
    assert "radiusAktiv: false" in skript
    assert "preisAktiv: false" in skript
    assert "state.home && state.radiusAktiv" in skript


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
