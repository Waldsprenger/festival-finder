"""Preise über die Zeit verfolgen.

Die Quellen nennen fast immer den Preis zum Verkaufsstart und schreiben ihn
selten fort. Tagesaktuelle Preise von den Veranstalterseiten zu holen, geht
nicht: Ein Viertel der Seiten untersagt das Auslesen in der robots.txt, und wo
es erlaubt wäre, stehen die Preise in nachgeladenen Shop-Fenstern oder bei
Ticketanbietern — von 22 geprüften Ticket-Unterseiten enthielt keine einzige
einen lesbaren Preis.

Was bleibt, ist die eigene Beobachtung: Der Lauf holt die Quellseiten täglich.
Ändert eine Quelle ihren Preis, steht die Änderung hier fest — und die Seite
kann den heutigen Preis nennen und den ersten in Klammern dahinter.

Festivals, die aus den Quellen verschwinden, bleiben zwei Monate stehen und
fallen dann heraus; sonst wüchse die Datei mit jedem Jahrgang — und ein
einziger Tag, an dem eine Quelle schweigt, würde die Geschichte aller ihrer
Festivals löschen.
"""

from datetime import date

from ..kern.festival import Festival
from ..kern.text import city_key, festival_key
from ..pfade import DATA, lies_json, schreib_json

DATEI = DATA / "preis_verlauf.json"
#: So lange bleibt ein Festival in der Beobachtung, auch wenn es gerade fehlt
GEDULD_TAGE = 60


def _tage_her(stand: str, heute: str) -> int:
    """Tage zwischen zwei ISO-Daten; ohne lesbares Datum: unendlich lange her."""
    try:
        return (date.fromisoformat(heute) - date.fromisoformat(stand)).days
    except ValueError:
        return 10 ** 6


def schluessel(f: Festival) -> str:
    """Ein Festival über Läufe hinweg wiedererkennen."""
    return f"{festival_key(f.name)}|{f.jahr}|{city_key(f.stadt)}"


def verfolgen(festivals: list[Festival], heute: str | None = None) -> dict[str, int]:
    """Preise mit dem letzten Lauf vergleichen und die Historie fortschreiben.

    Trägt bei jedem Festival, dessen Preis sich seit der ersten Beobachtung
    geändert hat, den Startpreis nach.
    """
    heute = heute or date.today().isoformat()
    vorher = lies_json(DATEI, {}) or {}
    verlauf: dict[str, dict] = {}
    geaendert = 0

    for f in festivals:
        if not f.preis:
            continue
        k = schluessel(f)
        alt = vorher.get(k)
        if alt is None:
            eintrag = {"erst": f.preis, "seit": heute,
                       "aktuell": f.preis, "stand": heute}
        elif alt["aktuell"] != f.preis:
            eintrag = {"erst": alt["erst"], "seit": alt["seit"],
                       "aktuell": f.preis, "stand": heute}
        else:
            eintrag = alt
        verlauf[k] = eintrag

        if eintrag["erst"] != f.preis:
            f.preis_start = eintrag["erst"]
            f.preis_start_seit = eintrag["seit"]
            geaendert += 1

    # Ein Festival, das in diesem Lauf fehlt, ist nicht unbedingt verschwunden:
    # An dem Tag, an dem festivalticker den Serverlauf abwies, fehlten 800 auf
    # einmal. Ihre Geschichte einfach zu löschen hieße, den Startpreis beim
    # nächsten Auftauchen neu zu erfinden.
    for k, alt in vorher.items():
        if k not in verlauf and _tage_her(alt.get("stand", ""), heute) <= GEDULD_TAGE:
            verlauf[k] = alt

    schreib_json(DATEI, verlauf)
    return {"beobachtet": len(verlauf), "geändert": geaendert,
            "neu": len(verlauf) - len(set(vorher) & set(verlauf))}
