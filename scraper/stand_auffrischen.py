"""Den mitgebrachten Stand einer Quelle auffrischen — sonst nichts.

    python scraper/stand_auffrischen.py              # alle mitgebrachten Quellen
    python scraper/stand_auffrischen.py festivalticker

Gedacht für den eigenen Rechner: festivalticker antwortet ihm, dem täglichen
Lauf auf fremden Servern dagegen mit 403. Was hier geholt wird, landet in
`data/schnappschuss/` und geht mit in die Versionsverwaltung; der Serverlauf
liest es, wenn seine eigene Anfrage nichts einbringt.

Bewusst schmal: Weder `data/festivals.json` noch die Webseite werden dabei
angefasst. Der Lauf dauert ein paar Minuten statt einer knappen Stunde und
lässt sich deshalb oft anstoßen — je öfter, desto frischer der Stand.
"""

from __future__ import annotations

import sys
import time
from datetime import date

import netz
import schnappschuss
from festival_scraper import einlesen
from quellen import QUELLEN


def auffrischen(name: str) -> int:
    """Eine Quelle holen und ablegen; gibt die Zahl der Datensätze zurück."""
    quelle = next((q for q in QUELLEN if q.name == name), None)
    if quelle is None:
        print(f"{name}: keine solche Quelle", file=sys.stderr)
        return 0

    print(f"{name}: Adressen sammeln ...", flush=True)
    urls = quelle.adressen(date.today().year)
    print(f"{name}: {len(urls)} Seiten", flush=True)
    records = einlesen(quelle, urls)

    if not records:
        # Der alte Stand bleibt, wie er ist. Eine leere Ablage wäre schlimmer
        # als eine ältere: Sie nähme dem Serverlauf die Quelle ganz.
        print(f"{name}: nichts gefunden - der bisherige Stand bleibt stehen",
              file=sys.stderr)
        return 0

    schnappschuss.schreiben(name, records)
    groesse = schnappschuss.datei(name).stat().st_size / 1e6
    print(f"{name}: {len(records)} Datensätze abgelegt ({groesse:.2f} MB)")
    return len(records)


def main() -> int:
    namen = sys.argv[1:] or list(schnappschuss.MITGEBEN)
    netz.einstellen(max_age_h=24.0, frisch=False)
    t0 = time.time()
    gesamt = sum(auffrischen(name) for name in namen)
    print(f"Dauer: {time.time() - t0:.0f}s")
    if netz.FEHLGESCHLAGEN:
        print(f"Nicht ladbar: {len(netz.FEHLGESCHLAGEN)} Seiten")
    # Rückgabewert 1, wenn gar nichts zusammenkam - dann soll ein Zeitplan
    # nichts committen.
    return 0 if gesamt else 1


if __name__ == "__main__":
    raise SystemExit(main())
