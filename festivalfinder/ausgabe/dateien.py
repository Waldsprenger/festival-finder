"""Der Bestand als Datei: JSON für die Webseite, CSV für die Tabelle.

Die Feldnamen im JSON sind englisch und bleiben es — `data/festivals.json`
wird mitveröffentlicht, und wer sie auswertet, soll das nach einem Umbau
weiter tun können. Die Zuordnung steht an einer Stelle: `Festival.als_json`.
"""

import csv

from ..kern.festival import Festival
from ..kern.zeit import deutsch
from ..pfade import DATA, schreib_json


def schreiben(festivals: list[Festival]) -> None:
    """JSON für die Webseite, drei CSV-Tabellen für alles andere."""
    schreib_json(DATA / "festivals.json", [f.als_json() for f in festivals])
    _festivals_csv(festivals)
    _lineups_csv(festivals)
    _bands_csv(festivals)


def _tabelle(name: str, kopf: list[str], zeilen) -> None:
    with (DATA / name).open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(kopf)
        w.writerows(zeilen)


def _festivals_csv(festivals: list[Festival]) -> None:
    _tabelle("festivals.csv",
             ["Name", "Jahr", "Von", "Bis", "Ort", "Land", "Venue", "Preis",
              "Webseite", "Genre", "Besucher", "Abgesagt", "Hinweis",
              "Preis zum Start", "Anzahl Acts", "Lineup", "Quellen"],
             ([f.name, f.jahr, deutsch(f.von), deutsch(f.bis), f.stadt,
               f.land, f.ort, f.preis, f.webseite, f.genre, f.besucher,
               "ja" if f.abgesagt else "", f.hinweis, f.preis_start,
               len(f.lineup), ", ".join(f.lineup),
               " | ".join(f.quellen.values())] for f in festivals))


def _lineups_csv(festivals: list[Festival]) -> None:
    _tabelle("lineups.csv",
             ["Band", "Festival", "Von", "Bis", "Ort", "Land"],
             ([b, f.name, deutsch(f.von), deutsch(f.bis), f.stadt, f.land]
              for f in festivals for b in f.lineup))


def _bands_csv(festivals: list[Festival]) -> None:
    """Acts über mehrere Festivals hinweg — zeigt Mehrfachbuchungen."""
    bands: dict[str, list[str]] = {}
    for f in festivals:
        for b in f.lineup:
            bands.setdefault(b, []).append(f.name)
    _tabelle("bands.csv",
             ["Band", "Anzahl Festivals", "Festivals"],
             ([b, len(fs), ", ".join(sorted(set(fs)))]
              for b, fs in sorted(bands.items(),
                                  key=lambda kv: (-len(kv[1]), kv[0].casefold()))))
