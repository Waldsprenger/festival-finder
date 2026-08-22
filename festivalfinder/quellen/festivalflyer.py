"""festivalflyer.com — nur die Startseite.

Mehr ist nicht erreichbar: Die Sitemap enthält ausschließlich Artikel (30.937
Stück), die Übersicht unter /events/ wird im Browser zusammengesetzt, und die
Detailseiten verweisen nur aufeinander. Die Startseite nennt dafür ein Dutzend
kommende Festivals mit vollem Datenblatt — über das Jahr wechseln sie durch.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, land_code
from ..kern.text import clean, valid_band
from ..netz import Abrufer, erstes_objekt, json_ld_events
from .basis import Quelle

FL = "https://festivalflyer.com"


class FestivalFlyer(Quelle):
    name = "festivalflyer"
    startseite = FL
    zweck = "Großbritannien und Irland"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        html = netz.fetch(f"{FL}/")
        if not html:
            netz.melde("festivalflyer: Startseite nicht ladbar")
            return []
        return list({u.rstrip("/") + "/": None
                     for u in re.findall(rf"{FL}/events/[a-z0-9\-]+/", html)})

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        ereignisse = json_ld_events(html)
        if not ereignisse:
            return None
        d = ereignisse[0]
        roh = clean(str(d.get("name", "")))
        if not roh:
            return None
        jm = re.search(r"\b(20\d{2})\b", roh)

        # „Fernhill Farm, Cheddar Road, BS40 6LD Compton Martin, United Kingdom"
        platz = erstes_objekt(d.get("location"))
        anschrift = clean(str(platz.get("name", "")))
        teile = [t.strip() for t in anschrift.split(",") if t.strip()]
        land = land_code(teile[-1]) if len(teile) > 1 else ""
        if not ist_land(land):
            return None
        # britische Postleitzahlen stehen vor dem Ort: „BS40 6LD Compton Martin"
        stadt_roh = teile[-2] if len(teile) > 1 else ""
        spielstaette = teile[0] if len(teile) > 2 else ""

        return fund(
            self.name, url,
            re.sub(r"\s*\b20\d{2}\b\s*$", "", roh).strip() or roh,
            von=zeit.aus_iso(d.get("startDate")), bis=zeit.aus_iso(d.get("endDate")),
            jahr=jm.group(1) if jm else "",
            stadt=clean(re.sub(r"^[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d?[A-Z]{0,2}\s+", "",
                               stadt_roh)),
            land=land,
            ort=spielstaette if len(spielstaette) <= 60 else "",
            abgesagt=str(d.get("eventStatus", "")).endswith("EventCancelled"),
            lineup=self._lineup(d),
        )

    def _lineup(self, d: dict) -> list[str]:
        """Die Beschreibung führt das Lineup, mit Schrägstrich getrennt."""
        beschreibung = re.sub(r"<[^>]+>", " ", str(d.get("description", "")))
        if "/" not in beschreibung:
            return []
        namen = []
        for teil in beschreibung.split("/"):
            nm = re.sub(r"(?i)^(line ?up so far\.?|lineup:?)\s*", "",
                        clean(teil).strip("*").strip())
            if valid_band(nm) and len(nm) <= 60:
                namen.append(nm)
        return namen
