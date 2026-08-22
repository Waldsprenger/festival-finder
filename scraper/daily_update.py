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

#: Zeitgrenze je Schritt. Die meisten sind in Sekunden durch; eine Stunde ist
#: reichlich Luft und trotzdem kurz genug, dass ein hängender Schritt am selben
#: Tag auffällt.
STUNDE = 3600

#: Das Einsammeln braucht länger: zwölf Quellen, 24.000 Seiten. Beim ersten
#: weltweiten Lauf ohne Zwischenspeicher waren es knapp zwei Stunden.
LANG = 4 * 3600

SCHRITTE = [
    ("Festivaldaten", ["festival_scraper.py", "--max-age", "24"]
                      + (["--frisch"] if FRISCH else []), LANG),
    # Das Ortsverzeichnis steht vor der Geokodierung: Was dort schon
    # drinsteht, muss nicht bei Nominatim erfragt werden.
    ("Ortsverzeichnis", ["build_gazetteer.py"]),
    ("Ortskoordinaten", ["geocode.py"]),
    # Kartengrenzen und Schrift ändern sich kaum und laufen aus dem Cache.
    # Sie stehen trotzdem hier, damit ein frischer Klon vollständig baut.
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

    for schritt in SCHRITTE:
        name, args = schritt[0], schritt[1]
        grenze = schritt[2] if len(schritt) > 2 else STUNDE
        t0 = time.time()
        try:
            lauf = subprocess.run([sys.executable, "scraper/" + args[0], *args[1:]],
                                  cwd=BASE, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=UMGEBUNG,
                                  timeout=grenze)
        except subprocess.TimeoutExpired as abbruch:
            # Ein Schritt, der nicht zurückkommt, ist schlimmer als einer, der
            # scheitert: Er hält den ganzen Lauf auf und fällt niemandem auf.
            # Das Ortsverzeichnis lief einmal vierzehn Stunden, weil eine
            # Prüfung in einer Schleife stand.
            fehler += 1
            zeilen.append(f"[{name}] ABBRUCH nach {time.time() - t0:.0f}s "
                          f"(Zeitgrenze {grenze}s)")
            zeilen += [f"    {z}" for z in
                       (abbruch.stdout or "").strip().splitlines()[-3:]]
            print(f"[{name}] ABBRUCH", flush=True)
            continue
        letzte = [z for z in (lauf.stdout or "").strip().splitlines() if z.strip()][-3:]
        stand = "ok" if lauf.returncode == 0 else f"FEHLER (exit {lauf.returncode})"
        # Warnungen stehen auf der Fehlerausgabe, auch wenn der Schritt gelingt -
        # ein Einbruch bei einer Quelle oder ein Widerspruch in den Daten soll
        # nicht nur in der Konsole aufblitzen, sondern im Protokoll stehen.
        meldungen = [z for z in (lauf.stderr or "").splitlines() if z.strip().startswith("!")]
        letzte += meldungen[-8:]
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
