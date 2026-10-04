"""festivalflyer.com — nur die Startseite.

Mehr ist nicht erreichbar: Die Sitemap enthält ausschließlich Artikel (30.937
Stück), die Übersicht unter /events/ wird im Browser zusammengesetzt, und die
Detailseiten verweisen nur aufeinander. Die Startseite nannte dafür ein Dutzend
kommende Festivals mit vollem Datenblatt — über das Jahr wechselten sie durch.

Seit Oktober 2026 ruht die Quelle. Die Startseite nennt nur noch zwei
Festivals, und ihr Datenblatt trägt kein Land mehr, bei einem nicht einmal
einen Ort („Queens Hall"). Die Detailseiten stehen sogar noch auf 2023. Seit
September lieferte der Lauf deshalb jeden Tag null Funde und die Warnung dazu.
Einmal im Monat sieht der Lauf auf der Startseite nach, ob sie wieder
kommende Festivals mit Land nennt.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.orte import ist_land, land_code
from ..kern.text import clean, feld, valid_band
from ..netz import Abrufer, erstes_objekt, json_ld_events
from .basis import Quelle

FL = "https://festivalflyer.com"


class FestivalFlyer(Quelle):
    name = "festivalflyer"
    startseite = FL
    zweck = "Großbritannien und Irland"
    ruht = ("nennt seit September 2026 nur noch zwei Festivals, ohne Land; "
            "die Detailseiten stehen auf 2023")

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
        roh = feld(d.get("name"))
        if not roh:
            return None
        jm = re.search(r"\b(20\d{2})\b", roh)

        land = self._land(d)
        if not land:
            return None
        # „Fernhill Farm, Cheddar Road, BS40 6LD Compton Martin, United Kingdom"
        platz = erstes_objekt(d.get("location"))
        teile = [t.strip() for t in feld(platz.get("name")).split(",") if t.strip()]
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
            abgesagt=feld(d.get("eventStatus")).endswith("EventCancelled"),
            lineup=self._lineup(d),
        )

    def _land(self, d: dict) -> str:
        """Das Land einer Veranstaltung: der letzte Teil der Anschrift im
        Ortsnamen. Leer, wenn dort keines steht."""
        platz = erstes_objekt(d.get("location"))
        teile = [t.strip() for t in feld(platz.get("name")).split(",") if t.strip()]
        land = land_code(teile[-1]) if len(teile) > 1 else ""
        return land if ist_land(land) else ""

    def wieder_offen(self, netz: Abrufer, seit: int) -> bool | None:
        """Nennt die Startseite wieder ein kommendes Festival mit Land?

        Eine Anfrage: Die Startseite trägt selbst ein Datenblatt je Festival.
        Aus dem Zwischenspeicher zählt sie nicht — dort kann eine alte liegen.
        """
        html = netz.fetch(f"{FL}/")
        if html is None or not netz.hat_geholt([FL]):
            return None
        return any((von := zeit.aus_iso(d.get("startDate"))) and von.year >= seit
                   and self._land(d) for d in json_ld_events(html))

    def _lineup(self, d: dict) -> list[str]:
        """Die Beschreibung führt das Lineup, mit Schrägstrich getrennt."""
        beschreibung = re.sub(r"<[^>]+>", " ", feld(d.get("description")))
        if "/" not in beschreibung:
            return []
        namen = []
        for teil in beschreibung.split("/"):
            nm = re.sub(r"(?i)^(line ?up so far\.?|lineup:?)\s*", "",
                        clean(teil).strip("*").strip())
            if valid_band(nm) and len(nm) <= 60:
                namen.append(nm)
        return namen
