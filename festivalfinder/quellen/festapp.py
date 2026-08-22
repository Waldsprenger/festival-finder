"""festapp.io — Sitemaps der Festivals und der einzelnen Ausgaben.

Weltweit, mit Datenblatt je Ausgabe. Frankreich, Italien und Spanien sind hier
dichter vertreten als bei den deutschsprachigen Quellen.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.geld import betrag
from ..kern.orte import ist_land, land_code
from ..kern.text import clean, valid_band
from ..netz import Abrufer, erstes_objekt, json_ld_events, sitemap_adressen
from .basis import Quelle

FP = "https://festapp.io"


def acts_aus_datenblatt(d: dict) -> list[str]:
    """performer-Liste eines schema.org-Blocks; Einträge sind Text oder Objekt."""
    namen = []
    for act in (d.get("performer") or []):
        nm = clean(str(act.get("name", "") if isinstance(act, dict) else act))
        if valid_band(nm):
            namen.append(nm)
    return namen


class Festapp(Quelle):
    name = "festapp"
    startseite = FP
    zweck = "Frankreich, Italien, Spanien"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        links: dict[str, None] = {}
        for karte in (f"{FP}/editions/sitemap/0.xml", f"{FP}/festivals/sitemap/0.xml"):
            xml = netz.fetch(karte)
            if not xml:
                netz.melde(f"festapp: {karte} nicht ladbar")
                continue
            for loc in sitemap_adressen(xml):
                m = re.fullmatch(r"https://festapp\.io/festivals/[a-z0-9\-]+(?:/(\d{4}))?",
                                 loc)
                if m and not (m.group(1) and int(m.group(1)) < seit):
                    links[loc] = None
        return list(links)

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        ereignisse = json_ld_events(html)
        if not ereignisse:
            return None
        d = ereignisse[0]
        roh = clean(str(d.get("name", "")))
        if not roh:
            return None
        jm = re.search(r"\b(20\d{2})\b", roh)

        platz = erstes_objekt(d.get("location"))
        adresse = erstes_objekt(platz.get("address"))
        # „Dorfstrasse 22, 3457 Sumiswald, Switzerland": Die Anschrift beginnt
        # oft mit der Straße, deshalb zählt der Ortsname aus location.name. Das
        # Land steht zuverlässig am Ende.
        teile = [t.strip() for t in clean(str(adresse.get("addressLocality", ""))).split(",")
                 if t.strip()]
        spielstaette = clean(str(platz.get("name", "")))
        stadt = spielstaette
        if not stadt and teile:
            # ohne location.name der vorletzte Teil, ohne führende Postleitzahl
            stadt = re.sub(r"^[A-Z]{0,2}[-\s]?\d[\w\s-]*?\s+", "",
                           teile[-2] if len(teile) > 1 else teile[0])
        land = land_code(teile[-1]) if len(teile) > 1 else ""
        if not ist_land(land):
            return None                       # ohne erkennbares Land kein Eintrag

        angebot = erstes_objekt(d.get("offers"))
        wert = betrag(str(angebot.get("price", "")))
        preis = ("" if wert is None else
                 f"ab {angebot.get('priceCurrency', 'EUR')} "
                 + f"{wert:.2f}".replace(".", ","))

        return fund(
            self.name, url,
            re.sub(r"\s*\b20\d{2}\b\s*$", "", roh).strip() or roh,
            von=zeit.aus_iso(d.get("startDate")), bis=zeit.aus_iso(d.get("endDate")),
            jahr=jm.group(1) if jm else "",
            stadt=stadt, land=land, ort=spielstaette,
            plz=clean(str(adresse.get("postalCode", ""))),
            preis=preis, webseite=clean(str(angebot.get("url", ""))),
            abgesagt=str(d.get("eventStatus", "")).endswith("EventCancelled"),
            lineup=acts_aus_datenblatt(d),
        )
