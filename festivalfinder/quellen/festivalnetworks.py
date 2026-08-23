"""festivalnetworks.com — 624 Festivals in einer Datei.

Die Karte der Seite lädt ihre Punkte aus einer JSON-Datei. Die zu lesen ist
genauer und schonender, als 624 Seiten einzeln abzurufen — deshalb ist dies die
einzige Quelle ohne Adressliste.
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

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        raise NotImplementedError("diese Quelle liefert eine Sammeldatei")

    def sammeldatei(self, netz: Abrufer, seit: int) -> list[Fund]:
        roh = netz.fetch(f"{FN}/data-api.php?r=festivals")
        try:
            eintraege = json.loads(roh or "[]")
        except json.JSONDecodeError:
            netz.melde(f"Datei nicht lesbar: {FN}")
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
