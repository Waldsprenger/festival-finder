"""Wann meinen zwei Einträge dasselbe Fest?

Jede dieser Fragen ist eine eigene Entscheidung mit einem eigenen
Gegenbeispiel. Sie stehen deshalb einzeln da und nicht als Bedingungen mitten
in den Stufen — dort wären sie nicht zu prüfen und nicht zu erklären.
"""

import difflib
from urllib.parse import urlparse

from ..kern.text import eng, fold


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
