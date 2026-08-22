"""jambase.com — Nordamerika, mit vollständigen Lineups.

Die Sitemap ist nach Monaten geteilt, der Jahrgang steht am Ende der Adresse
(„/festival/the-yarnival-2026"). Danach wird gefiltert, sonst holte der Lauf
26.000 Seiten, von denen die meisten vergangene Jahrgänge sind.

Diese Quelle bat den ersten weltweiten Lauf 1.575-mal um Ruhe (429) — sie ist
der Grund für die Bremse in `netz.abrufer`.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import zahl_oder_nichts
from ..kern.text import clean, valid_band
from ..netz import Abrufer, erstes_objekt, json_ld_events, sitemap_adressen, soup
from .basis import Quelle

JB = "https://www.jambase.com"

#: Adressen, die keine offizielle Festivalseite sind
KEINE_SEITE = re.compile(
    r"(?i)facebook|twitter|x\.com|instagram|tiktok|youtube|spotify|google\.|"
    r"jambase|ticketmaster|seetickets|eventbrite|theticketing|axs\.com|"
    r"bandsintown|linktr\.ee")


class JamBase(Quelle):
    name = "jambase"
    startseite = JB
    zweck = "Nordamerika, mit vollen Lineups"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        index = sitemap_adressen(netz.fetch(f"{JB}/sitemap.xml"))
        karten = [k for k in index if "pt-festival" in k]
        if not karten:
            netz.melde(f"Sitemap ohne Festivalkarten: {JB}")
            return []
        adressen: set[str] = set()
        for karte in karten:
            for u in sitemap_adressen(netz.fetch(karte)):
                jahr = re.search(r"-(\d{4})/?$", u)
                if jahr and int(jahr.group(1)) >= seit:
                    adressen.add(u)
        return sorted(adressen)

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        for d in json_ld_events(html):
            name = clean(str(d.get("name", "")))
            if not name:
                continue
            platz = erstes_objekt(d.get("location"))
            anschrift = erstes_objekt(platz.get("address"))
            geo = erstes_objekt(platz.get("geo"))
            acts = [clean(str(p.get("name", ""))) for p in (d.get("performer") or [])
                    if isinstance(p, dict)]
            return fund(
                self.name, url, name,
                von=zeit.aus_iso(d.get("startDate")),
                bis=zeit.aus_iso(d.get("endDate")),
                stadt=clean(str(anschrift.get("addressLocality", ""))),
                # Region statt Land: „NY" gehört zu US, nicht zu Norwegen
                land=str(anschrift.get("addressCountry", "")),
                ort=clean(str(platz.get("name", ""))),
                plz=clean(str(anschrift.get("postalCode", ""))),
                lat=zahl_oder_nichts(geo.get("latitude")),
                lon=zahl_oder_nichts(geo.get("longitude")),
                webseite=self._webseite(html),
                preis="Eintritt frei" if d.get("isAccessibleForFree") is True else "",
                lineup=[b for b in acts if valid_band(b)],
                abgesagt="cancel" in str(d.get("eventStatus", "")).lower(),
            )
        return None

    def _webseite(self, html: str) -> str:
        """Die offizielle Seite unter den ausgehenden Verweisen."""
        for a in soup(html).find_all("a", href=True):
            ziel = a["href"].strip()
            if ziel.startswith("http") and not KEINE_SEITE.search(ziel):
                return ziel
        return ""
