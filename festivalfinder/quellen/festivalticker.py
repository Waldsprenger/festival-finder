"""festivalticker.de — Listenseiten in allen Spielarten.

Die dichteste Abdeckung für Deutschland. Eine Sitemap gibt es nicht, dafür
Jahres-, Monats-, Länder- und Statusarchive. Die Jahresarchive zeigen je 40
Einträge; mehr gibt die Seite für vergangene Jahrgänge nicht her.

Besonderheit: Die Listenseiten nennen bereits Name, Termin, Ort und Stil. Diese
Stammdaten sind oft vollständiger als die Detailseite und werden deshalb
gemerkt — das ist der Zustand, den diese Quelle als einzige über ihre Seiten
hinweg braucht.
"""

import re
from urllib.parse import parse_qs, urljoin, urlparse

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.text import clean, valid_band
from ..netz import Abrufer, soup
from ..pfade import JAHRE, JAHR_HEUTE
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

FELDER = ["Stil", "Kategorie", "Preis", "Besucher", "Location", "Plz",
          "Ort", "Land", "Website", "Bands"]

BANDS_ENDE = re.compile(
    r"\s*(?:Neues zu:|Kommentare zu:|Zurück\b|Zum Festivalplaner|\bclose\b|"
    r"Kategorie:|Preis:|Besucher:|Location:|Stil:|Plz:|Ort:|Strasse:|Land:|Website:)")

# Bandlisten ohne Komma reihen „Bandname (Stilbeschreibung)" aneinander …
# Der Namensteil ist begrenzt: Unbegrenzt (`[^()]+?`) sucht das Muster in einem
# Text ohne Klammern von jeder Stelle aus bis zum Ende — bei einem Ablaufplan
# mit 4.000 Uhrzeiten waren das 64 Sekunden, bei 10.000 über sechs Minuten.
BANDS_KLAMMER = re.compile(r"([^()]{1,80}?)\s*\(([^()]{2,60})\)")
# … oder stehen als Ablaufplan „17:30 Band 19:45 Band" da.
BANDS_UHRZEIT = re.compile(r"\b\d{1,2}[:.]\d{2}\s*(?:Uhr)?\s*")


