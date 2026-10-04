"""festapp.io — Sitemaps der Festivals und der einzelnen Ausgaben.

Weltweit, mit Datenblatt je Ausgabe. Frankreich, Italien und Spanien sind hier
dichter vertreten als bei den deutschsprachigen Quellen.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.geld import betrag
from ..kern.orte import ist_land, land_code
from ..kern.text import feld, fold, valid_band
from ..netz import Abrufer, erstes_objekt, json_ld_events, sitemap_adressen
from .basis import Quelle, jahr_aus, ohne_jahr, ort_aus_anschrift

FP = "https://festapp.io"
_DETAIL = re.compile(r"https://festapp\.io/festivals/[a-z0-9\-]+(?:/(\d{4}))?")

#: Was in location.name eine Verwaltungseinheit statt eines Ortes ist
REGION = re.compile(
    r"(?i)^(?:england|scotland|wales|northern ireland|unknown)$| city$|shire$|"
    r"\b(?:county|län|region|regi[oó]n|provin[cz]i?[ae]|district|council|"
    r"upravna enota|greater|kommune|municipality|oblast|departamento|landkreis)\b")


def ort_aus(name_im_feld: str, anschrift: str) -> str:
    """Der Ort einer festapp-Ausgabe.

    location.name ist meist der Ort, in jedem zwölften Fall aber eine Region
    („England", „Greater London", „Dalarnas län"). Dann gilt der Ort aus der
    Anschrift („Clitheroe BB7 4LH"). Sonst bleibt location.name — in manchen
    Ländern steht vor dem Land nicht der Ort, sondern die Provinz („Cádiz",
    „Región Metropolitana").
    """
    if name_im_feld and (fold(name_im_feld) in fold(anschrift) or not REGION.search(name_im_feld)):
        return name_im_feld
    return ort_aus_anschrift(anschrift) or name_im_feld


def acts_aus_datenblatt(d: dict) -> list[str]:
    """performer-Liste eines schema.org-Blocks; Einträge sind Text oder Objekt."""
    namen = (feld(a.get("name") if isinstance(a, dict) else a) for a in d.get("performer") or [])
    return [n for n in namen if valid_band(n)]


class Festapp(Quelle):
    name = "festapp"
    startseite = FP
    zweck = "Frankreich, Italien, Spanien"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        links: dict[str, None] = {}
        for karte in (f"{FP}/editions/sitemap/0.xml", f"{FP}/festivals/sitemap/0.xml"):
            if not (xml := netz.fetch(karte)):
                netz.melde(f"festapp: {karte} nicht ladbar")
                continue
            for loc in sitemap_adressen(xml):
                if (m := _DETAIL.fullmatch(loc)) and not (m.group(1) and int(m.group(1)) < seit):
                    links[loc] = None
        return list(links)

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        if not (ereignisse := json_ld_events(html)):
            return None
        d = ereignisse[0]
        if not (roh := feld(d.get("name"))):
            return None

        # Anschrift: „Dorfstrasse 22, 3457 Sumiswald, Switzerland" — das Land
        # steht zuverlässig am Ende.
        platz = erstes_objekt(d.get("location"))
        anschrift_ = erstes_objekt(platz.get("address"))
        anschrift = feld(anschrift_.get("addressLocality"))
        teile = [t.strip() for t in anschrift.split(",") if t.strip()]
        if not ist_land(land := land_code(teile[-1]) if len(teile) > 1 else ""):
            return None                       # ohne erkennbares Land kein Eintrag
        stadt = ort_aus(feld(platz.get("name")), anschrift)

        angebot = erstes_objekt(d.get("offers"))
        wert = betrag(feld(angebot.get("price")))
        preis = "" if wert is None else (f"ab {angebot.get('priceCurrency', 'EUR')} "
                                         + f"{wert:.2f}".replace(".", ","))
        return fund(
            self.name, url, ohne_jahr(roh),
            von=zeit.aus_iso(d.get("startDate")), bis=zeit.aus_iso(d.get("endDate")),
            jahr=jahr_aus(roh), stadt=stadt, land=land,
            plz=feld(anschrift_.get("postalCode")),
            preis=preis, webseite=feld(angebot.get("url")),
            abgesagt=feld(d.get("eventStatus")).endswith("EventCancelled"),
            lineup=acts_aus_datenblatt(d),
        )
