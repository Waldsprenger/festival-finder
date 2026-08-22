"""Namen vereinheitlichen — damit dieselbe Band dieselbe Band bleibt.

Zwölf Quellen schreiben denselben Act auf ein Dutzend Arten: „2 Engel &
Charlie", „2 Engel and Charlie", „2 ENGEL &amp; CHARLIE". Hier stehen die
Schlüssel, über die sie zusammenfinden, und die Prüfung, die Bruchstücke aus
dem Fließtext von echten Bandnamen trennt.

Die Faltungsregeln selbst stehen in `data/faltung.json`: Die Suche im Browser
braucht dieselben, und als beide Seiten ihre eigene Tabelle pflegten, sind sie
auseinandergelaufen.
"""

import re
import unicodedata
from html import unescape

from ..pfade import DATA, lies_json

#: Zeichen, die man nicht sieht und die trotzdem stören: geschütztes und
#: schmales Leerzeichen, Nullbreiten-Zeichen, Schreibrichtungsmarken.
UNSICHTBAR = re.compile("[\xa0\u200b-\u200f\u2028\u2029\u202a-\u202e\ufeff]")


def clean(text: str | None) -> str:
    """Ein Name in einer Zeile: entschlüsselt, ohne unsichtbare Zeichen.

    Entschlüsselt heißt: HTML-Ersatzschreibweisen werden aufgelöst.
    Datenblätter aus WordPress liefern sie mit — „Shaq&#8217;s Fun House" und
    „Larry &amp; Joe" standen so auf 236 Karten. Im HTML-Fließtext nimmt der
    Parser sie einem ab, im JSON-Datenblatt nicht.
    """
    if not text:
        return ""
    return re.sub(r"\s+", " ", UNSICHTBAR.sub(" ", unescape(text))).strip()


# --------------------------------------------------------------------------
# Faltung
# --------------------------------------------------------------------------

def _regeln() -> dict:
    roh = lies_json(DATA / "faltung.json", {}) or {}
    return {feld: roh.get(feld, []) for feld in
            ("sonderzeichen", "ersatz", "verbinder", "artikel", "zusatz")}


REGELN = _regeln()

_SONDERZEICHEN = [tuple(p) for p in REGELN["sonderzeichen"]]
_ERSATZ = [tuple(p) for p in REGELN["ersatz"]]
_VERBINDER = re.compile(r"\b(" + "|".join(REGELN["verbinder"]) + r")\b")
_ARTIKEL = re.compile(r"^(" + "|".join(REGELN["artikel"]) + r")\s+")
_ZUSATZ = re.compile(r"\s+(" + "|".join(REGELN["zusatz"]) + r")$")


