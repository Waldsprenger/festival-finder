"""festivalabroad.com — 3.261 Festivals weltweit, jedes mit Datenblatt.

Die vollständigste der weltweiten Quellen: Termin, Koordinate, offizielle
Adresse, Kapazität und Genres stehen im Datenblatt der Seite.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, zahl_oder_nichts
from ..kern.text import clean
from ..netz import Abrufer, erstes_objekt, json_ld_events, sitemap_adressen, soup
from .basis import Quelle

FB = "https://www.festivalabroad.com"

#: „2000trees – Gloucestershire, United Kingdom 2027"
TITEL = re.compile(r"^(.*?)\s+[–-]\s+(.*?)(?:\s+(\d{4}))?$")


class FestivalAbroad(Quelle):
    name = "festivalabroad"
    startseite = FB
    zweck = "weltweit, mit Koordinaten und Genres"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Alle Festivalseiten aus der Sitemap; der Termin steht erst auf der Seite."""
        index = sitemap_adressen(netz.fetch(f"{FB}/sitemap.xml"))
        if not index:
            netz.melde(f"Sitemap nicht ladbar: {FB}")
            return []
        adressen: set[str] = set()
        for karte in index:
            if not karte.endswith(".xml"):
                continue
            for u in sitemap_adressen(netz.fetch(karte)):
                if re.search(r"/festivals/[^/]+$", u):
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
            angebot = erstes_objekt(d.get("offers"))
            return fund(
                self.name, url, name,
                von=zeit.aus_iso(d.get("startDate")),
                bis=zeit.aus_iso(d.get("endDate")),
                # „Dresden, Germany" — der Ort steht vorn, das Land dahinter
                stadt=clean(str(anschrift.get("addressLocality", ""))).split(",")[0],
                land=str(anschrift.get("addressCountry", "")),
                ort=clean(str(platz.get("name", ""))),
                lat=zahl_oder_nichts(geo.get("latitude")),
                lon=zahl_oder_nichts(geo.get("longitude")),
                webseite=str(d.get("url", "")),
                genre=clean(str(d.get("keywords", ""))),
                besucher=str(d.get("maximumAttendeeCapacity", "") or ""),
                preis="Eintritt frei" if d.get("isAccessibleForFree") is True else "",
                abgesagt="cancel" in str(d.get("eventStatus", "")).lower(),
            )
        return self._ohne_datenblatt(url, html)

    def _ohne_datenblatt(self, url: str, html: str) -> Fund | None:
        """Feste, deren nächster Termin noch aussteht.

        Für sie liefert die Seite kein Datenblatt — alles Nötige steht aber im
        Titel: Name, Ort, Land. Ohne Termin, denn den gibt es noch nicht
        („TBA - last edition: 8 Jul 2026").
        """
        s = soup(html)
        titel = clean(s.title.get_text()) if s.title else ""
        titel = re.sub(r"\s*[|–-]\s*Festival Abroad\s*$", "", titel)
        m = TITEL.match(titel)
        if not m:
            return None
        name = clean(m.group(1))
        ort_land = [t.strip(" .…") for t in (m.group(2) or "").split(",") if t.strip(" .…")]
        if not name or len(ort_land) < 2:
            return None
        # Lange Titel schneidet die Seite mit Auslassungszeichen ab: aus
        # „United States" wird „United State…". Was dann kein Land mehr ergibt,
        # bleibt lieber leer als falsch.
        land = ort_land[-1]
        return fund(self.name, url, name,
                    stadt=ort_land[0], land=land if ist_land(land) else "")
