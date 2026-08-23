"""Was seit gestern dazugekommen ist — und was davon eine Meldung wert ist.

Zwei Arten von Neuigkeit, und die zweite ist die interessantere:

* **Ein Festival ist neu** — es stand gestern in keiner Quelle.
* **Eine Band ist bestätigt** — das Festival steht längst in der Liste, aber
  im Lineup steht jetzt jemand, der gestern noch nicht darin stand. Wacken
  kennt jeder; interessant wird es, wenn dort Powerwolf dazukommt.

Dafür zwei Dateien, jede mit einer Aufgabe:

* `data/bestand_verlauf.json` — der **Zustand**: welche Festivals es gibt und
  wer bei ihnen spielt. Daran wird verglichen.
* `data/neuheiten.json` — das **Tagebuch**: was an welchem Tag dazukam, dreißig
  Tage weit zurück. Daraus entsteht beim Bauen `site/neu.json`, gegen das die
  Seite ihre gemerkten Wunschlisten hält.

Zwei Regeln halten das ruhig:

* **Der erste Lauf meldet nichts.** Ohne einen Zustand zum Vergleichen wäre
  jedes der 13.338 Festivals neu — das Tagebuch stünde voll und die Meldung
  wäre wertlos.
* **Ein Festival, das einen Lauf lang fehlt, ist nicht verschwunden.** An dem
  Tag, an dem festivalticker den Serverlauf abwies, fehlten 1.900 auf einmal.
  Ohne Geduld wären sie am Tag darauf allesamt „neu" gewesen.
"""

from datetime import date

from ..kern.festival import Festival
from ..pfade import DATA, lies_json, schreib_json

#: Der Zustand: was es gibt und wer dort spielt
ZUSTAND = DATA / "bestand_verlauf.json"
#: Das Tagebuch: was an welchem Tag dazukam
TAGEBUCH = DATA / "neuheiten.json"

#: So lange bleibt ein Festival im Zustand stehen, auch wenn es gerade fehlt
GEDULD_TAGE = 60
#: So weit reicht das Tagebuch zurück — so lange darf ein Gerät auch aus sein
TAGEBUCH_TAGE = 30


def _tage_her(stand: str, heute: str) -> int:
    """Tage zwischen zwei ISO-Daten; ohne lesbares Datum: unendlich lange her."""
    try:
        return (date.fromisoformat(heute) - date.fromisoformat(stand)).days
    except ValueError:
        return 10 ** 6


def verfolgen(festivals: list[Festival], heute: str | None = None) -> dict[str, int]:
    """Den Bestand mit dem letzten Lauf vergleichen und das Tagebuch fortschreiben."""
    heute = heute or date.today().isoformat()
    # Beim Lesen altern, nicht erst beim Schreiben: Sonst hinge die Geduld
    # daran, wie oft der Lauf zwischendurch stattgefunden hat — nach einem
    # halben Jahr Pause stünde der Zustand von damals noch als „gestern" da.
    vorher = {k: e for k, e in (lies_json(ZUSTAND, {}) or {}).items()
              if _tage_her(e.get("stand", ""), heute) <= GEDULD_TAGE}
    # Ohne Vergleichsstand wird nichts gemeldet. Das gilt auch, wenn der letzte
    # Lauf so lange her ist, dass nichts davon übrig blieb — dann weiß niemand
    # mehr, was in der Zwischenzeit dazugekommen ist.
    erster_lauf = not vorher

    tagebuch = [e for e in (lies_json(TAGEBUCH, []) or [])
                if _tage_her(e.get("seit", ""), heute) <= TAGEBUCH_TAGE]
    zustand: dict[str, dict] = {}
    neue_feste = neue_bands = 0

    for f in festivals:
        k = f.kennung
        alt = vorher.get(k)
        bands = f.lineup
        zustand[k] = {"seit": (alt or {}).get("seit", heute), "stand": heute,
                      "bands": bands}
        if erster_lauf:
            continue
        if alt is None:
            # Neu: Das ganze Lineup ist neu, auch wenn es leer ist.
            tagebuch.append({"k": k, "seit": heute, "grund": "neu", "bands": bands})
            neue_feste += 1
        elif (dazu := [b for b in bands if b not in set(alt.get("bands") or ())]):
            tagebuch.append({"k": k, "seit": heute, "grund": "lineup", "bands": dazu})
            neue_bands += len(dazu)

    for k, alt in vorher.items():
        zustand.setdefault(k, alt)

    schreib_json(ZUSTAND, zustand, kompakt=True)
    schreib_json(TAGEBUCH, tagebuch, kompakt=True)
    return {"festivals": neue_feste, "bands": neue_bands, "tagebuch": len(tagebuch)}
