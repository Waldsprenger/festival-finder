"""Namen vereinheitlichen — damit dieselbe Band dieselbe Band bleibt.

Zwölf Quellen schreiben denselben Act auf ein Dutzend Arten: „2 Engel &
Charlie", „2 Engel and Charlie", „2 ENGEL &amp; CHARLIE". Hier stehen die
Schlüssel, über die sie zusammenfinden, und die Prüfung, die Bruchstücke aus
dem Fließtext von echten Bandnamen trennt.

Die Faltungsregeln stehen in `data/faltung.json`: Die Suche im Browser braucht
dieselben, und als beide Seiten eigene Tabellen pflegten, liefen sie
auseinander.

Die Schlüssel (`fold`, `festival_key`, `city_key`) sind die Kennung eines
Festivals über Läufe hinweg; Preisgeschichte und Neuzugänge hängen daran. Wer
an ihnen etwas ändert, ändert jede gespeicherte Kennung mit.
"""

import re
import unicodedata
from functools import lru_cache
from html import unescape

from ..pfade import DATA, lies_json

#: Zeichen, die man nicht sieht und die trotzdem stören: geschütztes und
#: schmales Leerzeichen, Nullbreiten-Zeichen, Schreibrichtungsmarken.
UNSICHTBAR = re.compile("[\xa0​-‏  ‪-‮﻿]")

#: Steuerzeichen, die in keinem Text vorkommen — wohl aber, wenn eine Seite in
#: Windows-1252 als ISO-8859-1 gelesen wurde: „Nata\x9aa" statt „Nataša".
_STEUERZEICHEN = re.compile("[\x80-\x9f]")
_LEERRAUM = re.compile(r"\s+")


def _windows_1252(treffer: re.Match) -> str:
    """Das Zeichen, das ein Browser an dieser Stelle zeigt."""
    try:
        return treffer.group().encode("latin-1").decode("cp1252")
    except UnicodeDecodeError:
        return ""                        # fünf Stellen sind auch dort unbelegt


def clean(text: str | None) -> str:
    """Ein Name in einer Zeile: entschlüsselt, ohne unsichtbare Zeichen.

    Entschlüsselt heißt: HTML-Ersatzschreibweisen aufgelöst („Larry &amp; Joe"
    — im JSON-Datenblatt nimmt sie einem kein Parser ab) und Zeichensalat aus
    Windows-1252 so gelesen, wie ein Browser ihn zeigt.
    """
    if not text:
        return ""
    text = _STEUERZEICHEN.sub(_windows_1252, unescape(text))
    return _LEERRAUM.sub(" ", UNSICHTBAR.sub(" ", text)).strip()


def feld(wert) -> str:
    """Ein Textfeld aus einem Datenblatt — null heißt leer, nicht „None".

    `str(d.get("k", ""))` greift nicht, wenn der Schlüssel mit null dasteht:
    Dann entsteht die Zeichenkette „None" — bei 2.490 Festivals als Ortsname.
    """
    return clean("" if wert is None else str(wert))


# --------------------------------------------------------------------------
# Faltung
# --------------------------------------------------------------------------

_ROH = lies_json(DATA / "faltung.json", {}) or {}
REGELN = {k: _ROH.get(k, []) for k in ("sonderzeichen", "ersatz", "verbinder",
                                        "artikel", "zusatz")}

_SONDERZEICHEN = [tuple(p) for p in REGELN["sonderzeichen"]]
_ERSATZ = [tuple(p) for p in REGELN["ersatz"]]
_VERBINDER = re.compile(r"\b(" + "|".join(REGELN["verbinder"]) + r")\b")
_ARTIKEL = re.compile(r"^(" + "|".join(REGELN["artikel"]) + r")\s+")
_ZUSATZ = re.compile(r"\s+(" + "|".join(REGELN["zusatz"]) + r")$")
_KEIN_WORT = re.compile(r"[\W_]+")

