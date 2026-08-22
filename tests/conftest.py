"""Gemeinsame Grundlage der Tests.

Das Paket liegt im Projektverzeichnis; `pytest` findet es über die
Einstellung in pyproject.toml. Hier stehen nur die Hilfen, die mehrere
Testdateien brauchen — allen voran ein Abrufer, der nichts abruft.
"""

import gzip
import json
from pathlib import Path

import pytest

from festivalfinder.netz import Abrufer

SEITEN = Path(__file__).parent / "seiten"


class StillerAbrufer(Abrufer):
    """Holt nichts aus dem Netz. Was er liefern soll, bekommt er vorgelegt.

    Der Vorgänger war ein Modul voller Variablen, und jeder Test musste sie von
    Hand leeren. Jetzt bekommt jeder Test einen eigenen Abrufer — was er tut,
    steht im Test und nirgends sonst.
    """

    def __init__(self, seiten: dict[str, str] | None = None, **kw):
        super().__init__(**kw)
        self.seiten = seiten or {}
        self.gefragt: list[str] = []

    def fetch(self, url, retries=3):
        self.gefragt.append(url)
        return self.seiten.get(url)

    def endziel(self, link, eigene_domain):
        return ""


@pytest.fixture
def netz():
    """Ein Abrufer ohne Netz und ohne Gedächtnis aus anderen Tests."""
    return StillerAbrufer()


@pytest.fixture(scope="session")
def verzeichnis():
    """Was in tests/seiten/ liegt: echte, eingefrorene Seiten je Quelle."""
    return json.loads((SEITEN / "verzeichnis.json").read_text(encoding="utf-8"))


def seite(datei: str) -> str:
    """Eine eingefrorene Seite auspacken."""
    return gzip.decompress((SEITEN / datei).read_bytes()).decode("utf-8", "replace")
