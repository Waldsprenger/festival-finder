"""Wo was liegt — und wie geschrieben wird, ohne dass etwas halb bleibt.

Bewusst ohne Fremdpakete und ohne Wissen über Festivals: Auch die Werkzeuge,
die nur Symbole zeichnen oder Kartengrenzen vereinfachen, binden dieses Modul
ein. Sie sollen dafür weder `requests` noch `beautifulsoup4` brauchen.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

#: Wurzel des Projekts (festivalfinder/pfade.py → zwei Ebenen hoch)
BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "cache"
DATA = BASE / "data"
SITE = BASE / "site"

for _ordner in (CACHE, DATA, SITE):
    _ordner.mkdir(exist_ok=True)

#: Jahrgänge, die abgeklopft werden. Die Obergrenze wächst mit, damit künftige
#: Jahre ohne Codeänderung erfasst werden.
JAHR_HEUTE = date.today().year
JAHRE = range(2006, JAHR_HEUTE + 6)


def lies_json(pfad: Path, standard=None):
    """JSON lesen; fehlt die Datei oder ist sie zerrissen, kommt der Standard.

    Eine halb geschriebene Datei brachte früher jeden Lauf zum Stehen, bis
    jemand sie von Hand löschte. Sie wird stattdessen beiseitegelegt — was
    darin steht, ist vielleicht noch zu retten.
    """
    if not pfad.exists():
        return standard
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        beiseite = pfad.with_name(pfad.name + ".kaputt")
        pfad.replace(beiseite)
        print(f"  ! {pfad.name} war nicht lesbar ({exc.__class__.__name__}); "
              f"liegt jetzt als {beiseite.name} daneben", file=sys.stderr)
        return standard


def schreib_json(pfad: Path, inhalt, *, kompakt: bool = False) -> None:
    """JSON schreiben: erst vollständig daneben, dann an seinen Platz rücken.

    Bricht ein Lauf mitten im Schreiben ab, bliebe sonst eine halbe Datei
    zurück. Bei `preis_verlauf.json` hieße das: die ganze beobachtete
    Preisgeschichte weg — sie steht nirgends sonst.
    """
    text = json.dumps(inhalt, ensure_ascii=False,
                      **({"separators": (",", ":")} if kompakt else {"indent": 2}))
    schreib_text(pfad, text + ("" if kompakt else "\n"))


def schreib_text(pfad: Path, text: str) -> None:
    """Textdatei atomar schreiben — dieselbe Vorsicht wie bei JSON."""
    _atomar(pfad, lambda ziel: ziel.write_text(text, encoding="utf-8"))


def schreib_bytes(pfad: Path, roh: bytes) -> None:
    """Binärdatei atomar schreiben."""
    _atomar(pfad, lambda ziel: ziel.write_bytes(roh))


def _atomar(pfad: Path, schreiben) -> None:
    daneben = pfad.with_name(pfad.name + ".neu")
    schreiben(daneben)
    os.replace(daneben, pfad)
