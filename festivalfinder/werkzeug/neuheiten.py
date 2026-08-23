"""Seit wann kennen wir das? — die Grundlage für „was ist neu".

Zwei Arten von Neuigkeit, und die zweite ist die interessantere:

* **Ein Festival ist neu** — es stand vorher in keiner Quelle.
* **Eine Band ist bestätigt** — das Festival steht längst in der Liste, aber im
  Lineup steht jetzt jemand, der vorher nicht darin stand. Wacken kennt jeder;
  interessant wird es, wenn dort Powerwolf dazukommt.

Festgehalten wird deshalb nicht, *was an welchem Tag passiert ist*, sondern
*seit wann wir etwas kennen*: je Festival ein Datum, je Band im Lineup ein
Datum. Das ist dieselbe Auskunft, aber einmal je Sache statt einmal je
Ereignis — und damit ohne Zeitfenster. Wer nach vierzig Tagen wiederkommt,
bekommt die Änderungen aus vierzig Tagen; wer nach einem halben Jahr
wiederkommt, die aus einem halben Jahr. Ein Tagebuch mit Rückblickgrenze
konnte das nicht: Was älter war als die Grenze, fiel still heraus.

Begrenzt wird trotzdem, nur an der richtigen Stelle: Ein Festival, das aus
allen Quellen verschwunden ist, fliegt nach `GEDULD_TAGE` heraus. Damit wächst
die Datei nicht mit den Jahrgängen, sondern bleibt so groß wie der Bestand.

Zwei Regeln halten das ruhig:

* **Der erste Lauf meldet nichts.** Ohne einen Zustand zum Vergleichen wäre
  jedes der 13.338 Festivals neu. Der Tag, an dem die Aufzeichnung begann,
  steht als `beginn` in der Datei; alles, was dieses Datum trägt, gilt als
  „schon immer da" — dauerhaft, nicht nur beim ersten Mal.
* **Ein Festival, das einen Lauf lang fehlt, ist nicht verschwunden.** An dem
  Tag, an dem festivalticker den Serverlauf abwies, fehlten 1.900 auf einmal.
  Ohne Geduld wären sie am Tag darauf allesamt „neu" gewesen.
"""

from datetime import date

from ..kern.festival import Festival
from ..pfade import DATA, lies_json, schreib_json

#: Seit wann wir welches Festival und welche Band kennen
DATEI = DATA / "bestand_verlauf.json"

#: So lange bleibt ein Festival stehen, auch wenn es gerade in keiner Quelle ist
GEDULD_TAGE = 60


def _tage_her(stand: str, heute: str) -> int:
    """Tage zwischen zwei ISO-Daten; ohne lesbares Datum: unendlich lange her."""
    try:
        return (date.fromisoformat(heute) - date.fromisoformat(stand)).days
    except ValueError:
        return 10 ** 6


def lesen() -> dict:
    """Der aufgezeichnete Stand: `{"beginn": …, "stand": …, "feste": {…}}`."""
    roh = lies_json(DATEI, {}) or {}
    return {"beginn": roh.get("beginn", ""), "stand": roh.get("stand", ""),
            "feste": roh.get("feste") or {}}


def verfolgen(festivals: list[Festival], heute: str | None = None) -> dict[str, int]:
    """Aufzeichnen, seit wann wir was kennen; gibt die Zugänge dieses Laufs zurück."""
    heute = heute or date.today().isoformat()
    vorher = lesen()
    beginn = vorher["beginn"] or heute
    # Ein Lauf nach langer Pause richtet sich neu aus, statt zu urteilen. Die
    # Geduld fragt „wie lange hat keine Quelle das mehr geliefert" — und wenn
    # zwei Monate lang gar nicht gesammelt wurde, hat niemand gefragt. Ohne
    # diese Ausnahme wäre nach einer Pause der ganze Bestand „neu"; GitHub
    # schaltet zeitgesteuerte Läufe nach 60 Tagen ohne Aktivität ab, die Pause
    # ist also keine Erfindung.
    pause = _tage_her(vorher["stand"], heute) if vorher["stand"] else 0
    bekannt = dict(vorher["feste"]) if pause > GEDULD_TAGE else {
        k: e for k, e in vorher["feste"].items()
        if _tage_her(e.get("stand", ""), heute) <= GEDULD_TAGE}

    feste: dict[str, dict] = {}
    neue_feste = neue_bands = 0

    for f in festivals:
        alt = bekannt.get(f.kennung)
        seit = (alt or {}).get("seit", heute)
        alte_bands = (alt or {}).get("bands") or {}
        # Bands, die es beim ersten Sehen des Festivals schon gab, tragen
        # dessen Datum: Sie sind keine eigene Neuigkeit.
        bands = {name: alte_bands.get(name, heute) for name in f.lineup}

        feste[f.kennung] = {"seit": seit, "stand": heute, "bands": bands}
        if alt is None and seit > beginn:
            neue_feste += 1
        elif alt is not None:
            neue_bands += sum(1 for name in bands if name not in alte_bands)

    for kennung, alt in bekannt.items():
        feste.setdefault(kennung, alt)

    schreib_json(DATEI, {"beginn": beginn, "stand": heute, "feste": feste},
                 kompakt=True)
    return {"festivals": neue_feste, "bands": neue_bands, "bekannt": len(feste)}


def zugaenge(zustand: dict, kennung: str) -> tuple[str, dict[str, str]]:
    """Seit wann es dieses Festival gibt, und welche Band seit wann dazu.

    Zurück kommt nur, was nach dem Beginn der Aufzeichnung liegt — und bei den
    Bands nur, was später kam als das Festival selbst. Wer beim ersten Sehen
    schon im Lineup stand, ist keine eigene Meldung wert.
    """
    beginn = zustand["beginn"]
    eintrag = zustand["feste"].get(kennung)
    if not eintrag:
        return "", {}
    seit = eintrag["seit"] if eintrag["seit"] > beginn else ""
    bands = {name: datum for name, datum in (eintrag.get("bands") or {}).items()
             if datum > beginn and datum > eintrag["seit"]}
    return seit, bands
