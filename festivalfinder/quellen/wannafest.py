"""wannafest.com — Sitemap, überwiegend Clubabende.

In einer Stichprobe von 400 Einträgen waren 359 „Indoor", darunter Sachen wie
„Bootshaus DJ Contest". Ungefiltert hätten rund 1.800 Clubnächte die Liste
geflutet. Übernommen wird nur, was sich als Festival zu erkennen gibt: am Namen
oder daran, dass es draußen stattfindet.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, land_code
from ..kern.text import KNOPFBESCHRIFTUNG, clean
from ..netz import Abrufer, sitemap_adressen, soup
from .basis import Quelle

WF = "https://wannafest.com"

DRAUSSEN = {"outdoor", "buiten", "draussen", "draußen", "strand", "beach",
            "boot", "park"}
FESTIVALWORT = re.compile(r"(?i)festival|open ?air|openair|\bfest\b|"
                          r"weekender|\bdagen\b|\bdays\b|\bfestivals\b")


def land_und_ort(rest: str) -> tuple[str, str]:
    """„Austria Festivalterrein Salzburgring": erst das Land, dann die Spielstätte.

    Das Land kann aus mehreren Wörtern bestehen („United Kingdom"), deshalb von
    lang nach kurz probiert.
    """
    woerter = rest.split()
    for laenge in (3, 2, 1):
        code = land_code(" ".join(woerter[:laenge]))
        if ist_land(code):
            return code, clean(" ".join(woerter[laenge:]))
    return (land_code(" ".join(woerter[:2])) if woerter else ""), ""


class WannaFest(Quelle):
    name = "wannafest"
    startseite = WF
    zweck = "Elektronisches, Benelux"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Die Sitemap nennt die Serveradresse statt des Namens — deshalb ersetzt."""
        xml = netz.fetch(f"{WF}/sitemaps/festivals-1.xml")
        if not xml:
            netz.melde("wannafest: Sitemap nicht ladbar")
            return []
        pfade = {re.sub(r"^https?://[^/]+", "", loc) for loc in sitemap_adressen(xml)}
        return [WF + p for p in pfade if re.fullmatch(r"/festivals/[a-z0-9\-]+", p)]

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        titel = clean(s.title.get_text()) if s.title else ""
        name = re.sub(r"\s*[-–|]\s*WannaFest\s*$", "", titel).strip()
        if not name:
            return None

        flach = clean(s.get_text(" ", strip=True))
        dm = re.search(r"Date\s+(\w+ \d{1,2}, \d{4})[^A-Za-z]*(?:to\s+(\w+ \d{1,2}, \d{4}))?",
                       flach)
        von = zeit.aus_englisch(dm.group(1)) if dm else None
        bis = zeit.aus_englisch(dm.group(2)) if dm and dm.group(2) else None

        # „Location Plainfeld, Austria Festivalterrein Salzburgring Place Type"
        lm = re.search(r"Location\s+([^,]{2,40}),\s*(.*?)\s*"
                       r"(?:Place Type|Website|Past events)", flach)
        land, spielstaette = land_und_ort(clean(lm.group(2))) if lm else ("", "")
        if not ist_land(land):
            return None

        art = re.search(r"Place Type\s+([A-Za-zÄÖÜäöü]+)", flach)
        draussen = (art.group(1).casefold() in DRAUSSEN) if art else False
        if not draussen and not FESTIVALWORT.search(name):
            return None

        webseite = ""
        for a in s.find_all("a", href=True):
            if "official" in clean(a.get_text()).lower() and a["href"].startswith("http"):
                webseite = a["href"].strip()
                break

        brauchbar = (len(spielstaette) <= 60
                     and not KNOPFBESCHRIFTUNG.match(spielstaette))
        return fund(
            self.name, url, name,
            von=von, bis=bis,
            stadt=clean(lm.group(1)) if lm else "", land=land,
            ort=spielstaette if brauchbar else "",
            webseite=webseite,
        )