def bands(blob: str) -> list[str]:
    """Bandnamen aus einem Textblock, ohne zu raten."""
    blob = BANDS_ENDE.split(blob)[0].strip() if blob else ""
    if not blob:
        return []

    if "," in blob:
        return [clean(p) for p in blob.split(",") if valid_band(p)]

    # Kein Komma: Die Klammer hinter jedem Namen dient als Trenner. Erst ab
    # zwei Treffern ist das Muster belastbar; ohne Klammer im Text braucht es
    # gar nicht erst zu suchen.
    paare = BANDS_KLAMMER.findall(blob) if "(" in blob and ")" in blob else []
    if len(paare) >= 2:
        namen = [clean(n) for n, _ in paare]
        if (rest := clean(blob[blob.rfind(")") + 1:])):
            namen.append(rest)
        namen = [n for n in namen if valid_band(n) and len(n) <= 60]
        if len(namen) >= 2:
            return namen

    # Ablaufplan mit Uhrzeiten als Trenner
    if len(BANDS_UHRZEIT.findall(blob)) >= 2:
        namen = [clean(t) for t in BANDS_UHRZEIT.split(blob)]
        namen = [n for n in namen if valid_band(n) and len(n) <= 60]
        if len(namen) >= 2:
            return namen

    # Sonst gibt es keinen verlässlichen Trenner. Eine Aufteilung nach
    # Leerzeichen würde raten und aus „Nebula Allstars" die Band „Nebula"
    # machen — lieber kein Lineup als ein erfundenes. „Deep Purple Manfred
    # Mann's Earth Band" sind zwei Acts ohne Trenner, deshalb gilt der Block
    # nur bei kurzer, namensartiger Form als ein einzelner Act.
    if valid_band(blob) and len(blob) <= 30 and len(blob.split()) <= 4:
        return [clean(blob)]
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
            html = netz.fetch(url)
            if not html:
                # Künftige Jahrgänge existieren noch nicht — das ist kein
                # Fehler. Auch das kommende Jahr zählt dazu: festivalticker
                # führt es unter /festivals-2027/, aber nicht unter /2027/.
                jahr = re.search(r"/(?:festivals-)?(\d{4})/?$", url)
                if not (jahr and int(jahr.group(1)) > JAHR_HEUTE):
                    netz.melde(f"Liste nicht ladbar: {url}")
                continue
            self._liste_lesen(url, html, seit)
        return list(self.stamm)

    def _liste_lesen(self, url: str, html: str, seit: int) -> None:
        for ev in soup(html).find_all("tbody", class_="vevent"):
            a = ev.find("a", class_="summary")
            if not a or not a.get("href"):
                continue

            def wert(node):
                vt = node.find("span", class_="value-title") if node else None
                return zeit.aus_iso(vt.get("title", "")) if vt else None

            von = wert(ev.find("span", class_="dtstart"))
            bis = wert(ev.find("span", class_="dtend")) or von
            # Nach dem Ende, nicht nach dem Beginn: Ein Fest vom 29.12. bis zum
            # 1.1. läuft am Neujahrstag noch, sein Beginn liegt aber im alten
            # Jahr — so fiele es genau dann heraus, wenn es stattfindet.
            if seit and bis and bis.year < seit:
                continue
            loc = ev.find("span", class_="location")
            platz = clean(loc.get_text()) if loc else ""
            land = re.search(r"Land:\s*(\w{2,})", ev.get_text(" ", strip=True))
            stil = ev.find("span", title=True)
            self.stamm[urljoin(url, a["href"])] = {
                "name": clean(a.get_text()),
                "von": von,
                "bis": bis,
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
        if not name:
            h2 = s.find("h2")
            name = clean(h2.get_text()) if h2 else ""
        name = re.sub(r"^\d+\.\s*", "", name)             # „35. Wacken Open Air"
        name = re.sub(r"\s+(19|20)\d{2}$", "", name).strip()
        if not name:
            return None

        # Abgesagte Termine: durchgestrichene Überschrift plus roter Hinweis
        titel = s.find("h2")
        text = s.get_text("\n", strip=True)
        abgesagt = bool(titel and "line-through" in (titel.get("class") or [])) \
            or bool(re.search(r"wurde abgesagt", text, re.I))

        dm = re.search(r"Vom:\s*(\d{2}\.\d{2}\.\d{4})\s*bis:\s*(\d{2}\.\d{2}\.\d{4})",
                       text)
        if dm:
            von, bis = zeit.aus_deutsch(dm.group(1)), zeit.aus_deutsch(dm.group(2))
        else:
            eins = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
            von = bis = zeit.aus_deutsch(eins.group(1)) if eins else None

        felder: dict[str, str] = {}
        webseite = ""
        lineup: list[str] = []
        for tr in s.find_all("tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2:
                continue
            label = clean(tds[0].get_text()).rstrip(":")
            if label not in FELDER:
                continue
            if label == "Website":
                if (a := tds[1].find("a", href=True)):
                    webseite = self.webseite(netz, urljoin(url, a["href"].strip())).strip()
            elif label == "Bands":
                lineup.extend(bands(clean(tds[1].get_text())))
            else:
                # „Stil" steht gekürzt und vollständig auf der Seite
                wert = clean(tds[1].get_text())
                wert = re.sub(r"\s*\.{2,}\s*mehr\s*", " ", wert)
                felder.setdefault(label, re.sub(r"\s*close\s*$", "", wert).strip(" ,."))

        if not lineup:
            if (m := re.search(r"\bBands:\s*(.+)$", clean(s.get_text(" ", strip=True)))):
                lineup = bands(m.group(1))

        return fund(
            self.name, url, name,
            von=stamm.get("von") or von,
            bis=stamm.get("bis") or bis,
            stadt=felder.get("Ort", "") or stamm.get("stadt", ""),
            land=felder.get("Land", "") or stamm.get("land", ""),
            ort=felder.get("Location", ""),
            plz=felder.get("Plz", ""),
            preis=felder.get("Preis", ""),
            webseite=webseite,
            genre=(felder.get("Stil", "") or stamm.get("genre", "")
                   or felder.get("Kategorie", "")),
            besucher=felder.get("Besucher", ""),
            abgesagt=abgesagt,
            lineup=lineup,
        )
