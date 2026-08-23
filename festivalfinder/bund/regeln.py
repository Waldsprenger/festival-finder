"""Wann meinen zwei Einträge dasselbe Fest?

Jede dieser Fragen ist eine eigene Entscheidung mit einem eigenen
Gegenbeispiel. Sie stehen deshalb einzeln da und nicht als Bedingungen mitten
in den Stufen — dort wären sie nicht zu prüfen und nicht zu erklären.
"""

import difflib
import re
from urllib.parse import urlparse

from ..kern.orte import land_code
from ..kern.text import city_key, eng, festival_key, fold

#: Eine vorangestellte Ausgabenummer: „37. Fränkische Musiktage", „30th Denton"
ORDNUNGSZAHL = re.compile(r"^\d+\s*(?:th|st|nd|rd)?\s+")

#: Deutsche Umlaute schreiben die Quellen mal so, mal so. „Glücksgefühle"
#: wird zu „glucksgefuhle", „Gluecksgefuehle" zu „gluecksgefuehle" — zwei
#: Schlüssel für ein Fest. Zusammengezogen treffen sie sich wieder.
UMSCHRIFT = re.compile(r"ue|oe|ae|ss")


def kernname(name: str, ort: str = "") -> str:
    """Der Namenskern: ohne das, was zwei Quellen verschieden handhaben.

    Weg fallen die Ausgabenummer („37."), der Ort im Namen („Fränkische
    Musiktage Alzenau"), das Land („Time Warp Germany") und der Unterschied
    zwischen „ü" und „ue". Übrig bleibt, was die Veranstaltung ausmacht.

    Der Ort wird mitgegeben, weil er nur dann wegfallen darf, wenn er auch der
    Ort des Festivals ist: „Rock am Ring" verlöre sonst seinen Ring.

    Nur ausgeschriebene Ländernamen fallen weg, keine Kürzel: `land_code("am")`
    ergibt AM für Armenien, und „Rock am Ring" wurde damit zu „Rock Ring".
    Und bleibt am Ende zu wenig übrig, gilt der volle Schlüssel — „Festival de
    Chile" darf nicht auf „de" zusammenschrumpfen.
    """
    schluessel = ORDNUNGSZAHL.sub("", festival_key(name))
    ortsworte = set(city_key(ort).split())
    behalten = [w for w in schluessel.split()
                if w not in ortsworte and not (len(w) > 2 and len(land_code(w)) == 2)]
    kern = "".join(behalten)
    if len(kern) < 4:
        kern = "".join(schluessel.split())
    return UMSCHRIFT.sub(lambda m: m.group()[0], kern)


def dieselbe_veranstaltung(a: str, b: str, ort: str = "") -> bool:
    """Zwei Namen, ein Fest — sofern Ort und Termin es schon bestätigt haben.

    Diese Frage stellt sich erst, wenn zwei Einträge am selben Ort zur selben
    Zeit stehen. Dann ist ein Unterschied in Ausgabenummer, Ortsnamen,
    Landesnamen oder Umlautschreibung kein Unterschied mehr.

    Nicht darunter fällt ein zusätzliches Wort mit eigener Bedeutung: „Gay
    Pride Festival" und „Hunkering Gay Pride Festival" stehen am selben Tag in
    Amsterdam und sind zwei Veranstaltungen.
    """
    if not zahlen_passen(a, b):
        return False
    ka, kb = kernname(a, ort), kernname(b, ort)
    return bool(ka) and ka == kb


def name_steckt_drin(a: str, b: str) -> bool:
    """Steckt der eine Name vollständig im anderen?

    Für terminlose Einträge, die oft die Übersichtsseite eines Festes sind und
    dann einen Zusatz tragen: „BigCityBeats World Club Dome" gegen „World Club
    Dome", „Rock the Ocean's Tortuga Music Festival" gegen „Tortuga Music
    Festival".

    Der kürzere Name braucht zwei Wörter. Bei einem genügte ein angehängtes
    Wort für einen Treffer, und „Awakenings Upclose" ist eine eigene Reihe,
    nicht die Übersichtsseite von „Awakenings".
    """
    if not zahlen_passen(a, b):
        return False
    ta, tb = festival_key(a).split(), festival_key(b).split()
    kurz, lang = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return len(kurz) >= 2 and set(kurz) < set(lang)


