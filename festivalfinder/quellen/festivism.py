"""festivism.com — ein Nachschlagewerk ohne Termine.

5.207 Festivals aus aller Welt, jedes mit Ort und Land, aber ohne Datum. Das
ist kein Mangel dieser Quelle, sondern ihr Zweck: Sie führt das Fest, nicht
seine nächste Ausgabe. Für den Bestand heißt das, dass ihre Einträge terminlos
bleiben — und in Stufe 6 mit dem datierten Zwilling zusammenfinden, wo es einen
gibt.
"""

import re

from ..kern.fund import Fund, fund
from ..kern.text import clean
from ..netz import Abrufer, erstes_objekt, json_ld_events, sitemap_adressen
from .basis import Quelle

FV = "https://www.festivism.com"


class Festivism(Quelle):
    name = "festivism"
    startseite = FV
    zweck = "Nachschlagewerk ohne Termine"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        adressen = [u for u in sitemap_adressen(netz.fetch(f"{FV}/sitemap.xml"))
                    if re.search(r"/festivals/[^/]+$", u)]
        if not adressen:
            netz.melde(f"Sitemap ohne Festivalseiten: {FV}")
        return sorted(set(adressen))

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        for d in json_ld_events(html):
            name = clean(str(d.get("name", "")))
            if not name:
                continue
            anschrift = erstes_objekt(erstes_objekt(d.get("location")).get("address"))
            land = str(anschrift.get("addressCountry", ""))
            # „XW" steht bei dieser Quelle für die Spielwelt: Konzerte in
            # Minecraft und Roblox. Die gibt es wirklich — hinfahren kann man
            # nicht.
            if land.upper() == "XW" or "online" in str(
                    d.get("eventAttendanceMode", "")).lower():
                return None
            stadt = clean(str(anschrift.get("addressLocality", ""))).split(",")[0]
            return fund(self.name, url, name, stadt=stadt, land=land)
        return None
