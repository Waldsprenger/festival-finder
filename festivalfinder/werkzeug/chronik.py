"""Ein Strich je Monat: wie groß der Bestand war und was die Quellen lieferten.

`data/lauf.json` beschreibt den letzten Lauf und wird bei jedem überschrieben.
Die Chronik behält je Monat eine Zeile — und ist damit die einzige Stelle, an
der sich zurückschauen lässt: Wie ist der Bestand über die Jahre gewachsen, kam
festivalticker je wieder, wann hat eine Quelle aufgehört zu liefern?

Sie wird mitversioniert, und das aus einem zweiten Grund: **GitHub schaltet
zeitgesteuerte Läufe in öffentlichen Projekten ab, wenn 60 Tage lang niemand
ins Projekt geschrieben hat.** Die Läufe selbst zählen dabei nicht — nur ein
Schreibvorgang im Projekt. Über den Herbst wird an dieser Seite ohnehin
gearbeitet, im Frühjahr oft monatelang nicht; genau dann fiele der tägliche
Lauf aus, und mit ihm alles, was er trägt.

Eine Zeile im Monat ist die kleinste ehrliche Antwort darauf. Ein leerer
Commit täte es technisch auch, wäre aber genau das: leer. Was hier steht, hat
für sich einen Zweck, und dass es nebenbei den Lauf am Leben hält, ist kein
Kunstgriff, sondern die Folge davon, dass etwas passiert.
"""

import json
from datetime import date

from ..pfade import DATA, schreib_text

DATEI = DATA / "chronik.jsonl"


def zeilen() -> list[dict]:
    """Die bisherigen Monatszeilen; eine unlesbare Zeile hält nichts auf."""
    if not DATEI.exists():
        return []
    heraus = []
    for zeile in DATEI.read_text(encoding="utf-8").splitlines():
        if not zeile.strip():
            continue
        try:
            heraus.append(json.loads(zeile))
        except json.JSONDecodeError:
            continue
    return heraus


def nachtragen(lauf: dict, acts: int, heute: str | None = None) -> bool:
    """Die Zeile dieses Monats anlegen, falls es sie noch nicht gibt.

    Gibt True zurück, wenn geschrieben wurde — daran erkennt der Workflow, ob
    es etwas zu veröffentlichen gibt.
    """
    monat = (heute or date.today().isoformat())[:7]
    bisher = zeilen()
    if any(z.get("monat") == monat for z in bisher):
        return False

    bisher.append({
        "monat": monat,
        "stand": lauf.get("stand", ""),
        "festivals": lauf.get("festivals", 0),
        "acts": acts,
        "quellen": lauf.get("quellen") or {},
        # Was an dem Tag nicht stimmte, gehört dazu: Ohne das steht später eine
        # Zahl da, ohne dass jemand weiß, warum sie so niedrig war.
        "warnungen": lauf.get("warnungen") or [],
    })
    bisher.sort(key=lambda z: z.get("monat", ""))
    schreib_text(DATEI, "".join(
        json.dumps(z, ensure_ascii=False, separators=(",", ":")) + "\n"
        for z in bisher))
    return True
