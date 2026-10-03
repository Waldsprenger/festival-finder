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

from .bund.regeln import dieselbe_veranstaltung
from .kern.festival import Festival
from .kern.geld import KOSTENLOS
from .kern.orte import ist_land
from .kern.text import KNOPFBESCHRIFTUNG, PLZ_VORN, city_key
from .kern.zeit import ueberlappt
from .pfade import DATA, lies_json, schreib_json
from .werkzeug import schnappschuss

#: Ein Jahr im Festivalnamen („Big Day Out 2000 Auckland")
JAHR_IM_NAMEN = re.compile(r"\b(19\d\d|20\d\d)\b")

#: Was ein leeres Datenblattfeld hinterlässt, wenn es durch `str()` gegangen ist
NULLWORT = {"none", "null", "nil", "undefined", "nan", "n/a"}

#: Felder, in denen ein solches Wort nie ein echter Wert wäre
TEXTFELDER = ("stadt", "land", "ort", "plz", "preis", "webseite", "genre",
              "besucher", "hinweis")


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
        # `str(blatt.get("city", ""))` sieht sicher aus und ist es nicht: Steht
        # der Schlüssel im Datenblatt und trägt den Wert null, greift der
        # Standardwert nicht, und heraus kommt die Zeichenkette „None". Genau
        # das stand bei 2.490 Festivals als Ortsname — auf der Karte, in der
        # Suche, und der Geokodierer fragte in 111 Ländern nach einem Ort
        # namens „None".
        merke(not any(getattr(f, feld).strip().lower() in NULLWORT
                      for feld in TEXTFELDER), "Nullwert als Text im Feld")
        merke(not f.webseite or f.webseite.lower().startswith("http"),
              "Webseite ist keine Adresse")

    # Dubletten: derselbe Namenskern, gleicher Ort, sich überschneidender
    # Termin. Zwei Ausgaben desselben Festivals im selben Jahr gibt es wirklich
    # (Heartbeatz im Juni und im September) — die dürfen bleiben.
    #
    # Gefragt wird nach dem Kern, nicht nach dem Schlüssel: Sonst prüfte diese
    # Stelle genau das, was das Zusammenführen ohnehin schon zusammengelegt
    # hat, und könnte nie anschlagen. „Glücksgefühle" gegen „Gluecksgefuehle"
    # in Hockenheim stand ein halbes Jahr unbemerkt doppelt in den Daten.
    gruppen: dict[tuple[str, str], list[Festival]] = {}
    for f in festivals:
        gruppen.setdefault((f.jahr, city_key(f.stadt)), []).append(f)
    for gleiche in gruppen.values():
        for i, a in enumerate(gleiche):
            for b in gleiche[i + 1:]:
                merke(not (ueberlappt(a.von, a.bis, b.von, b.bis)
                           and dieselbe_veranstaltung(a.name, b.name, a.stadt)),
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
    mitgebracht = mitgebracht or {}
    #: Hinweise auf das Alter eines mitgebrachten Standes
    alterung: list[str] = []
    #: Einbrüche gegenüber dem letzten Lauf
    einbrueche: list[str] = []

    for name, datum in mitgebracht.items():
        # Die Quelle bedient diesen Lauf nicht, ihr Stand liegt aber bei. Zu
        # melden ist deshalb nicht ihr Schweigen, sondern sein Alter.
        tage = schnappschuss.alter_in_tagen(datum)
        if tage is None:
            alterung.append(f"{name}: mitgebrachter Stand ohne lesbares Datum")
        elif tage > schnappschuss.ALTERSGRENZE_TAGE:
            alterung.append(f"{name}: mitgebrachter Stand vom {datum} "
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
            einbrueche.append(f"{name}: kein einziger Fund")
        elif frueher and jetzt < frueher * 0.8:
            einbrueche.append(f"{name}: {jetzt} statt {frueher} Funde")

    frueher_gesamt = vorher.get("festivals")
    if frueher_gesamt and festivals < frueher_gesamt * 0.8:
        einbrueche.append(f"Festivals gesamt: {festivals} statt {frueher_gesamt}")

    # Bei einem Einbruch bleibt der alte Maßstab stehen: Sonst gilt der
    # schlechte Wert ab morgen als normal und die Warnung verstummt, obwohl
    # nichts repariert ist.
    #
    # Nur bei einem Einbruch. Die Alterswarnung zählt hier nicht: Den Stand von
    # festivalticker frischt nur ein Lauf von zu Hause auf, sie steht also oft
    # wochenlang in jedem Lauf. Zählte sie mit, fröre der Maßstab für
    # immer auf dem höchsten je erreichten Wert ein — und meldete Jahre später
    # einen Einbruch, den es nie gab.
    gemerkt = {name: (vorher.get("quellen", {}).get(name, jetzt)
                      if any(name in w for w in einbrueche) else jetzt)
               for name, jetzt in funde.items()}
    schreib_json(STAND, {"quellen": gemerkt,
                         "festivals": max(festivals, frueher_gesamt or 0)
                         if einbrueche else festivals})
    return alterung + einbrueche
