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

Ergebnis: `data/preis_verlauf.json`, je Festival der erste und der aktuelle
Preis mit Datum. Festivals, die aus den Quellen verschwinden, bleiben zwei
Monate stehen und fallen dann heraus; sonst wüchse die Datei mit jedem
Jahrgang - und ein einziger Tag, an dem eine Quelle schweigt, würde die
Geschichte aller ihrer Festivals löschen.
"""

from __future__ import annotations

from datetime import date

from gemeinsam import DATA, lies_json, schreib_json
from text import city_key, festival_key

DATEI = DATA / "preis_verlauf.json"
#: So lange bleibt ein Festival in der Beobachtung, auch wenn es gerade fehlt
GEDULD_TAGE = 60


def _tage_her(stand: str, heute: str) -> int:
    """Tage zwischen zwei ISO-Daten; ohne lesbares Datum: unendlich lange her."""
    try:
        return (date.fromisoformat(heute) - date.fromisoformat(stand)).days
    except ValueError:
        return 10 ** 6


def schluessel(f: dict) -> str:
    """Festival über Läufe hinweg wiedererkennen."""
    return f"{festival_key(f['name'])}|{f['year']}|{city_key(f['city'])}"


def verfolgen(festivals: list[dict], heute: str | None = None) -> dict[str, int]:
    """Preise mit dem letzten Lauf vergleichen und die Historie fortschreiben.

    Trägt bei jedem Festival, dessen Preis sich seit der ersten Beobachtung
    geändert hat, den Startpreis nach (`price_start`, `price_start_seit`).
    """
    heute = heute or date.today().isoformat()
    vorher = lies_json(DATEI, {}) or {}
    verlauf: dict[str, dict] = {}
    geaendert = 0

    for f in festivals:
        if not f["price"]:
            continue
        k = schluessel(f)
        alt = vorher.get(k)
        if alt is None:
            eintrag = {"erst": f["price"], "seit": heute,
                       "aktuell": f["price"], "stand": heute}
        elif alt["aktuell"] != f["price"]:
            eintrag = {"erst": alt["erst"], "seit": alt["seit"],
                       "aktuell": f["price"], "stand": heute}
        else:
            eintrag = alt
        verlauf[k] = eintrag

        if eintrag["erst"] != f["price"]:
            f["price_start"] = eintrag["erst"]
            f["price_start_seit"] = eintrag["seit"]
            geaendert += 1

    # Ein Festival, das in diesem Lauf fehlt, ist nicht unbedingt verschwunden:
    # An dem Tag, an dem festivalticker den Serverlauf abwies, fehlten 800 auf
    # einmal. Ihre Geschichte einfach zu löschen hiesse, den Startpreis beim
    # nächsten Auftauchen neu zu erfinden. Also bleiben sie eine Weile stehen.
    for k, alt in vorher.items():
        if k not in verlauf and _tage_her(alt.get("stand", ""), heute) <= GEDULD_TAGE:
            verlauf[k] = alt

    schreib_json(DATEI, verlauf)
    return {"beobachtet": len(verlauf), "geändert": geaendert,
            "neu": len(verlauf) - len(set(vorher) & set(verlauf))}
