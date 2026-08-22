"""festivalhopper.de — Sitemap, der Jahrgang steht in der Adresse."""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, land_code
from ..kern.text import clean, valid_band
from ..netz import Abrufer, sitemap_adressen, soup
from .basis import Quelle

FH = "https://www.festivalhopper.de"

#: „28. Summer Breeze 18.08.2027 (Mi) - 21.08.2027 (Sa)"
TERMIN = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s*\(\w{2}\)\s*-\s*(\d{2}\.\d{2}\.\d{4})")

FELDER = {
    "genre":    r"Musikart:[^A-Za-z0-9]*(.*?)\s*(?:Region:|Festivalort:|Besucher:)",
    "region":   r"Region:[^A-Za-z0-9]*(.*?)\s*(?:Festivalort:|Besucher:|Tickets:)",
    "ort":      r"Festivalort:[^A-Za-z0-9]*(.*?)\s*(?:Besucher:|Tickets:|Infos)",
    # Dicht am Wort: „Besucher:[^0-9]*" sprang über ganze Absätze hinweg und
    # holte die nächste Ziffer irgendwo auf der Seite — auf Seiten mit
    # „Besucherinformationen" wurden daraus Zahlen mit 66 Stellen.
    "besucher": r"Besucher:\s{0,3}([\d.]{1,9})",
    "preis":    r"Tickets:[^A-Za-z0-9]*(.*?)\s*(?:Infos zum|Anfahrt|Lineup)",
}


class FestivalHopper(Quelle):
    name = "festivalhopper"
    startseite = FH
    zweck = "deutschsprachig, Lineups als Verweise"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        xml = netz.fetch(f"{FH}/sitemap-festivals.xml")
        if not xml:
            netz.melde("festivalhopper: Sitemap nicht ladbar")
            return []
        muster = re.compile(rf"{FH}/festival/([a-z0-9\-]+?)-((?:19|20)\d{{2}})")
        return [loc for loc in sitemap_adressen(xml)
                if (m := muster.fullmatch(loc)) and int(m.group(2)) >= seit]

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        h1 = s.find("h1")
        roh = clean(h1.get_text()) if h1 else ""
        if not roh:
            return None
        jm = re.search(r"\b(20\d{2})\b", roh)
        name = re.sub(r"\s*\b20\d{2}\b\s*$", "", roh).strip()
        if not name:
            return None

        flach = clean(s.get_text(" ", strip=True))
        tm = TERMIN.search(flach)

        feld: dict[str, str] = {}
        for schluessel, muster in FELDER.items():
            m = re.search(muster, flach, re.S)
            wert = clean(m.group(1)) if m else ""
            if wert and wert.lower() not in ("unbekannt", "keine angabe", "-"):
                feld[schluessel] = wert

        # „Bayern , 🇩🇪 Deutschland" — das Land steht hinten, mit Flaggenzeichen
        # davor, das kein Buchstabe ist.
        land_roh = feld.get("region", "").split(",")[-1]
        land = land_code(clean(re.sub(r"[^\w ÄÖÜäöüß-]", " ", land_roh)))
        if land and not ist_land(land):
            return None                       # „Bayern" ist kein Land

        # „91550 Dinkelsbühl", aber auch „CH-8152 Glattbrugg" oder „A-1010 Wien"
        ort_roh = feld.get("ort", "")
        plz_m = re.match(r"\s*(?:[A-Z]{1,2}-)?(\d{4,5})\b\s*(.*)$", ort_roh)

        preis = feld.get("preis", "")
        if preis and not re.search(r"\d", preis):
            preis = ""

        # Bandnamen stehen als einzelne Verweise. Die Bandkarten liegen unter
        # /bands/karten/; die kürzeren /bands/-Adressen sind Menüpunkte.
        lineup = [clean(a.get_text()) for a in s.find_all("a", href=True)
                  if "/bands/karten/" in a["href"] and valid_band(a.get_text())]

        von = zeit.aus_deutsch(tm.group(1)) if tm else None
        return fund(
            self.name, url, name,
            von=von, bis=zeit.aus_deutsch(tm.group(2)) if tm else None,
            jahr=jm.group(1) if jm else "",
            stadt=clean(plz_m.group(2)) if plz_m else ort_roh,
            land=land,
            plz=plz_m.group(1) if plz_m else "",
            preis=preis, webseite=self._webseite(s), genre=feld.get("genre", ""),
            besucher=feld.get("besucher", ""),
            hinweis="" if von else "Termin noch nicht veröffentlicht",
            lineup=lineup,
        )

    def _webseite(self, s) -> str:
        for a in s.find_all("a", href=True):
            ziel = a["href"].strip()
            if not ziel.startswith("http") or "festivalhopper" in ziel:
                continue
            if re.search(r"(?i)openstreetmap|facebook|instagram|youtube|twitter|ticket",
                         ziel):
                continue
            if clean(a.get_text()).lower().replace("www.", "") in ziel.lower():
                return ziel
        return ""