#: So viele Schlüssel merken sich `fold`, `festival_key` und `city_key`. Beim
#: Zusammenführen fällt `fold` 1,2 Millionen Mal an, für 126.000 verschiedene
#: Namen. Mehr Platz brächte nichts: Beim Bauen faltet das Ortsverzeichnis
#: 260.000 Namen je einmal, die würden den Speicher nur füllen.
GEDAECHTNIS = 1 << 17


@lru_cache(maxsize=GEDAECHTNIS)
def fold(value: str) -> str:
    """Aggressiver Schlüssel für den Namensvergleich.

    Buchstaben aller Schriften bleiben stehen: Ein früheres `[^a-z0-9]` ließ
    von „Мумий Тролль" nichts übrig, und „Ελλάδα Band" fiel mit jeder anderen
    so verkürzten Band zusammen.
    """
    v = unicodedata.normalize("NFKD", clean(value).lower())
    v = "".join(c for c in v if not unicodedata.combining(c))
    for a, b in _SONDERZEICHEN:
        v = v.replace(a, b)
    for a, b in _ERSATZ:
        v = v.replace(a, b)
    v = _VERBINDER.sub(" and ", v)
    v = _LEERRAUM.sub(" ", _KEIN_WORT.sub(" ", v)).strip()
    v = _ZUSATZ.sub("", _ARTIKEL.sub("", v))
    return v.strip()


def _zusammen(gefaltet: str) -> str:
    """Getrennt- und Zusammenschreibung meinen dieselbe Band („1000 Mods" und
    „1000mods") — außer bei kurzen Namen, wo „B-One" und „Bone" zwei sind."""
    eng_ = gefaltet.replace(" ", "")
    return eng_ if len(eng_) >= 5 else gefaltet


class Kuerzel:
    """Die Tabelle der Bandkürzel — ein Objekt, weil sie sich im Lauf ändert.

    `bund.bandnamen.kollisionen` schaltet Kürzel ab, die in diesem Bestand eine
    andere Band meinen: „LP" ist die Sängerin, nicht Linkin Park.
    """

    def __init__(self, roh: dict[str, str] | None = None):
        if roh is None:
            roh = lies_json(DATA / "band_aliase.json", {}) or {}
        #: gefaltetes Kürzel → ausgeschriebener Name
        self.nach_kuerzel = {fold(k): v for k, v in roh.items()}
        #: Bandschlüssel → hinterlegte Schreibweise
        self.nach_schluessel = {_zusammen(fold(v)): v for v in roh.values()}

    def abschalten(self, kurz: str) -> None:
        """Dieses Kürzel gilt nicht mehr als Abkürzung."""
        self.nach_kuerzel.pop(kurz, None)

    def band_key(self, name: str) -> str:
        """Schlüssel einer Band; hinterlegte Kürzel lösen sich dabei auf."""
        k = fold(name)
        ziel = self.nach_kuerzel.get(k)
        return _zusammen(fold(ziel) if ziel else k)


#: Die Tabelle des gewöhnlichen Laufs. Wer sie verändert, tut das an einem
#: Objekt, das er selbst gebaut hat — nicht an diesem.
KUERZEL = Kuerzel()


def band_key(name: str) -> str:
    """Bandschlüssel nach der Standardtabelle."""
    return KUERZEL.band_key(name)


# --------------------------------------------------------------------------
# Festival- und Ortsschlüssel
# --------------------------------------------------------------------------

#: Namen, die keine Regel zusammenbringt: Übersetzungen („Carnival of Cultures"
#: für den „Karneval der Kulturen") und Tippfehler genau im Kernwort. Die Liste
#: steht in `data/festival_aliase.json` und wächst ohne Codeänderung.
FESTIVAL_ALIAS = {fold(variante): richtig for variante, richtig
                  in (lies_json(DATA / "festival_aliase.json", {}) or {}).items()}

