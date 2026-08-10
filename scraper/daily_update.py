"""Taeglicher Datenlauf: scrapen, neue Orte geokodieren, Seite neu bauen.

    python scraper/daily_update.py

Schreibt ein Protokoll nach data/update.log. Der Scraper laedt nur Seiten neu,
deren Cache aelter als 24 Stunden ist; die Geokodierung fragt ausschliesslich
Orte an, die noch nicht im Cache stehen.
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOG = BASE / "data" / "update.log"

STEPS = [
    ("Festivaldaten", [sys.executable, "scraper/festival_scraper.py", "--max-age", "24"]),
    ("Ortskoordinaten", [sys.executable, "scraper/geocode.py"]),
    # Die folgenden drei Datensaetze aendern sich kaum und laufen aus dem Cache.
    # Sie stehen trotzdem hier, damit ein frischer Klon vollstaendig baut.
    ("Ortsverzeichnis", [sys.executable, "scraper/build_gazetteer.py"]),
    ("Kartengrenzen", [sys.executable, "scraper/build_map.py"]),
    ("Schrift", [sys.executable, "scraper/fetch_fonts.py"]),
    ("Uebersicht", [sys.executable, "scraper/build_overview.py"]),
    ("Webseite", [sys.executable, "scraper/build_site.py"]),
    ("Artifact-Bundle", [sys.executable, "scraper/build_artifact.py"]),
]


def main() -> int:
    started = datetime.now()
    lines = [f"=== Lauf {started:%Y-%m-%d %H:%M} ==="]
    failed = 0

    for label, cmd in STEPS:
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        tail = [l for l in (proc.stdout or "").strip().splitlines() if l.strip()][-3:]
        status = "ok" if proc.returncode == 0 else f"FEHLER (exit {proc.returncode})"
        if proc.returncode != 0:
            failed += 1
            tail += [l for l in (proc.stderr or "").strip().splitlines()[-5:]]
        lines.append(f"[{label}] {status} nach {time.time() - t0:.0f}s")
        lines += [f"    {l}" for l in tail]
        print(f"[{label}] {status}", flush=True)

    lines.append(f"=== Ende, Dauer {(datetime.now() - started).seconds}s, "
                 f"{failed} Fehler ===\n")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"Protokoll: {LOG}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
