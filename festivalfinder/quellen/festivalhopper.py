"""festivalhopper.de — Sitemap, der Jahrgang steht in der Adresse."""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, land_code
from ..kern.text import clean, valid_band
from ..netz import Abrufer, sitemap_adressen, soup
from .basis import Quelle, erster_link, felder, jahr_aus, ohne_jahr

FH = "https://www.festivalhopper.de"

#: „28. Summer Breeze 18.08.2027 (Mi) - 21.08.2027 (Sa)"
TERMIN = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s*\(\w{2}\)\s*-\s*(\d{2}\.\d{2}\.\d{4})")

FELDER = {
    "genre":    r"Musikart:[^A-Za-z0-9]*(.*?)\s*(?:Region:|Festivalort:|Besucher:)",
    "region":   r"Region:[^A-Za-z0-9]*(.*?)\s*(?:Festivalort:|Besucher:|Tickets:)",
    "ort":      r"Festivalort:[^A-Za-z0-9]*(.*?)\s*(?:Besucher:|Tickets:|Infos)",
    # Dicht am Wort: „Besucher:[^0-9]*" sprang über ganze Absätze und holte
    # die nächste Ziffer der Seite — auf Seiten mit „Besucherinformationen"
    # ergab das Zahlen mit 66 Stellen.
    "besucher": r"Besucher:\s{0,3}([\d.]{1,9})",
    "preis":    r"Tickets:[^A-Za-z0-9]*(.*?)\s*(?:Infos zum|Anfahrt|Lineup)",
}

LEER = re.compile(r"(?i)^(unbekannt|keine angabe|-)$")


class FestivalHopper(Quelle):
    name = "festivalhopper"
    startseite = FH
    zweck = "deutschsprachig, Lineups als Verweise"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        if not (xml := netz.fetch(f"{FH}/sitemap-festivals.xml")):
            netz.melde("festivalhopper: Sitemap nicht ladbar")
            return []
        muster = re.compile(rf"{FH}/festival/([a-z0-9\-]+?)-((?:19|20)\d{{2}})")
        return [loc for loc in sitemap_adressen(xml)
                if (m := muster.fullmatch(loc)) and int(m.group(2)) >= seit]

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        h1 = s.find("h1")
        if not (roh := clean(h1.get_text()) if h1 else ""):
            return None
        name = ohne_jahr(roh)

        flach = clean(s.get_text(" ", strip=True))
        werte = felder(flach, FELDER, LEER)

        # „Bayern , 🇩🇪 Deutschland" — das Land steht hinten, mit Flagge davor
        land = land_code(clean(re.sub(r"[^\w ÄÖÜäöüß-]", " ",
                                      werte.get("region", "").split(",")[-1])))
        if land and not ist_land(land):
            return None                       # „Bayern" ist kein Land

        preis = werte.get("preis", "")
        tm = TERMIN.search(flach)
        von = zeit.aus_deutsch(tm.group(1)) if tm else None
        return fund(
            self.name, url, name,
            von=von, bis=zeit.aus_deutsch(tm.group(2)) if tm else None,
            jahr=jahr_aus(roh),
            # „91550 Dinkelsbühl", „CH-8152 Glattbrugg", „RG2 Reading": die
            # Postleitzahl löst fund()
            stadt=werte.get("ort", ""), land=land,
            preis=preis if re.search(r"\d", preis) else "",
            webseite=erster_link(s, ausser="festivalhopper", ziel_im_text=True,
                                 weg=r"openstreetmap|facebook|instagram|youtube|"
                                     r"twitter|ticket"),
            genre=werte.get("genre", ""), besucher=werte.get("besucher", ""),
            hinweis="" if von else "Termin noch nicht veröffentlicht",
            # Bandkarten liegen unter /bands/karten/; kürzere /bands/-Adressen
            # sind Menüpunkte
            lineup=[clean(a.get_text()) for a in s.find_all("a", href=True)
                    if "/bands/karten/" in a["href"] and valid_band(a.get_text())],
        )
