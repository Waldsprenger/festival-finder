"""Der Sammellauf: zwölf Quellen abklappern und zu einem Bestand bündeln.

Hier steht die Reihenfolge des Ganzen, nicht die Kunst des Einzelnen: Wie eine
Quelle ihre Seiten findet, steht in `quellen/`, wie aus Funden ein Festival
wird, in `bund/`.
"""

import concurrent.futures as cf
from dataclasses import dataclass, field

from .kern.festival import Festival
from .kern.fund import Fund
from .netz import Abrufer
from .quellen import Quelle, alle
from .werkzeug import schnappschuss


@dataclass
class Ergebnis:
    """Was ein Sammellauf hinterlässt — Zahlen inbegriffen."""

    festivals: list[Festival] = field(default_factory=list)
    #: Quellenname → Zahl der Funde
    funde: dict[str, int] = field(default_factory=dict)
    #: Quellenname → Datum des mitgebrachten Standes, falls einer einsprang
    mitgebracht: dict[str, str] = field(default_factory=dict)
    #: Quellenname → Seiten, an denen ihr Leser gescheitert ist
    parsefehler: dict[str, int] = field(default_factory=dict)
    #: Kürzel, die in diesem Bestand eine andere Band meinen
    kollisionen: list[str] = field(default_factory=list)
    bandstatistik: dict = field(default_factory=dict)


def einlesen(netz: Abrufer, quelle: Quelle, urls: list[str],
             parsefehler: dict[str, int]) -> list[Fund]:
    """Detailseiten einer Quelle parallel holen und auslesen."""
    funde: list[Fund] = []
    fertig = 0
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        auftraege = {pool.submit(netz.fetch, u): u for u in urls}
        for auftrag in cf.as_completed(auftraege):
            url = auftraege[auftrag]
            fertig += 1
            if fertig % 100 == 0:
                print(f"  {quelle.name}: {fertig}/{len(urls)}", flush=True)
            html = auftrag.result()
            if not html:
                continue
            try:
                f = quelle.lesen(netz, url, html)
            except Exception as exc:
                # Ein Fehler kostet dieses Festival, nicht den Lauf. Gezählt
                # wird trotzdem: Stille Ausfälle sind die gefährlichsten.
                parsefehler[quelle.name] = parsefehler.get(quelle.name, 0) + 1
                netz.melde(f"Parsefehler {url}: {exc}")
                continue
            if f and f.name:
                funde.append(f)
    return funde


def funde_sammeln(netz: Abrufer, seit: int, *, limit: int = 0,
                  quellen: list[Quelle] | None = None) -> tuple[list[Fund], Ergebnis]:
    """Alle Quellen abklappern; gibt die Funde und die Begleitzahlen zurück."""
    quellen = quellen if quellen is not None else alle()
    ergebnis = Ergebnis()
    alle_funde: list[Fund] = []

    print(f"Sammle Detail-Links ab Jahrgang {seit} ...", flush=True)
    # Quellen mit einer Sammeldatei haben keine Adressen je Festival — ihr
    # Abruf steht weiter unten, wo auch die Seiten gelesen werden.
    adressen = {q.name: q.adressen(netz, seit) for q in quellen
                if type(q).sammeldatei is Quelle.sammeldatei}
    print("  " + " | ".join(f"{n} {len(u)}" for n, u in adressen.items()), flush=True)

    for quelle in quellen:
        gefunden = _eine_quelle(netz, quelle, adressen, seit, limit, ergebnis)
        ergebnis.funde[quelle.name] = len(gefunden)
        alle_funde += gefunden

    print(f"Datensätze: {len(alle_funde)}", flush=True)
    return alle_funde, ergebnis


def _eine_quelle(netz: Abrufer, quelle: Quelle, adressen: dict, seit: int,
                 limit: int, ergebnis: Ergebnis) -> list[Fund]:
    if quelle.name not in adressen:
        gefunden = quelle.sammeldatei(netz, seit) or []
        print(f"  {quelle.name}: {len(gefunden)} Datensätze aus einer Datei", flush=True)
    else:
        urls = adressen[quelle.name]
        gefunden = einlesen(netz, quelle, urls[:limit] if limit else urls,
                            ergebnis.parsefehler)

    if gefunden:
        # Was dieser Lauf erreicht hat, bekommt der nächste mit, der es nicht
        # erreicht. Ein Teillauf (--limit) taugt dafür nicht.
        if not limit and schnappschuss.schreiben(quelle.name, gefunden):
            groesse = schnappschuss.datei(quelle.name).stat().st_size / 1e6
            print(f"  Stand von {quelle.name} abgelegt ({groesse:.2f} MB)")
        return gefunden

    mitgebracht, stand = schnappschuss.lesen(quelle.name)
    if mitgebracht:
        ergebnis.mitgebracht[quelle.name] = stand
        print(f"  {quelle.name} antwortet nicht - Stand vom {stand} "
              f"mit {len(mitgebracht)} Datensätzen")
    return mitgebracht
