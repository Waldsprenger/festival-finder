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

Dass sie altert, bleibt sichtbar: Ab `ALTERSGRENZE_TAGE` meldet der Wächter in
`festival_scraper.pruefe_ausbeute` nicht mehr das Schweigen der Quelle,
sondern das Datum ihres Standes — im Laufbericht und in der Zusammenfassung.
Wann diese Daten zu alt sind, um sie noch zu zeigen, ist damit eine
Entscheidung, die jemand trifft, und keine, die still passiert.

Zwei Regeln halten das ehrlich:

* Geschrieben wird nur, was auch wirklich gefunden wurde. Ein Lauf ohne
  Funde darf den Stand nicht leeren — sonst löschte ausgerechnet der Lauf,
  der nichts erreicht, die letzte Abschrift.
* Gelesen wird nur, wenn die Quelle im Lauf selbst nichts hergibt. Sollte sie
  wieder antworten, gilt ihre Antwort.
"""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime

from gemeinsam import DATA

#: Quellen mit mitgeliefertem Stand. Bewusst kurz: Jeder Eintrag hier ist
#: eine Quelle, die nicht jeder Lauf erreichen kann.
MITGEBEN = ("festivalticker",)

ORDNER = DATA / "schnappschuss"
#: Ab hier ist der Stand alt genug, um daran erinnert zu werden
ALTERSGRENZE_TAGE = 21


def datei(quelle: str):
    return ORDNER / f"{quelle}.json.gz"


def schreiben(quelle: str, records: list[dict]) -> bool:
    """Den Stand einer Quelle ablegen. False, wenn es nichts abzulegen gab."""
    if quelle not in MITGEBEN or not records:
        return False
    ORDNER.mkdir(parents=True, exist_ok=True)
    inhalt = json.dumps({
        "quelle": quelle,
        "stand": datetime.now().astimezone().strftime("%Y-%m-%d"),
        # Nach Adresse sortiert: Die Seiten kommen aus vier Fäden zurück, also
        # in wechselnder Reihenfolge. Ohne das Sortieren unterschiede sich die
        # Datei nach jedem Lauf und stünde als neue Fassung in der Geschichte,
        # obwohl kein einziges Festival anders ist.
        "records": sorted(records, key=lambda r: (r.get("source_url", ""),
                                                  r.get("name", ""))),
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # mtime auf 0: Sonst unterscheidet sich die gepackte Datei bei jedem Lauf,
    # auch wenn kein einziges Festival anders ist - und landete als neue
    # Fassung in der Versionsgeschichte.
    datei(quelle).write_bytes(gzip.compress(inhalt, 9, mtime=0))
    return True


def lesen(quelle: str) -> tuple[list[dict], str]:
    """Der abgelegte Stand und sein Datum; leer, wenn es keinen gibt."""
    p = datei(quelle)
    if not p.exists():
        return [], ""
    inhalt = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    return inhalt.get("records") or [], inhalt.get("stand") or ""


def alter_in_tagen(stand: str) -> int | None:
    """Wie viele Tage der Stand auf dem Buckel hat."""
    try:
        return (date.today() - date.fromisoformat(stand)).days
    except ValueError:
        return None