def ort_deckt_sich(a: str, b: str) -> bool:
    """Steckt der eine Ortsname im anderen?

    Die Quellen füllen das Ortsfeld unterschiedlich genau. Mal steht die
    Gemeinde vorn („Oberndorf am Neckar" gegen „Oberndorf"), mal hinten
    („Stemwede-Wehdem" gegen „Wehdem"), mal steht die Spielstätte davor
    („Kulturpark Deutzen" gegen „Deutzen"). Alle drei meinen denselben Ort.
    Ein bloßer Wortanfang genügt dagegen nicht — „Kiel" und „Kieler Bucht"
    sind nicht dasselbe.
    """
    if not (a and b):
        return False
    return (a == b or a.startswith(b + " ") or b.startswith(a + " ")
            or a.endswith(" " + b) or b.endswith(" " + a))


def name_deckt_sich(ka: str, kb: str) -> bool:
    """Strenger Namensvergleich für Termine, die nicht am selben Tag beginnen.

    Ein gemeinsames Wort genügt hier nicht: „METAStadt Open Air Wien" und
    „Afrika Tage Wien" teilen sich die Stadt im Namen und sind zwei
    Veranstaltungen. Verlangt wird, dass ein Name vollständig im anderen steckt
    („Neuborn" in „NOAF Neuborn") oder beide ohne Leerzeichen gleich sind
    („R.O.I. Rock On Isens" und „ROI Rock On Isens").
    """
    ta, tb = set(ka.split()), set(kb.split())
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    return ka.replace(" ", "") == kb.replace(" ", "")


def zahlen_passen(a: str, b: str) -> bool:
    """Nennen beide Namen Zahlen — und dann dieselben?

    Eine Ziffer ist selten Zierrat. „ИОНОСФЕРА №15" und „ИОНОСФЕРА №24" sind
    zwei Abende einer Reihe, „Total Music Meeting '91" und „'96" zwei
    Jahrgänge; als Zeichenketten sind sie zu 90 % gleich und fielen sonst
    zusammen. Nennt nur einer eine Zahl, sagt das nichts: „Wacken Open Air
    2026" und „Wacken Open Air" sind dasselbe.
    """
    za, zb = re.findall(r"\d+", a), re.findall(r"\d+", b)
    return not (za and zb) or za == zb


def schreibweise_gleich(a: str, b: str) -> bool:
    """Meinen zwei Namen dasselbe, nur anders geschrieben?

    „Sonne Mond Sterne" und „SonneMondSterne", „Kunst!Rasen" und „Kunstrasen
    Bonn", „Sziget" und „Szigit" — Leerzeichen, Satzzeichen und Tippfehler
    trennen sonst Einträge, die zusammengehören.

    Zweimal verglichen: einmal der Schlüssel, einmal der volle Name. Beim
    „Soerdfest" gegen „Sørdfest" bleibt vom Schlüssel nur „soerd" und „sord"
    übrig — zu kurz für einen belastbaren Vergleich, während die vollen Namen
    zu 97 % übereinstimmen.
    """
    if not zahlen_passen(a, b):
        return False
    return _aehnlich(eng(a), eng(b)) or _aehnlich(fold(a).replace(" ", ""),
                                                  fold(b).replace(" ", ""))


def _aehnlich(x: str, y: str) -> bool:
    """Ein Rumpf von sechs Zeichen schützt kurze Namen wie „Wutz"."""
    if len(x) < 6 or len(y) < 6:
        return False
    if x == y or x.startswith(y) or y.startswith(x):
        return True
    return difflib.SequenceMatcher(None, x, y).ratio() >= 0.82


def namen_verwandt(a: str, b: str) -> bool:
    """Steckt ein Name im anderen — oder sind es zwei Schreibweisen desselben?"""
    fa, fb = fold(a), fold(b)
    if len(fa) >= 5 and len(fb) >= 5 and (fa in fb or fb in fa):
        return True
    return schreibweise_gleich(a, b)


def adresse(url: str) -> str:
    """Der Rechnername einer Adresse, ohne www und Schrägstrich.

    „https://www.Kosmosfestival.fi/" und „http://kosmosfestival.fi" sind
    dieselbe Seite — und damit dasselbe Fest.
    """
    wirt = urlparse((url or "").strip().lower()).netloc
    return wirt[4:] if wirt.startswith("www.") else wirt