def fold(value: str) -> str:
    """Aggressiver Schlüssel für den Namensvergleich.

    Beginnt mit `clean()`: Ohne das wäre „Larry &amp; Joe" ein anderer Act als
    „Larry & Joe" — der Schlüssel sähe die Ersatzschreibweise als Wort.

    Buchstaben aller Schriften bleiben stehen. Ein früheres `[^a-z0-9]` ließ
    von „Мумий Тролль" nichts übrig — der Act galt damit als namenlos und fiel
    aus jedem Lineup; „Ελλάδα Band" schrumpfte auf „band" und wäre mit jeder
    anderen so verkürzten Band zusammengefallen.
    """
    v = unicodedata.normalize("NFKD", clean(value).lower())
    v = "".join(c for c in v if not unicodedata.combining(c))
    for a, b in _SONDERZEICHEN:
        v = v.replace(a, b)
    for a, b in _ERSATZ:
        v = v.replace(a, b)
    v = _VERBINDER.sub(" and ", v)
    v = re.sub(r"[\W_]+", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    v = _ARTIKEL.sub("", v)
    v = _ZUSATZ.sub("", v)
    return v.strip()


def _zusammen(gefaltet: str) -> str:
    """Getrennt- und Zusammenschreibung meinen dieselbe Band.

    „1000 Mods" und „1000mods" gehören zusammen. Bei kurzen Namen bleibt die
    Trennung erhalten, weil dort verschiedene Acts zusammenfielen („B-One" und
    „Bone").
    """
    eng = gefaltet.replace(" ", "")
    return eng if len(eng) >= 5 else gefaltet


# --------------------------------------------------------------------------
# Kürzel
# --------------------------------------------------------------------------

class Kuerzel:
    """Die Tabelle der Bandkürzel — ein Objekt, weil sie sich unterwegs ändert.

    `bund.bandnamen.kollisionen` schaltet Kürzel ab, die eine andere Band
    meinen: „LP" steht für die Sängerin, nicht für Linkin Park. Früher war das
    eine Änderung an einem Modulwörterbuch, und jeder Test musste sie
    zurücknehmen — sonst hing sein Ergebnis davon ab, welcher vorher lief.
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
# Schlüssel
# --------------------------------------------------------------------------

#: Namen, die keine Regel zusammenbringt — siehe `festival_name`
FESTIVAL_ALIAS = {fold(variante): richtig for variante, richtig
                  in (lies_json(DATA / "festival_aliase.json", {}) or {}).items()}


def festival_name(name: str) -> str:
    """Die verbindliche Schreibweise eines Festivals.

    Manche Quellen übersetzen den Namen („Carnival of Cultures" für den
    Berliner „Karneval der Kulturen") oder verschreiben sich in genau dem Wort,
    das den Namen ausmacht („Die Schagernacht München"). Kein Vergleich von
    Buchstaben findet das — deshalb eine kurze Liste in
    `data/festival_aliase.json`, die sich ohne Codeänderung erweitern lässt.
    """
    return FESTIVAL_ALIAS.get(fold(name), name)


def festival_key(name: str) -> str:
    """Schlüssel eines Festivals: ohne Artikel, Jahr und Festival/Open Air."""
    v = fold(name)
    v = re.sub(r"\b(19|20)\d{2}\b", " ", v)
    v = re.sub(r"\b(festival|fest|open air|openair|open|air)\b", " ", v)
    # Angehängt und zusammengeschrieben meint dasselbe: „Reloadfestival" stand
    # als eigener Eintrag neben „Reload Festival", weil nur das freistehende
    # Wort wegfiel. Der Rumpf muss dabei vier Zeichen behalten, sonst würde aus
    # „Festa" ein leerer Schlüssel.
    v = re.sub(r"(?<=\w{4})(festival|openair|fest)\b", " ", v)
    v = re.sub(r"\b(festival|openair)(?=\w{4})", " ", v)
    return re.sub(r"\s+", " ", v).strip() or fold(name)


def eng(name: str) -> str:
    """Festivalschlüssel ohne Leerzeichen."""
    return festival_key(name).replace(" ", "")


def city_key(value: str) -> str:
    """Ortsschlüssel ohne Postleitzahl."""
    return fold(re.sub(r"\b\d{4,6}\b", " ", value or ""))


# --------------------------------------------------------------------------
# Bandnamen
# --------------------------------------------------------------------------

_FUELLWORT = re.compile(
    r"^(uvm|u\.v\.m\.|und viele mehr|alle artists|t\.b\.a\.?|tba|mehr|close|"
    r"line ?-?up|weitere|special guest[s]?|support|n/a|-{1,3})$", re.I)

#: „26. 7.2026" oder „04.07.2026 Auch der zweite Festivaltag"
_DATUM_VORNE = re.compile(r"^\d{1,2}\.\s?\d{1,2}\.\d{2,4}\b")

# Reste aus Beschreibungs- und Preisfeldern. Die Beschriftungen brauchen ihren
# Doppelpunkt: „\bKategorie:\b" traf nie, weil dahinter ein Leerzeichen steht
# und zwischen zwei Satzzeichen keine Wortgrenze liegt.
_FELDREST = re.compile(r"\b(?:VVK|AK|Camping|Rahmenprogramm|"
                       r"zum kompletten Programm)\b"
                       r"|\b(?:Kategorie|Preis|Besucher|Stil|Location)\s*:", re.I)
_SATZWORT = re.compile(r"\b(?:ist|sind|wird|werden|findet|treffen|startet|sorgen|"
                       r"bestätigt|außerdem)\b", re.I)


def valid_band(name: str) -> bool:
    """Ist das ein Bandname — oder ein Bruchstück aus dem Fließtext?"""
    n = clean(name)
    if len(n) < 2 or len(n) > 90:
        return False
    if _FUELLWORT.match(n) or _DATUM_VORNE.match(n) or _FELDREST.search(n):
        return False
    # Ein Buchstabe irgendeiner Schrift genügt: Vorher war nur das lateinische
    # Alphabet gemeint, und „Мумий Тролль" galt deshalb nicht als Bandname.
    if not re.search(r"[^\W_]", n):
        return False
    # Satzwörter erst ab einer Länge prüfen, die kein Bandname mehr hat —
    # „Werden Wir Uns Wiedersehen" soll nicht durchfallen.
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

def besucherzahl(roh: str) -> str:
    """Eine Besucherzahl — oder gar keine, wenn der Text mehrere Zahlen nennt.

    Früher blieben schlicht alle Ziffern des Textes übrig. Auf Seiten, deren
    Muster ins Leere griff, ergab das Zahlen mit 66 Stellen, zusammengeklebt
    aus Datumsangaben. Eine unklare Angabe ist kein Wissen: Dann lieber nichts.
    """
    text = clean(roh)
    if not text:
        return ""
    zahlen = [z for z in (re.sub(r"\D", "", t) for t in
                          re.findall(r"\d[\d.\s']*\d|\d", text)) if z]
    if len(zahlen) != 1:
        return ""
    wert = int(zahlen[0])
    # Unter zehn ist keine Besucherzahl, über fünf Millionen auch nicht.
    return str(wert) if 10 <= wert <= 5_000_000 else ""


#: Wonach eine Spielstätte aussieht, wenn die Seite gar keine nennt: Dann steht
#: dort der nächste Knopf („Tickets Ticket" stand so auf acht Karten).
KNOPFBESCHRIFTUNG = re.compile(
    r"(?i)^(?:tickets?\b|get |buy |mehr\b|more |website\b|infos?\b|hier\b)")

#: „104 45 Athen", „170 00 Prague" — Postleitzahl vor dem Ortsnamen
PLZ_VORN = re.compile(r"^(\d{3,5}(?:\s?\d{2})?)\s+(?=\D)")


def plz_und_stadt(stadt: str, plz: str) -> tuple[str, str]:
    """Steht die Postleitzahl im Ortsfeld, gehört sie ins Postleitzahlfeld.

    Sonst heißt der Ort „104 45 Athen", die Karte findet ihn nicht, und auf der
    Karte steht die Nummer mit.
    """
    ort = clean(stadt)
    treffer = PLZ_VORN.match(ort)
    if not treffer:
        return ort, clean(plz)
    return ort[treffer.end():].strip(), clean(plz) or treffer[1].replace(" ", "")


def genres_vereinen(*werte: str) -> str:
    """Genres mehrerer Quellen sammeln; doppelte Angaben fallen weg.

    Früher gewann die erste gefüllte Quelle und die übrigen verfielen. Bei
    „Rock im Park" blieb so das festivalsunited-Wort „genreübergreifendes"
    stehen, während festival-alarm acht konkrete Richtungen nennt. Die
    Vereinigung ist näher an der Wahrheit als jede Quelle allein.
    """
    gesehen: dict[str, str] = {}
    for wert in werte:
        for teil in (wert or "").split(","):
            teil = clean(teil)
            if teil:
                gesehen.setdefault(teil.casefold(), teil)
    return ", ".join(gesehen.values())
