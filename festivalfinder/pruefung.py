"""Was am Ergebnis nicht stimmen kann — und was gegenüber gestern fehlt.

Zwei verschiedene Fragen, deshalb zwei Funktionen:

* **Stimmigkeit** fragt nicht „wie beim letzten Mal", sondern „in sich
  stimmig": Passt das Jahr zum Termin, liegt das Ende nicht vor dem Anfang,
  zählt das Lineup richtig? Jeder dieser Punkte war schon einmal falsch.
* **Ausbeute** vergleicht mit dem letzten Lauf. Ändert eine Quelle ihren
  Seitenaufbau, liefert ihr Leser plötzlich weniger oder nichts mehr — in der
  Gesamtliste fällt das kaum auf, weil die anderen elf weiter füllen.
"""

import re

from .kern.festival import Festival
from .kern.geld import KOSTENLOS
from .kern.orte import ist_land
from .kern.text import KNOPFBESCHRIFTUNG, PLZ_VORN, city_key, festival_key
from .kern.zeit import ueberlappt
from .pfade import DATA, lies_json, schreib_json
from .werkzeug import schnappschuss

#: Ein Jahr im Festivalnamen („Big Day Out 2000 Auckland")
JAHR_IM_NAMEN = re.compile(r"\b(19\d\d|20\d\d)\b")


def gewesene_ausgabe(f: Festival, seit: int) -> bool:
    """Terminlos, aber mit vergangenem Jahr im Namen — das war einmal.

    Nachschlagewerke führen auch, was gewesen ist. Ohne Termin sähe der Eintrag
    auf der Seite aus wie eine offene Ankündigung; der Jahrgang im Namen sagt,
    dass er keine ist.
    """
    if f.von:
        return False
    jahre = [int(j) for j in JAHR_IM_NAMEN.findall(f.name)]
    return bool(jahre) and max(jahre) < seit


def stimmigkeit(festivals: list[Festival]) -> list[str]:
    """Widersprüche im Ergebnis finden, bevor sie auf die Seite kommen."""
    zaehler: dict[str, int] = {}

    def merke(bedingung: bool, was: str) -> None:
        if not bedingung:
            zaehler[was] = zaehler.get(was, 0) + 1

    for f in festivals:
        merke(bool(f.name.strip()), "ohne Namen")
        merke(bool(f.quellen), "ohne Quelle")
        merke(not f.von or f.jahr == str(f.von.year), "Jahr passt nicht zum Termin")
        merke(not (f.von and f.bis) or f.bis >= f.von, "Ende vor Anfang")
        merke(f.lat is None or (abs(f.lat) <= 90 and abs(f.lon) <= 180),
              "Koordinate ausserhalb der Erde")
        merke(not f.besucher or f.besucher.isdigit(), "Besucherzahl keine Zahl")
        # „isdigit" allein ließ Zahlen mit 66 Stellen durch, zusammengeklebt aus
        # Datumsangaben — eine Zahl war es ja.
        merke(not f.besucher.isdigit() or 10 <= int(f.besucher) <= 5_000_000,
              "Besucherzahl unplausibel")
        merke(not f.land or ist_land(f.land), "Land nicht erkannt")
        merke(not PLZ_VORN.match(f.stadt or ""), "Postleitzahl im Ortsfeld")
        merke(not f.preis or bool(re.search(r"[1-9]", f.preis))
              or bool(KOSTENLOS.search(f.preis)), "Preis ohne Preis")
        merke(not f.ort or not KNOPFBESCHRIFTUNG.match(f.ort),
              "Spielstätte ist eine Knopfbeschriftung")

    # Dubletten: gleicher Name, gleicher Ort, sich überschneidender Termin.
    # Zwei Ausgaben desselben Festivals im selben Jahr gibt es wirklich
    # (Heartbeatz im Juni und im September) — die dürfen bleiben.
    gruppen: dict[tuple[str, str, str], list[Festival]] = {}
    for f in festivals:
        gruppen.setdefault((festival_key(f.name).replace(" ", ""), f.jahr,
                            city_key(f.stadt)), []).append(f)
    for gleiche in gruppen.values():
        for i, a in enumerate(gleiche):
            for b in gleiche[i + 1:]:
                merke(not ueberlappt(a.von, a.bis, b.von, b.bis),
                      "Dublette übrig geblieben")

    return [f"{n}x {was}" for was, n in sorted(zaehler.items())]


STAND = DATA / "quellen_stand.json"


def ausbeute(funde: dict[str, int], festivals: int,
             mitgebracht: dict[str, str] | None = None) -> list[str]:
    """Vergleicht die Ausbeute mit dem letzten Lauf und meldet Einbrüche.

    Ein Fünftel weniger gilt als Einbruch; kleinere Schwankungen sind normal,
    Festivals kommen und gehen.
    """
    vorher = lies_json(STAND, {}) or {}
    warnungen: list[str] = []
    mitgebracht = mitgebracht or {}

    for name, datum in mitgebracht.items():
        # Die Quelle bedient diesen Lauf nicht, ihr Stand liegt aber bei. Zu
        # melden ist deshalb nicht ihr Schweigen, sondern sein Alter.
        tage = schnappschuss.alter_in_tagen(datum)
        if tage is None:
            warnungen.append(f"{name}: mitgebrachter Stand ohne lesbares Datum")
        elif tage > schnappschuss.ALTERSGRENZE_TAGE:
            warnungen.append(f"{name}: mitgebrachter Stand vom {datum} "
                             f"ist {tage} Tage alt")

    for name, jetzt in funde.items():
        if name in mitgebracht:
            continue
        frueher = vorher.get("quellen", {}).get(name)
        if not jetzt:
            # Ohne diesen Fall bleibt die schlimmste Störung stumm: Eine Null
            # ist als Maßstab unbrauchbar (`0 < 0 * 0.8` ist falsch), also
            # meldete der Vergleich nichts — und beim Lauf auf fremden Servern
            # lieferte festivalticker über Monate nichts, ohne dass es auffiel.
            warnungen.append(f"{name}: kein einziger Fund")
        elif frueher and jetzt < frueher * 0.8:
            warnungen.append(f"{name}: {jetzt} statt {frueher} Funde")

    frueher_gesamt = vorher.get("festivals")
    if frueher_gesamt and festivals < frueher_gesamt * 0.8:
        warnungen.append(f"Festivals gesamt: {festivals} statt {frueher_gesamt}")

    # Bei einem Einbruch bleibt der alte Maßstab stehen: Sonst gilt der
    # schlechte Wert ab morgen als normal und die Warnung verstummt, obwohl
    # nichts repariert ist.
    gemerkt = {name: (vorher.get("quellen", {}).get(name, jetzt)
                      if any(name in w for w in warnungen) else jetzt)
               for name, jetzt in funde.items()}
    schreib_json(STAND, {"quellen": gemerkt,
                         "festivals": max(festivals, frueher_gesamt or 0)
                         if warnungen else festivals})
    return warnungen
