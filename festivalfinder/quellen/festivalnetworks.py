"""festivalnetworks.com — 624 Festivals in einer Datei.

Die Karte der Seite lädt ihre Punkte aus einer JSON-Datei. Die zu lesen ist
genauer und schonender, als 624 Seiten einzeln abzurufen — deshalb ist dies die
einzige Quelle ohne Adressliste.

Seit dem 9. September 2026 gibt die Schnittstelle die Datei nur noch gegen ein
kurzlebiges Zugangszeichen heraus, das die Karte sich vorher holt; ohne
antwortet sie mit 403. Das ist eine Entscheidung des Betreibers und wird wie
jedes 403 geachtet: Das Zeichen nachzuahmen hieße, genau die Schranke zu
umgehen, die er eingebaut hat.

Seit Oktober 2026 ruht die Quelle deshalb. Einmal im Monat fragt der Lauf die
Datei trotzdem ab, genau wie früher und ohne Zeichen: Kommt sie wieder, steht
das als Warnung im Bericht. Dann genügt es, `ruht` zu leeren.
"""

import json

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import zahl_oder_nichts
from ..kern.text import feld, genres_vereinen
from ..netz import Abrufer
from .basis import Quelle

FN = "https://festivalnetworks.com"


class FestivalNetworks(Quelle):
    name = "festivalnetworks"
    startseite = FN
    zweck = "624 Festivals in einer Datei"
    ruht = "gibt ihre Datei seit dem 9. September 2026 nur noch mit Zugangszeichen heraus"

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        raise NotImplementedError("diese Quelle liefert eine Sammeldatei")

    def sammeldatei(self, netz: Abrufer, seit: int) -> list[Fund]:
        roh = netz.fetch(f"{FN}/data-api.php?r=festivals")
        # Ein abgewiesener Abruf ist etwas anderes als eine leere Datei. Beides
        # zu leeren Klammern zu machen, ließ im Bericht nur „kein einziger
        # Fund" stehen — ohne Hinweis, woran es lag.
        if roh is None:
            netz.melde(f"Datei nicht ladbar: {FN}")
            return []
        try:
            eintraege = json.loads(roh)
        except json.JSONDecodeError:
            netz.melde(f"Datei nicht lesbar: {FN}")
            return []
        # Eine Absage kommt als {"error": "Forbidden"} — als Liste gelesen,
        # wären das Schlüssel statt Festivals.
        if not isinstance(eintraege, list):
            netz.melde(f"Datei ohne Festivalliste: {FN}")
            return []

        funde = []
        for e in eintraege:
            name = feld(e.get("Festival Name"))
            von = zeit.aus_kurz(feld(e.get("Start Date")))
            if not name or (von and von.year < seit):
                continue
            preis = e.get("Ticket Price (EUR)")
            funde.append(fund(
                self.name, f"{FN}/#{name}", name,
                von=von, bis=zeit.aus_kurz(feld(e.get("End Date"))),
                stadt=feld(e.get("City/Region")).split(",")[0],
                land=feld(e.get("Country")),
                lat=zahl_oder_nichts(e.get("Latitude")),
                lon=zahl_oder_nichts(e.get("Longitude")),
                webseite=feld(e.get("Website")),
                genre=genres_vereinen(feld(e.get("Genre")),
                                      feld(e.get("Sub-Genre"))),
                besucher=feld(e.get("Capacity")),
                preis=f"ca. {preis} €" if isinstance(preis, (int, float)) and preis else "",
            ))
        return funde

    def wieder_offen(self, netz: Abrufer, seit: int) -> bool | None:
        """Eine Anfrage ohne Zeichen — genau die, die seit September abgewiesen wird.

        Eine Datei zählt nur, wenn sie wirklich über das Netz kam: Im
        Zwischenspeicher kann noch eine von vor der Sperre liegen, und ein Lauf
        mit `--max-age 0` nähme sie von dort.
        """
        funde = self.sammeldatei(netz, seit)
        if funde and not netz.hat_geholt([FN]):
            return None
        return bool(funde)
