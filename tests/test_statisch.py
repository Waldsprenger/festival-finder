"""Was ein Leser sieht, ohne den Code auszuführen.

Diese Prüfung gibt es wegen eines Ausfalls, der drei Läufe und vier Stunden
gekostet hat. In `befehl_sammeln` steht oben `lauf.vorbereiten(funde)` — `lauf`
ist das Modul `bund.lauf`. Weiter unten bekam eine lokale Variable denselben
Namen, und damit galt `lauf` für die ganze Funktion als lokal: Der Aufruf oben
warf einen `UnboundLocalError`, und zwar erst nach achtzig Minuten Sammeln.

Kein Test hat das gemerkt, weil `befehl_sammeln` keinen hat — die Funktion
holt zwölf Verzeichnisse ab, das lässt sich nicht sinnvoll nachstellen. Ein
Blick auf den Quelltext hätte gereicht: pyflakes meldet genau diesen Fall.
"""

import subprocess
import sys

import pytest

from festivalfinder.pfade import BASE

pytest.importorskip("pyflakes", reason="ohne pyflakes keine statische Prüfung")


def test_der_quelltext_haelt_der_statischen_pruefung_stand():
    """Verwendung vor der Zuweisung, unbekannte Namen, toter Import.

    Alle drei fallen sonst erst zur Laufzeit auf — und im Sammellauf heißt das:
    nach achtzig Minuten.
    """
    lauf = subprocess.run(
        [sys.executable, "-m", "pyflakes", "festivalfinder", "tests"],
        cwd=BASE, capture_output=True, text=True)
    assert not lauf.stdout.strip(), "pyflakes meldet:\n" + lauf.stdout
