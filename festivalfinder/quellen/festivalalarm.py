"""festival-alarm.com — Jahresseiten und Regionsseiten.

Führt bei den meisten Festivals kein Lineup („keine Daten"), liefert dafür
Spielstätte, Besucherzahl und Preise. Die Werte stehen über mehrere Zeilen
verteilt; gelesen wird jedes Feld bis zur nächsten bekannten Beschriftung.
"""

import re
from urllib.parse import urljoin

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land
from ..kern.text import clean, valid_band
from ..netz import Abrufer, soup
from ..pfade import JAHRE
from .basis import Quelle, felder

FA = "https://www.festival-alarm.com"

FELDER = {
    "preis":    r"Festivalticket \(ab\):\s*(.*?)\s*(?:Tagesticket|Ticketshop|Teilnehmer)",
    "stadt":    r"Stadt:\s*(.*?)\s*(?:Bundesland:|Land:)",
    "land":     r"\bLand:\s*(.*?)\s*(?:Veranstaltungsplatz|Wo:|Örtlichkeit|Camping)",
    "genre":    r"Genres:\s*(.*?)\s*(?:Gründung|Festivalausgabe|Besucher)",
    "besucher": r"Besucher:\s*(.*?)\s*(?:Sonstiges|Weiterführende|Webseite)",
    "ort":      r"Örtlichkeit:\s*(.*?)\s*(?:Camping|Künstler|Anreise)",
    "acts":     r"Künstler:\s*(.*?)\s*(?:Anreise|Wie komme)",
}

LEER = re.compile(r"^(keine daten|unbekannt|-|)$", re.I)

#: „Baltic Open Air 19.08. - 21.08.2026" oder ein einzelner Tag
TERMIN = re.compile(r"(\d{2}\.\d{2}\.)\s*-\s*(\d{2}\.\d{2}\.\d{4})|(\d{2}\.\d{2}\.\d{4})")


def acts(roh: str) -> list[str]:
    """Die Künstler — sofern das Feld eine Liste ist und keine Beschreibung.

    Manche Seiten setzen den Beschreibungstext ins Künstlerfeld. Beim Honey
    Lake Sessions standen so „sowie einem Falafel und Kimchi Stand" und „denn
    es ist unmöglich" als Bands in der Suche. Ein Satzbruchstück beginnt klein
    und hat mehrere Wörter; ist das ein Drittel der Einträge, ist es Prosa.
    """
    teile = [clean(t) for t in roh.split(",") if clean(t)]
    prosa = sum(1 for t in teile if t[:1].islower() and len(t.split()) >= 3)
    if not teile or prosa * 10 >= len(teile) * 3:
        return []
    return [t for t in teile if valid_band(t)]


class FestivalAlarm(Quelle):
    name = "festivalalarm"
    startseite = FA
    zweck = "Spielstätte, Besucherzahl und Preise"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Jahresseiten; die Regionsseiten fangen auf, was dort fehlt."""
        links: dict[str, None] = {}
        for jahr in (j for j in JAHRE if j >= seit):
            if not (html := netz.fetch(f"{FA}/Festivals-{jahr}")):
                continue
            seite = re.compile(rf'href="(/Festivals-{jahr}/[^"]+)"')
            links.update(dict.fromkeys(urljoin(FA, h) for h in seite.findall(html)))
            for pfad, code in set(re.findall(
                    rf'href="(/festival/region/[^"]+/{jahr}/([A-Z]{{2}}))"', html)):
                if ist_land(code):
                    for h in seite.findall(netz.fetch(urljoin(FA, pfad)) or ""):
                        links.setdefault(urljoin(FA, h), None)
        return list(links)

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        h1 = s.find("h1")
        if not (roh := clean(h1.get_text(" ", strip=True)) if h1 else ""):
            return None

        von = bis = None
        if (dm := TERMIN.search(roh)) and dm.group(2):
            von = zeit.aus_deutsch(dm.group(1) + dm.group(2)[-4:])
            bis = zeit.aus_deutsch(dm.group(2))
        elif dm:
            von = bis = zeit.aus_deutsch(dm.group(3))
        if not (name := re.sub(r"[\s\-–|]+$", "", clean(roh[:dm.start()]) if dm else roh)):
            return None

        werte = felder(clean(s.get_text(" ", strip=True)), FELDER, LEER)
        preis = clean(werte.get("preis", "").replace("ca.", "").replace("€", "EUR"))
        if not re.search(r"\d", preis):
            preis = ""
        elif not preis.lower().startswith("ab"):
            preis = f"ab {preis}"

        return fund(
            self.name, url, name, von=von, bis=bis,
            # „97209 Veitshöchheim", „CA-92201 Indio": die Postleitzahl löst fund()
            stadt=werte.get("stadt", ""), land=werte.get("land", ""),
            ort=werte.get("ort", ""), preis=preis, webseite=self._webseite(s),
            genre=werte.get("genre", ""), besucher=werte.get("besucher", ""),
            lineup=acts(werte.get("acts", "")),
        )

    def _webseite(self, s) -> str:
        """Der Verweis im Block mit der Beschriftung „Webseite" — ohne
        Partnerlinks und ohne die Quelle selbst."""
        for block in s.find_all(["li", "div", "p"]):
            if "Webseite" not in block.get_text():
                continue
            a = block.find("a", href=True)
            if a and a["href"].startswith("http") and "awin1.com" not in a["href"] \
                    and "festival-alarm" not in a["href"]:
                return a["href"].strip()
        return ""
