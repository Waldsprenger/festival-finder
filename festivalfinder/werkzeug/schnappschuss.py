"""Ein Stand je Quelle, für den Fall, dass sie einen Lauf nicht bedient.

Lange galt: festivalticker antwortet dem eigenen Rechner mit 200 und dem
täglichen Lauf auf GitHub-Servern mit 403 — eine Entscheidung des Betreibers
gegenüber Rechenzentrums-Adressen. Was der Lauf zu Hause ohnehin holte, wurde
hier abgelegt und mitversioniert; der Serverlauf las es, wenn seine eigene
Anfrage nichts einbrachte. Umgangen wurde dabei nichts.

Seit dem 22. August 2026 weist festivalticker auch den Rechner zu Hause ab.
Damit lässt sich der Stand nicht mehr auffrischen: Die Datei in
`data/schnappschuss/` ist die letzte Abschrift dessen, was die Quelle
beantwortet hat, und sie altert. Sie bleibt trotzdem — ohne sie fehlen der
Seite rund 1.900 Festivals von einem Tag auf den anderen.

Dass sie altert, bleibt sichtbar: Ab `ALTERSGRENZE_TAGE` meldet die Prüfung
nicht mehr das Schweigen der Quelle, sondern das Datum ihres Standes.

Zwei Regeln halten das ehrlich:

* Geschrieben wird nur, was auch wirklich gefunden wurde. Ein Lauf ohne Funde
  darf den Stand nicht leeren — sonst löschte ausgerechnet der Lauf, der
  nichts erreicht, die letzte Abschrift.
* Gelesen wird nur, wenn die Quelle im Lauf selbst nichts hergibt. Sollte sie
  wieder antworten, gilt ihre Antwort.
"""

import gzip
import json
from dataclasses import asdict
from datetime import date, datetime

from ..kern import zeit
from ..kern.fund import Fund
from ..pfade import DATA, schreib_bytes

#: Quellen mit mitgeliefertem Stand. Bewusst kurz: Jeder Eintrag hier ist eine
#: Quelle, die nicht jeder Lauf erreichen kann.
MITGEBEN = ("festivalticker",)

ORDNER = DATA / "schnappschuss"
#: Ab hier ist der Stand alt genug, um daran zu erinnern
ALTERSGRENZE_TAGE = 21


def datei(quelle: str):
    return ORDNER / f"{quelle}.json.gz"


def _als_zeile(f: Fund) -> dict:
    """Ein Fund als JSON — Termine als ISO-Datum, alles andere unverändert."""
    d = asdict(f)
    d["von"] = zeit.iso(f.von)
    d["bis"] = zeit.iso(f.bis)
    d["lineup"] = list(f.lineup)
    return d


def _aus_zeile(d: dict) -> Fund:
    return Fund(**{**d,
                   "von": zeit.aus_iso(d.get("von")),
                   "bis": zeit.aus_iso(d.get("bis")),
                   "lineup": tuple(d.get("lineup") or ())})


def schreiben(quelle: str, funde: list[Fund]) -> bool:
    """Den Stand einer Quelle ablegen. False, wenn es nichts abzulegen gab."""
    if quelle not in MITGEBEN or not funde:
        return False
    ORDNER.mkdir(parents=True, exist_ok=True)
    inhalt = json.dumps({
        "quelle": quelle,
        "stand": datetime.now().astimezone().strftime("%Y-%m-%d"),
        # Nach Adresse sortiert: Die Seiten kommen aus vier Fäden zurück, also
        # in wechselnder Reihenfolge. Ohne das Sortieren unterschiede sich die
        # Datei nach jedem Lauf und stünde als neue Fassung in der Geschichte,
        # obwohl kein einziges Festival anders ist.
        "records": [_als_zeile(f) for f in sorted(funde, key=lambda f: (f.url, f.name))],
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # mtime auf 0, aus demselben Grund.
    schreib_bytes(datei(quelle), gzip.compress(inhalt, 9, mtime=0))
    return True


def lesen(quelle: str) -> tuple[list[Fund], str]:
    """Der abgelegte Stand und sein Datum; leer, wenn es keinen gibt."""
    p = datei(quelle)
    if not p.exists():
        return [], ""
    inhalt = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    return [_aus_zeile(d) for d in (inhalt.get("records") or [])], inhalt.get("stand", "")


def alter_in_tagen(stand: str) -> int | None:
    """Wie viele Tage der Stand auf dem Buckel hat."""
    try:
        return (date.today() - date.fromisoformat(stand)).days
    except ValueError:
        return None
