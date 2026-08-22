"""festival-alarm.com — Jahresseiten und Regionsseiten.

Führt bei den meisten Festivals kein Lineup („keine Daten"), liefert dafür
Spielstätte, Besucherzahl und Preise. Die Werte stehen über mehrere Zeilen
verteilt, deshalb wird der Text zu einer Zeile geglättet und jedes Feld bis zur
nächsten bekannten Beschriftung gelesen.
"""

import re
from urllib.parse import urljoin

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land
from ..kern.text import clean, valid_band
from ..netz import Abrufer, soup
from ..pfade import JAHRE
from .basis import Quelle

FA = "https://www.festival-alarm.com"

FELDER = {
    "preis":     r"Festivalticket \(ab\):\s*(.*?)\s*(?:Tagesticket|Ticketshop|Teilnehmer)",
    "stadt":     r"Stadt:\s*(.*?)\s*(?:Bundesland:|Land:)",
    "land":      r"\bLand:\s*(.*?)\s*(?:Veranstaltungsplatz|Wo:|Örtlichkeit|Camping)",
    "genre":     r"Genres:\s*(.*?)\s*(?:Gründung|Festivalausgabe|Besucher)",
    "besucher":  r"Besucher:\s*(.*?)\s*(?:Sonstiges|Weiterführende|Webseite)",
    "ort_name":  r"Örtlichkeit:\s*(.*?)\s*(?:Camping|Künstler|Anreise)",
    "acts":      r"Künstler:\s*(.*?)\s*(?:Anreise|Wie komme)",
}

LEER = re.compile(r"^(keine daten|unbekannt|-|)$", re.I)


class FestivalAlarm(Quelle):
    name = "festivalalarm"
    startseite = FA
    zweck = "Spielstätte, Besucherzahl und Preise"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Jahresseiten; die Regionsseiten fangen auf, was dort fehlt."""
        links: dict[str, None] = {}
        for jahr in JAHRE:
            if jahr < seit:
                continue
            html = netz.fetch(f"{FA}/Festivals-{jahr}")
            if not html:
                continue
            for href in re.findall(rf'href="(/Festivals-{jahr}/[^"]+)"', html):
                links[urljoin(FA, href)] = None

            for pfad, code in set(re.findall(
                    rf'href="(/festival/region/[^"]+/{jahr}/([A-Z]{{2}}))"', html)):
                if not ist_land(code):
                    continue
                for href in re.findall(rf'href="(/Festivals-{jahr}/[^"]+)"',
                                       netz.fetch(urljoin(FA, pfad)) or ""):
                    links.setdefault(urljoin(FA, href), None)
        return list(links)

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        h1 = s.find("h1")
        roh = clean(h1.get_text(" ", strip=True)) if h1 else ""
        if not roh:
            return None

        # „Baltic Open Air 19.08. - 21.08.2026"
        dm = re.search(r"(\d{2}\.\d{2}\.)\s*-\s*(\d{2}\.\d{2}\.\d{4})|(\d{2}\.\d{2}\.\d{4})",
                       roh)
        von = bis = None
        if dm and dm.group(2):
            von = zeit.aus_deutsch(dm.group(1) + dm.group(2)[-4:])
            bis = zeit.aus_deutsch(dm.group(2))
        elif dm and dm.group(3):
            von = bis = zeit.aus_deutsch(dm.group(3))
        name = re.sub(r"[\s\-–|]+$", "", clean(roh[:dm.start()]) if dm else roh)
        if not name:
            return None

        flach = clean(s.get_text(" ", strip=True))
        feld: dict[str, str] = {}
        for schluessel, muster in FELDER.items():
            m = re.search(muster, flach, re.S)
            wert = clean(m.group(1)) if m else ""
            if wert and not LEER.match(wert):
                feld[schluessel] = wert

        stadt_roh = feld.get("stadt", "")
        plz_m = re.match(r"\s*(\d{4,5})\b", stadt_roh)

        preis = feld.get("preis", "")
        if preis:
            preis = clean(preis.replace("ca.", "").replace("€", "EUR"))
            preis = "" if not re.search(r"\d", preis) else preis
            if preis and not preis.lower().startswith("ab"):
                preis = f"ab {preis}"

        return fund(
            self.name, url, name,
            von=von, bis=bis,
            stadt=clean(re.sub(r"^\d{4,5}\s*", "", stadt_roh)),
            land=feld.get("land", ""),
            ort=feld.get("ort_name", ""),
            plz=plz_m.group(1) if plz_m else "",
            preis=preis, webseite=self._webseite(s), genre=feld.get("genre", ""),
            besucher=feld.get("besucher", ""),
            lineup=[clean(b) for b in feld.get("acts", "").split(",") if valid_band(b)],
        )

    def _webseite(self, s) -> str:
        for block in s.find_all(["li", "div", "p"]):
            if "Webseite" not in block.get_text():
                continue
            a = block.find("a", href=True)
            if a and a["href"].startswith("http") and "awin1.com" not in a["href"] \
                    and "festival-alarm" not in a["href"]:
                return a["href"].strip()
        return ""
