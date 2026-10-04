"""festivalticker.de — Listenseiten in allen Spielarten.

Die dichteste Abdeckung für Deutschland. Eine Sitemap gibt es nicht, dafür
Jahres-, Monats-, Länder- und Statusarchive. Die Jahresarchive zeigen je 40
Einträge; mehr gibt die Seite für vergangene Jahrgänge nicht her.

Die Listenseiten nennen schon Name, Termin, Ort und Stil — oft vollständiger
als die Detailseite. Diese Stammdaten merkt sich die Quelle (`self.stamm`) und
nimmt sie beim Lesen der Detailseite dazu.
"""

import re
from urllib.parse import parse_qs, urljoin, urlparse

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.text import clean, genres_vereinen, valid_band
from ..netz import Abrufer, soup
from ..pfade import JAHR_HEUTE, JAHRE
from .basis import Quelle

FT = "https://www.festivalticker.de"

LISTEN = (
    [f"{FT}/alle-festivals/", f"{FT}/alle-festivals-ab-jetzt/",
     f"{FT}/festivals-in-deutschland/", f"{FT}/internationale-festivals/",
     f"{FT}/laufende-festivals/", f"{FT}/neue-festivals/",
     f"{FT}/umsonst-und-draussen/"]
    + [f"{FT}/festivals-{m}/" for m in zeit.MONATE]
    + [f"{FT}/festivals-{j}/" for j in JAHRE]
    + [f"{FT}/{j}/" for j in JAHRE]
)

FELDER = {"Stil", "Kategorie", "Preis", "Besucher", "Location", "Plz",
          "Ort", "Land", "Website", "Bands"}

BANDS_ENDE = re.compile(
    r"\s*(?:Neues zu:|Kommentare zu:|Zurück\b|Zum Festivalplaner|\bclose\b|"
    r"Kategorie:|Preis:|Besucher:|Location:|Stil:|Plz:|Ort:|Strasse:|Land:|Website:)")

# Bandlisten ohne Komma reihen „Bandname (Stilbeschreibung)" aneinander. Der
# Namensteil ist begrenzt: unbegrenzt sucht das Muster in einem Text ohne
# Klammern von jeder Stelle bis zum Ende — bei 10.000 Uhrzeiten über sechs
# Minuten.
BANDS_KLAMMER = re.compile(r"([^()]{1,80}?)\s*\(([^()]{2,60})\)")
# … oder stehen als Ablaufplan „17:30 Band 19:45 Band" da.
BANDS_UHRZEIT = re.compile(r"\b\d{1,2}[:.]\d{2}\s*(?:Uhr)?\s*")
#: „Dj Sconan und weitere" — der Nachsatz gehört nicht zum Namen. 302 Acts
#: standen so in den Daten und fanden nie zu ihrer Band.
NACHSATZ = re.compile(r"(?i)\s+(?:und|and|&|\+)\s+(?:viele\s+)?(?:weitere|mehr|more)\.?$"
                      r"|\s+u\.?\s?v\.?\s?m\.?$")
_TERMIN = re.compile(r"Vom:\s*(\d{2}\.\d{2}\.\d{4})\s*bis:\s*(\d{2}\.\d{2}\.\d{4})")
_EIN_DATUM = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")


def _name(roh: str) -> str:
    return NACHSATZ.sub("", clean(roh))


def bands(blob: str) -> list[str]:
    """Bandnamen aus einem Textblock, ohne zu raten."""
    blob = BANDS_ENDE.split(blob)[0].strip() if blob else ""
    if not blob:
        return []

    if "," in blob:
        return [n for p in blob.split(",") if valid_band(n := _name(p))]

    # Kein Komma: Die Klammer hinter jedem Namen dient als Trenner — ab zwei
    # Treffern ist das Muster belastbar.
    paare = BANDS_KLAMMER.findall(blob) if "(" in blob and ")" in blob else []
    if len(paare) >= 2:
        namen = [_name(n) for n, _ in paare]
        if (rest := _name(blob[blob.rfind(")") + 1:])):
            namen.append(rest)
        if len(namen := [n for n in namen if valid_band(n) and len(n) <= 60]) >= 2:
            return namen

    # Ablaufplan mit Uhrzeiten als Trenner
    if len(BANDS_UHRZEIT.findall(blob)) >= 2:
        namen = [_name(t) for t in BANDS_UHRZEIT.split(blob)]
        if len(namen := [n for n in namen if valid_band(n) and len(n) <= 60]) >= 2:
            return namen

    # Sonst gibt es keinen verlässlichen Trenner. Nach Leerzeichen zu teilen
    # hieße raten („Nebula Allstars" ergäbe „Nebula"); als ein Act gilt der
    # Block nur bei kurzer, namensartiger Form.
    blob = _name(blob)
    if valid_band(blob) and len(blob) <= 30 and len(blob.split()) <= 4:
        return [blob]
    return []


