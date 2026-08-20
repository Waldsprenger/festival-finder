"""Der komplette Datenlauf: sammeln, verorten, Seite bauen.

    python scraper/daily_update.py            # täglich: nur Älteres nachladen
    python scraper/daily_update.py --frisch   # wöchentlich: alles neu holen

Im Regelfall lädt der Scraper nur Seiten neu, deren Zwischenspeicher älter als
24 Stunden ist; die Geokodierung fragt ausschließlich Orte an, die noch nicht
im Cache stehen.

Mit --frisch wird jede Seite neu abgerufen und anschließend gelöscht, was der
Lauf nicht angefasst hat. Das hält den Zwischenspeicher aktuell: Stille
Korrekturen der Quellen — ein verschobener Termin, ein nachgetragener Act —
kämen sonst erst an, wenn die Seite von sich aus wieder abgerufen wird.

Jeder Schritt läuft als eigener Prozess: Bricht einer ab, laufen die übrigen
weiter, und das Protokoll in data/update.log sagt, welcher es war.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime

from gemeinsam import BASE, DATA

LOG = DATA / "update.log"

# Die Schritte laufen als eigene Prozesse; ohne diese Vorgabe schreibt ein
# Kindprozess unter Windows in der Codepage der Konsole, während hier UTF-8
# gelesen wird - Umlaute im Protokoll wären dann Buchstabensalat.
UMGEBUNG = {**os.environ, "PYTHONIOENCODING": "utf-8"}

FRISCH = "--frisch" in sys.argv[1:]

SCHRITTE = [
    ("Festivaldaten", ["festival_scraper.py", "--max-age", "24"]
                      + (["--frisch"] if FRISCH else [])),
    ("Ortskoordinaten", ["geocode.py"]),
    # Die folgenden drei Datensätze ändern sich kaum und laufen aus dem Cache.
    # Sie stehen trotzdem hier, damit ein frischer Klon vollständig baut.
    ("Ortsverzeichnis", ["build_gazetteer.py"]),
    ("Kartengrenzen", ["build_map.py"]),
    ("Schrift", ["fetch_fonts.py"]),
    ("Übersicht", ["build_overview.py"]),
    ("Webseite", ["build_site.py"]),
    # nach build_site, weil der Service Worker den Datenstand als Version nutzt
    ("App-Dateien", ["build_pwa.py"]),
    ("Einzelseite", ["build_artifact.py"]),
]


def main() -> int:
    start = datetime.now()
    zeilen = [f"=== {'frischer Lauf' if FRISCH else 'Lauf'} {start:%Y-%m-%d %H:%M} ==="]
    fehler = 0

    for name, args in SCHRITTE:
        t0 = time.time()
        lauf = subprocess.run([sys.executable, "scraper/" + args[0], *args[1:]],
                              cwd=BASE, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=UMGEBUNG)
        letzte = [z for z in (lauf.stdout or "").strip().splitlines() if z.strip()][-3:]
        stand = "ok" if lauf.returncode == 0 else f"FEHLER (exit {lauf.returncode})"
        if lauf.returncode != 0:
            fehler += 1
            letzte += (lauf.stderr or "").strip().splitlines()[-5:]
        zeilen.append(f"[{name}] {stand} nach {time.time() - t0:.0f}s")
        zeilen += [f"    {z}" for z in letzte]
        print(f"[{name}] {stand}", flush=True)

    zeilen.append(f"=== Ende, Dauer {(datetime.now() - start).seconds}s, "
                  f"{fehler} Fehler ===\n")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    print(f"Protokoll: {LOG}")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
