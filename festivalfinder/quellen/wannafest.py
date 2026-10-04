"""wannafest.com — Sitemap, überwiegend Clubabende.

In einer Stichprobe von 400 Einträgen waren 359 „Indoor", darunter Sachen wie
„Bootshaus DJ Contest". Übernommen wird nur, was sich als Festival zu erkennen
gibt: am Namen oder daran, dass es draußen stattfindet.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, land_code
from ..kern.text import KNOPFBESCHRIFTUNG, clean
from ..netz import Abrufer, sitemap_adressen, soup
from .basis import Quelle, erster_link, ohne_jahr

WF = "https://wannafest.com"

DRAUSSEN = {"outdoor", "buiten", "draussen", "draußen", "strand", "beach", "boot", "park"}
FESTIVALWORT = re.compile(r"(?i)festival|open ?air|openair|\bfest\b|"
                          r"weekender|\bdagen\b|\bdays\b|\bfestivals\b")
_TERMIN = re.compile(r"Date\s+(\w+ \d{1,2}, \d{4})[^A-Za-z]*(?:to\s+(\w+ \d{1,2}, \d{4}))?")
#: „Location Plainfeld, Austria Festivalterrein Salzburgring Place Type"
_ORT = re.compile(r"Location\s+([^,]{2,40}),\s*(.*?)\s*(?:Place Type|Website|Past events)")


def land_und_ort(rest: str) -> tuple[str, str]:
    """„Austria Festivalterrein Salzburgring": erst das Land, dann die
    Spielstätte. Das Land kann mehrere Wörter haben („United Kingdom")."""
    woerter = rest.split()
    for laenge in (3, 2, 1):
        if ist_land(code := land_code(" ".join(woerter[:laenge]))):
            return code, clean(" ".join(woerter[laenge:]))
    return (land_code(" ".join(woerter[:2])) if woerter else ""), ""


class WannaFest(Quelle):
    name = "wannafest"
    startseite = WF
    zweck = "Elektronisches, Benelux"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Die Sitemap nennt die Serveradresse statt des Namens — deshalb ersetzt."""
        if not (xml := netz.fetch(f"{WF}/sitemaps/festivals-1.xml")):
            netz.melde("wannafest: Sitemap nicht ladbar")
            return []
        pfade = {re.sub(r"^https?://[^/]+", "", loc) for loc in sitemap_adressen(xml)}
        return [WF + p for p in pfade if re.fullmatch(r"/festivals/[a-z0-9\-]+", p)]

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        titel = clean(s.title.get_text()) if s.title else ""
        # „Veerplas Festival - 2026 - WannaFest": Seitenname und Jahr fallen weg
        if not (name := ohne_jahr(re.sub(r"\s*[-–|]\s*WannaFest\s*$", "", titel).strip())):
            return None

        flach = clean(s.get_text(" ", strip=True))
        dm = _TERMIN.search(flach)
        lm = _ORT.search(flach)
        land, spielstaette = land_und_ort(clean(lm.group(2))) if lm else ("", "")
        if not ist_land(land):
            return None

        art = re.search(r"Place Type\s+([A-Za-zÄÖÜäöü]+)", flach)
        if not (art and art.group(1).casefold() in DRAUSSEN) and not FESTIVALWORT.search(name):
            return None

        brauchbar = len(spielstaette) <= 60 and not KNOPFBESCHRIFTUNG.match(spielstaette)
        return fund(
            self.name, url, name,
            von=zeit.aus_englisch(dm.group(1)) if dm else None,
            bis=zeit.aus_englisch(dm.group(2)) if dm and dm.group(2) else None,
            stadt=clean(lm.group(1)) if lm else "", land=land,
            ort=spielstaette if brauchbar else "",
            webseite=erster_link(s, text="official"),
        )
