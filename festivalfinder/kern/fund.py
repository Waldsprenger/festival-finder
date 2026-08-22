"""Ein Fund: was eine Quelle über eine Veranstaltung hergibt.

Früher war das ein Wörterbuch mit zweiundzwanzig Schlüsseln. `rec["date_form"]`
statt `rec["date_from"]` fiel dann erst zur Laufzeit auf — bei `.get()` gar
nicht, da kam still `None` zurück. Jetzt ist es ein eingefrorener Datensatz mit
festen Feldern: Ein Tippfehler wirft einen `AttributeError`, sobald die Zeile
läuft, und ein Fund lässt sich nach dem Bauen nicht mehr heimlich ändern.

`fund()` ist der Trichter, durch den jede Quelle geht. Hier steht, was für alle
zwölf gilt — und nirgends sonst.
"""

from dataclasses import dataclass, field
from datetime import date

from . import geld, orte, text


@dataclass(frozen=True, slots=True)
class Fund:
    """Was eine Quelle liefert — geprüft und geradegezogen.

    Gebaut wird ein Fund über `fund()`, nicht über den Konstruktor: Nur dort
    laufen die Prüfungen, die für alle Quellen gelten.
    """

    quelle: str
    url: str
    name: str
    von: date | None = None
    bis: date | None = None
    jahr: str = ""
    stadt: str = ""
    land: str = ""
    ort: str = ""                       # Spielstätte
    plz: str = ""
    lat: float | None = None
    lon: float | None = None
    preis: str = ""
    webseite: str = ""
    genre: str = ""
    besucher: str = ""
    hinweis: str = ""
    abgesagt: bool = False
    lineup: tuple[str, ...] = field(default_factory=tuple)


def fund(quelle: str, url: str, name: str, *,
         von: date | None = None, bis: date | None = None, jahr: str = "",
         stadt: str = "", land: str = "", ort: str = "", plz: str = "",
         lat: float | None = None, lon: float | None = None,
         preis: str = "", webseite: str = "", genre: str = "",
         besucher: str = "", hinweis: str = "", abgesagt: bool = False,
         lineup=None) -> Fund:
    """Ein Fund, wie ihn alle Quellen abliefern.

    Hier wird geradegezogen, was sonst jede Quelle einzeln beachten müsste —
    und hier steht die Plausibilitätsprüfung, die für alle zwölf gilt:

    * Der Name folgt der Liste in `data/festival_aliase.json`, falls er dort
      steht — für Fälle, die kein Buchstabenvergleich findet.
    * Das Jahr richtet sich nach dem Termin. Steht im Titel ein anderes als im
      Datum („Sommer im Park Gera 2027" mit Termin im August 2026), gilt der
      Termin: Er ist die genauere Angabe.
    * Das Land als Kürzel, nicht als Name. Sechs Leser lieferten „DE", zwei
      „Deutschland", und geradegezogen wurde es erst beim Zusammenführen. Zwei
      Schreibweisen für dieselbe Sache sind eine Fehlerquelle, auch wenn am
      Ende beide richtig ankommen.
    * Die Besucherzahl ist eine einzelne, plausible Zahl — oder keine.
    * Ein Act steht einmal im Lineup, auch wenn er an zwei Tagen spielt.
    * Der Preis nennt eine Zahl oder freien Eintritt; „Pop Punk" ist kein Preis.
    * Steht die Postleitzahl im Ortsfeld („104 45 Athen"), gehört sie ins
      Postleitzahlfeld.
    * Eine Koordinate muss auf der Erde liegen, nicht bei null Grad null — und
      in dem Land, das die Quelle nennt. Sonst steht Lollapalooza Berlin in
      Chicago und das LongLake Festival Lugano in Buenos Aires.
    """
    if not orte.punkt_plausibel(lat, lon) or not orte.punkt_passt_zum_land(
            lat, lon, land):
        lat = lon = None
    stadt, plz = text.plz_und_stadt(stadt, plz)
    return Fund(
        quelle=quelle,
        url=url,
        name=text.festival_name(name),
        von=von,
        bis=bis or von,
        jahr=str(von.year) if von else jahr,
        stadt=stadt,
        land=orte.land_code(land),
        ort=ort,
        plz=plz,
        lat=lat,
        lon=lon,
        preis=geld.ist_preis(preis),
        webseite=webseite,
        genre=genre,
        besucher=text.besucherzahl(besucher),
        hinweis=hinweis,
        abgesagt=abgesagt,
        # Ohne Wiederholungen, Reihenfolge wie geliefert: jambase nennt
        # einzelne Acts zweimal, wenn sie an mehreren Tagen spielen.
        lineup=tuple(dict.fromkeys(lineup or ())),
    )
