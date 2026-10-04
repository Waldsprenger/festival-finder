"""festivalfinder.eu — Trefferliste der European Festivals Association.

Klassik, Theater und Osteuropa. Der Filter artDisciplines=music entspricht der
Suche auf der Seite; ohne ihn kämen Film- und Tanzfestivals mit.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, land_code
from ..kern.text import clean
from ..netz import Abrufer, soup
from .basis import Quelle, erster_link, ohne_jahr

FF = "https://www.festivalfinder.eu"

LISTE = re.compile(r'href="(/find-festival-organisations/[a-z0-9\-]+)"')
#: „21 Aug 2026 - 30 Nov 2026", danach „Didymoteicho, Greece"
TERMIN = re.compile(r"(\d{1,2} [A-Z][a-z]{2} \d{4})\s*[-–]\s*(\d{1,2} [A-Z][a-z]{2} \d{4})")
ORT = re.compile(r"\s*([^,]{2,40}),\s*([A-Za-zÄÖÜäöü' \-]{3,40}?)\s+"
                 r"(?:Visit|facebook|instagram|X\b|youtube|The |This )")


class FestivalFinderEu(Quelle):
    name = "festivalfinder"
    startseite = FF
    zweck = "Klassik, Theater und Osteuropa"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Die Trefferliste blättert über den Pfad: /p2, /p3 und so fort."""
        links: dict[str, None] = {}
        for seite in range(1, 260):
            pfad = f"{FF}/find-festival-organisations" + ("" if seite == 1 else f"/p{seite}")
            if not (html := netz.fetch(f"{pfad}?query&country&daterange"
                                       f"&artDisciplines%5B0%5D=music")):
                break
            neu = {FF + t for t in LISTE.findall(html)
                   if t.rstrip("/") != "/find-festival-organisations"} - set(links)
            if not neu:
                break
            links.update(dict.fromkeys(neu))
        return list(links)

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        # Die ersten beiden <h1> gehören dem Cookie-Hinweis, deshalb der Titel.
        # Fehlseiten antworten mit 200, erkennbar nur an ihrem Text.
        titel = clean(s.title.get_text()) if s.title else ""
        name = re.sub(r"\s*[-–|]\s*European Festivals Association\s*$", "", titel)
        if not name or name.lower().startswith("we could not find"):
            return None

        flach = clean(s.get_text(" ", strip=True))
        stadt = land = ""
        if (tm := TERMIN.search(flach)) and (om := ORT.match(flach[tm.end():tm.end() + 120])):
            stadt, land = clean(om.group(1)), land_code(clean(om.group(2)))
        if not ist_land(land):
            return None

        von = zeit.aus_englisch(tm.group(1))
        return fund(
            self.name, url, ohne_jahr(name),
            von=von, bis=zeit.aus_englisch(tm.group(2)),
            stadt=stadt, land=land,
            webseite=erster_link(s, text="visit website"),
            hinweis="" if von else "Termin noch nicht veröffentlicht",
        )