class Festivalticker(Quelle):
    name = "festivalticker"
    startseite = FT
    zweck = "dichteste Abdeckung für Deutschland"

    def __init__(self):
        #: Adresse → was die Listenseite über dieses Festival schon wusste
        self.stamm: dict[str, dict] = {}

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Stammdaten je Festival aus den Listen (Name, Termin, Ort, Land, Stil)."""
        self.stamm.clear()
        for url in LISTEN:
            if (html := netz.fetch(url)):
                self._liste_lesen(url, html, seit)
                continue
            # Künftige Jahrgänge gibt es noch nicht — auch das kommende Jahr
            # führt festivalticker nur unter /festivals-2027/, nicht unter /2027/.
            jahr = re.search(r"/(?:festivals-)?(\d{4})/?$", url)
            if not (jahr and int(jahr.group(1)) > JAHR_HEUTE):
                netz.melde(f"Liste nicht ladbar: {url}")
        return list(self.stamm)

    def _liste_lesen(self, url: str, html: str, seit: int) -> None:
        for ev in soup(html).find_all("tbody", class_="vevent"):
            a = ev.find("a", class_="summary")
            if not a or not a.get("href"):
                continue

            def wert(knoten):
                vt = knoten.find("span", class_="value-title") if knoten else None
                return zeit.aus_iso(vt.get("title", "")) if vt else None

            von = wert(ev.find("span", class_="dtstart"))
            bis = wert(ev.find("span", class_="dtend")) or von
            # Nach dem Ende, nicht nach dem Beginn: Ein Fest vom 29.12. bis
            # zum 1.1. läuft am Neujahrstag noch.
            if seit and bis and bis.year < seit:
                continue
            loc = ev.find("span", class_="location")
            platz = clean(loc.get_text()) if loc else ""
            land = re.search(r"Land:\s*(\w{2,})", ev.get_text(" ", strip=True))
            stil = ev.find("span", title=True)
            self.stamm[urljoin(url, a["href"])] = {
                "name": clean(a.get_text()), "von": von, "bis": bis,
                "stadt": re.sub(r"^\d[\w\- ]*?\s+", "", platz).strip() or platz,
                "land": land.group(1).upper() if land else "",
                "genre": clean(stil.get("title")) if stil else "",
            }

    def webseite(self, netz: Abrufer, link: str) -> str:
        """Extern verlinkt wird über /link/?url=… oder eine Weiterleitung."""
        q = parse_qs(urlparse(link).query)
        for key in ("url", "u", "link", "goto"):
            if q.get(key):
                return q[key][0].strip()
        if "festivalticker.de" not in urlparse(link).netloc:
            return link
        return netz.endziel(link, "festivalticker.de")

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        stamm = self.stamm.get(url, {})
        s = soup(html)
        name = stamm.get("name") or (clean(s.title.get_text()) if s.title else "")
        titel = s.find("h2")
        if not name and titel:
            name = clean(titel.get_text())
        name = re.sub(r"\s+(19|20)\d{2}$", "", re.sub(r"^\d+\.\s*", "", name)).strip()
        if not name:
            return None

        # Abgesagt: durchgestrichene Überschrift oder roter Hinweis
        text = s.get_text("\n", strip=True)
        abgesagt = bool(titel and "line-through" in (titel.get("class") or [])) \
            or bool(re.search(r"wurde abgesagt", text, re.I))

        if (dm := _TERMIN.search(text)):
            von, bis = zeit.aus_deutsch(dm.group(1)), zeit.aus_deutsch(dm.group(2))
        else:
            eins = _EIN_DATUM.search(text)
            von = bis = zeit.aus_deutsch(eins.group(1)) if eins else None

        werte: dict[str, str] = {}
        webseite, lineup = "", []
        for tr in s.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2 or (label := clean(tds[0].get_text()).rstrip(":")) not in FELDER:
                continue
            if label == "Website":
                if (a := tds[1].find("a", href=True)):
                    webseite = self.webseite(netz, urljoin(url, a["href"].strip())).strip()
            elif label == "Bands":
                lineup.extend(bands(clean(tds[1].get_text())))
            else:
                # „Stil" steht gekürzt und vollständig auf der Seite
                wert = re.sub(r"\s*\.{2,}\s*mehr\s*", " ", clean(tds[1].get_text()))
                werte.setdefault(label, re.sub(r"\s*close\s*$", "", wert).strip(" ,."))

        if not lineup and (m := re.search(r"\bBands:\s*(.+)$",
                                          clean(s.get_text(" ", strip=True)))):
            lineup = bands(m.group(1))

        return fund(
            self.name, url, name,
            von=stamm.get("von") or von, bis=stamm.get("bis") or bis,
            stadt=werte.get("Ort", "") or stamm.get("stadt", ""),
            land=werte.get("Land", "") or stamm.get("land", ""),
            ort=werte.get("Location", ""), plz=werte.get("Plz", ""),
            preis=werte.get("Preis", ""), webseite=webseite,
            # Gekürzt und vollständig hintereinander: doppelte fallen weg
            genre=genres_vereinen(werte.get("Stil", "") or stamm.get("genre", "")
                                  or werte.get("Kategorie", "")),
            besucher=werte.get("Besucher", ""),
            abgesagt=abgesagt, lineup=lineup,
        )