_JAHR = re.compile(r"\b(19|20)\d{2}\b")
_FESTIVALWORT = re.compile(r"\b(festival|fest|open air|openair|open|air)\b")
# Angehängt und zusammengeschrieben meint dasselbe („Reloadfestival"). Der
# Rumpf behält vier Zeichen, sonst würde aus „Festa" ein leerer Schlüssel.
_ANGEHAENGT = re.compile(r"(?<=\w{4})(festival|openair|fest)\b")
_VORANGESTELLT = re.compile(r"\b(festival|openair)(?=\w{4})")
_PLZ = re.compile(r"\b\d{4,6}\b")


def festival_name(name: str) -> str:
    """Die verbindliche Schreibweise eines Festivals."""
    return FESTIVAL_ALIAS.get(fold(name), name)


@lru_cache(maxsize=GEDAECHTNIS)
def festival_key(name: str) -> str:
    """Schlüssel eines Festivals: ohne Artikel, Jahr und Festival/Open Air."""
    v = _FESTIVALWORT.sub(" ", _JAHR.sub(" ", fold(name)))
    v = _VORANGESTELLT.sub(" ", _ANGEHAENGT.sub(" ", v))
    return _LEERRAUM.sub(" ", v).strip() or fold(name)


def eng(name: str) -> str:
    """Festivalschlüssel ohne Leerzeichen."""
    return festival_key(name).replace(" ", "")


@lru_cache(maxsize=GEDAECHTNIS)
def city_key(value: str) -> str:
    """Ortsschlüssel ohne Postleitzahl."""
    return fold(_PLZ.sub(" ", value or ""))


# --------------------------------------------------------------------------
# Bandnamen
# --------------------------------------------------------------------------

_FUELLWORT = re.compile(
    r"^(uvm|u\.v\.m\.|und viele mehr|und weitere|and more|alle artists|t\.b\.a\.?|"
    r"tba|mehr|close|line ?-?up|weitere|special guest[s]?|support|n/a|-{1,3})$", re.I)

#: „26. 7.2026" oder „04.07.2026 Auch der zweite Festivaltag"
_DATUM_VORNE = re.compile(r"^\d{1,2}\.\s?\d{1,2}\.\d{2,4}\b")

# Reste aus Beschreibungs- und Preisfeldern. Die Beschriftungen brauchen ihren
# Doppelpunkt: zwischen „Kategorie:" und dem Leerzeichen danach liegt keine
# Wortgrenze, „\bKategorie:\b" traf deshalb nie.
_FELDREST = re.compile(r"\b(?:VVK|AK|Camping|Rahmenprogramm|"
                       r"zum kompletten Programm)\b"
                       r"|\b(?:Kategorie|Preis|Besucher|Stil|Location)\s*:", re.I)
_SATZWORT = re.compile(r"\b(?:ist|sind|wird|werden|findet|treffen|startet|sorgen|"
                       r"bestätigt|außerdem)\b", re.I)
_BUCHSTABE = re.compile(r"[^\W_]")


def valid_band(name: str) -> bool:
    """Ist das ein Bandname — oder ein Bruchstück aus dem Fließtext?"""
    n = clean(name)
    if not 2 <= len(n) <= 90:
        return False
    if _FUELLWORT.match(n) or _DATUM_VORNE.match(n) or _FELDREST.search(n):
        return False
    # Ein Buchstabe irgendeiner Schrift genügt („Мумий Тролль")
    if not _BUCHSTABE.search(n):
        return False
    # Satzwörter erst ab sechs Wörtern: „Werden Wir Uns Wiedersehen" ist eine Band
    return not (len(n.split()) >= 6 and _SATZWORT.search(n))


