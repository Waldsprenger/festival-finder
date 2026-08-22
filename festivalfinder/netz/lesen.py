"""Aus einer abgerufenen Seite das herausholen, was maschinenlesbar ist.

Drei Wege, die sich alle zwölf Quellen teilen: der Elementbaum, die Sitemap
und das Datenblatt nach schema.org. Reine Funktionen ohne Netz — was hier
hineingeht, ist bereits abgerufen.
"""

import json
import re

from bs4 import BeautifulSoup


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def sitemap_adressen(xml: str | None) -> list[str]:
    """Alle <loc>-Einträge einer Sitemap."""
    return re.findall(r"<loc>([^<]+)</loc>", xml or "")


#: Was in einem Datenblatt als Veranstaltung gilt
_EREIGNIS = {"event", "festival", "musicevent", "musicfestival"}


def json_ld_events(html: str) -> list[dict]:
    """Alle Veranstaltungsblöcke aus dem Datenblatt einer Seite (schema.org).

    Die Blöcke stecken mal einzeln, mal als Liste, mal in einem `@graph` — alle
    drei Formen kommen in den Quellen vor.
    """
    treffer: list[dict] = []
    for m in re.finditer(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>",
                         html, re.S):
        try:
            daten = json.loads(m.group(1).strip())
        except Exception:
            continue
        stapel = daten if isinstance(daten, list) else [daten]
        while stapel:
            d = stapel.pop()
            if not isinstance(d, dict):
                continue
            if isinstance(d.get("@graph"), list):
                stapel.extend(d["@graph"])
            if str(d.get("@type", "")).lower() in _EREIGNIS:
                treffer.append(d)
    return treffer


def erstes_objekt(wert) -> dict:
    """Ein Datenblattfeld, das mal ein Objekt und mal eine Liste ist.

    `location`, `offers` und `performer` kommen in beiden Formen vor; ohne
    diese Vereinheitlichung stünde in jedem Leser dieselbe Fallunterscheidung.
    """
    if isinstance(wert, list):
        wert = wert[0] if wert else {}
    return wert if isinstance(wert, dict) else {}
