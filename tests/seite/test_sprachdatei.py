"""Die Sprachdatei: Ein Tippfehler nimmt die ganze Seite mit.

Ein einziges nicht geschütztes Apostroph in einer Zeichenkette („Avrupa'nın")
beendet sie mitten im Satz — der Browser bricht die Datei ab, und statt der
Oberfläche stehen die Schlüsselnamen auf der Seite. Python kann kein JavaScript
ausführen, wohl aber die Form prüfen: Was hier nicht als Zeichenkette
durchgeht, geht auch dort nicht durch.
"""

import re

from festivalfinder.pfade import SITE

JS = SITE / "js"
I18N = (JS / "i18n.js").read_text(encoding="utf-8")

#: 'so' oder "so", geschützte Zeichen eingeschlossen
KETTE = r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\""
#: de: 'Text' — Sprachkürzel und Wert
EINTRAG = re.compile(rf"\b([a-z]{{2}}):\s*({KETTE})")
#: 'app.tagline': { — Beginn eines Textblocks
BEGINN = re.compile(rf"^\s*({KETTE}):\s*\{{")

#: Alle Skripte der Seite, in der Reihenfolge aus index.html
SEITE = (SITE / "index.html").read_text(encoding="utf-8")
SKRIPTE = re.findall(r'<script[^>]+src="([^"]+)"', SEITE)


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
    """Die Tabelle TEXTE als Wörterbuch: Schlüssel → Sprache → Text."""
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


def quelltexte() -> dict[str, str]:
    """Alle Skripte der Seite plus index.html, nach Namen."""
    dateien = {"index.html": SEITE}
    for pfad in SKRIPTE:
        datei = SITE / pfad
        if datei.exists():
            dateien[pfad] = datei.read_text(encoding="utf-8")
    return dateien


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
    for name, inhalt in quelltexte().items():
        for s in re.findall(r"\bt\(\s*'([\w.]+)'", inhalt):
            # t('genre.' + key) wird erst zur Laufzeit vollständig
            if not s.endswith(".") and s not in vorhanden:
                fehlt.add(f"{name}: {s}")
    assert not fehlt, f"unbekannte Textschlüssel: {fehlt}"


def test_auch_die_umwegigen_schluessel_gibt_es():
    """Nicht jeder Schlüssel steht direkt in t() — manche über eine Variable.

    Die Kartenbeschriftung wählt ihren Schlüssel je nach Zahl der Pins aus drei
    Möglichkeiten aus; keine davon fände die Prüfung darüber.
    """
    vorhanden = set(texte())
    raeume = {s.split(".", 1)[0] for s in vorhanden}
    fehlt = set()
    for name, inhalt in quelltexte().items():
        for s in re.findall(r"'([a-z][A-Za-z0-9]*\.[A-Za-z0-9.]+)'", inhalt):
            if s.split(".", 1)[0] in raeume and s not in vorhanden:
                fehlt.add(f"{name}: {s}")
    assert not fehlt, f"unbekannte Textschlüssel: {fehlt}"


def test_keine_verwaisten_texte():
    """Ein Text, den niemand ruft, ist Ballast — und beim Übersetzen Arbeit."""
    alles = "\n".join(quelltexte().values())
    verwaist = sorted(k for k in texte()
                      if f"'{k}'" not in alles
                      # t('genre.' + key) und t('sort.' + key) sind Familien
                      and not re.match(r"^(genre|sort)\.", k))
    assert not verwaist, f"nirgends verwendet: {verwaist}"
