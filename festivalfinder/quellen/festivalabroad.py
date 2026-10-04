"""festivalabroad.com — gut 3.000 Festivals weltweit, fast jedes mit Datenblatt.

Die vollständigste der weltweiten Quellen: Termin, Koordinate, Kapazität und
Genres stehen im Datenblatt der Seite. Feste ohne neuen Termin haben keins;
dann trägt der Seitentitel Name, Ort und Land.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, zahl_oder_nichts
from ..kern.text import clean, feld
from ..netz import Abrufer, erstes_objekt, json_ld_events, sitemap_adressen, soup
from .basis import Quelle

FB = "https://www.festivalabroad.com"

#: „2000trees – Gloucestershire, United Kingdom 2027"
TITEL = re.compile(r"^(.*?)\s+[–-]\s+(.*?)(?:\s+(\d{4}))?$")
#: Verweis auf die Länderseite, beschriftet mit dem Ort: „Bend, United States"
LAENDERSEITE = re.compile(r"^/festivals-in-")


class FestivalAbroad(Quelle):
    name = "festivalabroad"
    startseite = FB
    zweck = "weltweit, mit Koordinaten und Genres"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Alle Festivalseiten aus der Sitemap; der Termin steht erst auf der Seite."""
        if not (index := sitemap_adressen(netz.fetch(f"{FB}/sitemap.xml"))):
            netz.melde(f"Sitemap nicht ladbar: {FB}")
            return []
        return sorted({u for karte in index if karte.endswith(".xml")
                       for u in sitemap_adressen(netz.fetch(karte))
                       if re.search(r"/festivals/[^/]+$", u)})

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        for d in json_ld_events(html):
            if not (name := feld(d.get("name"))):
                continue
            platz = erstes_objekt(d.get("location"))
            anschrift = erstes_objekt(platz.get("address"))
            geo = erstes_objekt(platz.get("geo"))
            # Das Datenblatt nennt als `url` bei 85 Festivals die eigene Seite
            # bei festivalabroad — eine offizielle Adresse ist das nicht.
            webseite = feld(d.get("url"))
            return fund(
                self.name, url, name,
                von=zeit.aus_iso(d.get("startDate")), bis=zeit.aus_iso(d.get("endDate")),
                # „Dresden, Germany" — der Ort steht vorn, das Land dahinter
                stadt=feld(anschrift.get("addressLocality")).split(",")[0],
                land=feld(anschrift.get("addressCountry")),
                ort=feld(platz.get("name")),
                lat=zahl_oder_nichts(geo.get("latitude")),
                lon=zahl_oder_nichts(geo.get("longitude")),
                webseite="" if "festivalabroad.com" in webseite else webseite,
                genre=feld(d.get("keywords")),
                besucher=feld(d.get("maximumAttendeeCapacity")),
                preis="Eintritt frei" if d.get("isAccessibleForFree") is True else "",
                abgesagt="cancel" in feld(d.get("eventStatus")).lower(),
            )
        return self._ohne_datenblatt(url, html)

    def _ohne_datenblatt(self, url: str, html: str) -> Fund | None:
        """Feste, deren nächster Termin noch aussteht („TBA - last edition: 8 Jul 2026").

        Seit 2026 lautet der Titel „4 Peaks Music Festival – Dates to Be
        Announced | Bend, Unit…" — so stand es bei allen 145 terminlosen
        Festivals als Ort in den Daten, und keines fand zu seinem datierten
        Eintrag. Vollständig steht der Ort im Verweis auf die Länderseite; der
        Titel hilft, wo der Verweis fehlt.
        """
        s = soup(html)
        titel = re.sub(r"\s*[|–-]\s*Festival Abroad\s*$", "",
                       clean(s.title.get_text()) if s.title else "")
        if not (m := TITEL.match(titel)) or not (name := clean(m.group(1))):
            return None
        ort = next((clean(a.get_text()) for a in s.find_all("a", href=LAENDERSEITE)
                    if "," in a.get_text()), "") or (m.group(2) or "").split("|")[-1]
        teile = [t.strip(" .…") for t in ort.split(",") if t.strip(" .…")]
        if len(teile) < 2:
            return None
        # Ein abgeschnittener Titel macht aus „United States" „United State…";
        # was kein Land mehr ergibt, bleibt lieber leer als falsch.
        return fund(self.name, url, name, stadt=teile[0],
                    land=teile[-1] if ist_land(teile[-1]) else "")
