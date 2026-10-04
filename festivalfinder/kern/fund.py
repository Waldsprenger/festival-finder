"""Ein Fund: was eine Quelle über eine Veranstaltung hergibt.

Ein eingefrorener Datensatz mit festen Feldern: Ein Tippfehler im Feldnamen
wirft sofort, und nach dem Bauen lässt sich nichts mehr heimlich ändern.

`fund()` ist der Trichter, durch den jede Quelle geht. Hier steht, was für alle
zwölf gilt — und nirgends sonst.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import geld, orte, text


@dataclass(frozen=True, slots=True)
class Fund:
    """Was eine Quelle liefert — geprüft und geradegezogen. Gebaut wird ein
    Fund über `fund()`, nicht über den Konstruktor: Nur dort laufen die
    Prüfungen."""

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


#: Was als Ortsname dasteht, aber keiner ist: eine Jahreszahl gehört zum
#: Festivalnamen („Immergut Festival 2026" stand bei 24 Festivals im
#: Ortsfeld), eine Wikidata-Kennung („Q226941") zum Datenblatt dahinter.
_KEIN_ORT = re.compile(r"\b(?:19|20)\d\d\b|^Q\d+$")


def fund(quelle: str, url: str, name: str, *,
         von: date | None = None, bis: date | None = None, jahr: str = "",
         stadt: str = "", land: str = "", ort: str = "", plz: str = "",
         lat: float | None = None, lon: float | None = None,
         preis: str = "", webseite: str = "", genre: str = "",
         besucher: str = "", hinweis: str = "", abgesagt: bool = False,
         lineup=None) -> Fund:
    """Ein Fund, wie ihn alle Quellen abliefern. Geradegezogen wird hier:

    * Der Name folgt `data/festival_aliase.json`, wo kein Buchstabenvergleich
      hilft.
    * Ein Termin, der vor seinem Anfang endet, ist keiner (festivalabroad:
      NorthSide vom 12. bis 6. Juni). Ohne Termin findet der Eintrag über Ort
      und Namen zu dem, den die anderen Quellen datieren.
    * Das Jahr richtet sich nach dem Termin, nicht nach dem Titel.
    * Das Land als Kürzel, nicht als Name.
    * Die Postleitzahl gehört ins Postleitzahlfeld, nicht vor den Ortsnamen;
      eine Jahreszahl oder Wikidata-Kennung ist kein Ort.
    * Eine Spielstätte, die nur den Ort wiederholt, sagt nichts — auf der
      Karte stand sonst „Winnipeg, Winnipeg, CA", bei allen 2.960 Funden von
      festapp.
    * Eine Koordinate muss auf der Erde liegen, nicht bei null Grad null — und
      in dem Land, das die Quelle nennt.
    * Preis, Besucherzahl und Webseite müssen sein, was sie behaupten; aus der
      Webseite fallen Werbeparameter wie `utm_source=wannafest`.
    * Ein Act steht einmal im Lineup, auch wenn er an zwei Tagen spielt.
    """
    if von and bis and bis < von:
        von = bis = None
    if not orte.punkt_plausibel(lat, lon) or not orte.punkt_passt_zum_land(lat, lon, land):
        lat = lon = None
    stadt, plz = text.plz_und_stadt(stadt, plz)
    if _KEIN_ORT.search(stadt):
        stadt = ""
    ort = text.clean(ort)
    if ort.casefold() == stadt.casefold():
        ort = ""
    return Fund(
        quelle=quelle, url=url, name=text.festival_name(name),
        von=von, bis=bis or von,
        jahr=str(von.year) if von else jahr,
        stadt=stadt, land=orte.land_code(land), ort=ort, plz=plz,
        lat=lat, lon=lon,
        preis=geld.ist_preis(preis), webseite=adresse(webseite),
        genre=genre, besucher=text.besucherzahl(besucher),
        hinweis=hinweis, abgesagt=abgesagt,
        lineup=tuple(dict.fromkeys(lineup or ())),
    )


def adresse(wert: str) -> str:
    """Eine Adresse, die mit http beginnt — ohne Werbeparameter.

    Acht Karten trugen einen Verweis auf „None", weil ein Datenblattfeld null
    hieß. Und wannafest hängt an 1.054 Adressen „?utm_source=wannafest" an.
    """
    wert = (wert or "").strip()
    if not wert.lower().startswith("http"):
        return ""
    teile = urlsplit(wert)
    if "utm_" not in teile.query:
        return wert
    rest = [(k, v) for k, v in parse_qsl(teile.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")]
    return urlunsplit(teile._replace(query=urlencode(rest)))
