"""Gemeinsame Grundlage der Tests: das scraper-Verzeichnis importierbar machen."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def frische_aliase():
    """Jeder Test beginnt mit der vollständigen Kürzeltabelle.

    `alias_kollisionen` schaltet Kürzel ab, und zwar im Modul — ohne diese
    Rückstellung hinge das Ergebnis eines Tests davon ab, welcher vorher lief.
    """
    import text
    text.aliase_zuruecksetzen()
    yield
    text.aliase_zuruecksetzen()