def canonical_band(varianten: list[str]) -> str:
    """Die häufigste, bei Gleichstand die längste und sauberste Schreibweise."""
    zaehler: dict[str, int] = {}
    for v in varianten:
        zaehler[v] = zaehler.get(v, 0) + 1

    def rang(eintrag):
        name, anzahl = eintrag
        # Großbuchstabe am Anfang zuerst: sonst gewänne bei Akronymen wie
        # B.O.S.C.H. die durchgehend kleingeschriebene Variante.
        return (anzahl, name[:1].isupper(),
                name != name.lower() and name != name.upper(),
                -name.count("."), len(name))

    return max(zaehler.items(), key=rang)[0]


# --------------------------------------------------------------------------
# Einzelne Felder
# --------------------------------------------------------------------------

_ZAHLENGRUPPE = re.compile(r"\d[\d.\s']*\d|\d")
_KEINE_ZIFFER = re.compile(r"\D")


def besucherzahl(roh: str) -> str:
    """Eine Besucherzahl — oder gar keine, wenn der Text mehrere Zahlen nennt.

    Früher blieben alle Ziffern des Textes übrig; auf Seiten, deren Muster ins
    Leere griff, ergab das Zahlen mit 66 Stellen aus Datumsangaben.
    """
    text = clean(roh)
    zahlen = [z for z in (_KEINE_ZIFFER.sub("", t) for t in _ZAHLENGRUPPE.findall(text)) if z]
    if len(zahlen) != 1:
        return ""
    wert = int(zahlen[0])
    return str(wert) if 10 <= wert <= 5_000_000 else ""


#: Wonach eine Spielstätte aussieht, wenn die Seite keine nennt: der nächste
#: Knopf („Tickets Ticket" stand so auf acht Karten).
KNOPFBESCHRIFTUNG = re.compile(
    r"(?i)^(?:tickets?\b|get |buy |mehr\b|more |website\b|infos?\b|hier\b)")

#: Postleitzahl vor dem Ortsnamen, in den Schreibweisen der Quellen. Die
#: Reihenfolge zählt: „1012 AB Amsterdam" muss als niederländischer Code
#: gelesen werden, bevor „1012" allein passt.
PLZ_VORN = re.compile(
    r"^(?:[A-Z]{1,2}-)?("                        # „CA-92201 Indio", „D-97209"
    r"\d{4}\s?[A-Z]{2}(?=\s)"                    # NL: „1012 AB Amsterdam"
    r"|\d{4}-\d{3}"                              # PT: „6060-133 Idanha-a-Nova"
    r"|\d{2}-\d{3}"                              # PL: „80-873 Gdansk"
    r"|[A-Z]{1,2}\d{1,2}[A-Z]?(?:\s\d[A-Z]{2})?" # GB: „BN2 Brighton", „M17 1AB …"
    r"|\d{3,5}(?:\s?\d{2})?"                     # „97209 …", „104 45 Athen"
    r")\s+(?=[^\W\d_])")


def plz_und_stadt(stadt: str, plz: str) -> tuple[str, str]:
    """Steht die Postleitzahl im Ortsfeld, gehört sie ins Postleitzahlfeld.

    Sonst heißt der Ort „BN2 Brighton" oder „80-873 Gdansk", und weder das
    Ortsverzeichnis noch Nominatim finden ihn.
    """
    ort = clean(stadt)
    treffer = PLZ_VORN.match(ort)
    if not treffer:
        return ort, clean(plz)
    return ort[treffer.end():].strip(), clean(plz) or treffer[1].replace(" ", "")


def genres_vereinen(*werte: str) -> str:
    """Genres mehrerer Quellen sammeln; doppelte Angaben fallen weg.

    Die Vereinigung ist näher an der Wahrheit als jede Quelle allein: Bei
    „Rock im Park" nennt festivalsunited „genreübergreifend", festival-alarm
    acht konkrete Richtungen.
    """
    gesehen: dict[str, str] = {}
    for wert in werte:
        for teil in (wert or "").split(","):
            if (teil := clean(teil)):
                gesehen.setdefault(teil.casefold(), teil)
    return ", ".join(gesehen.values())
