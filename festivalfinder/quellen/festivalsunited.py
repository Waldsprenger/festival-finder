"""festivalsunited.com — Sitemap je Jahrgang plus Länderseiten.

Die ergiebigste Quelle: Lineups, Preise und auf jeder Seite ein
maschinenlesbares Datenblatt, das Lücken des Fließtexts füllt.
"""

import re

from ..kern import zeit
from ..kern.fund import Fund, fund
from ..kern.geld import betrag
from ..kern.orte import land_code
from ..kern.text import clean, genres_vereinen, valid_band
from ..netz import Abrufer, sitemap_adressen, soup
from .basis import Quelle, erster_link, jahr_aus, ohne_jahr

FU = "https://www.festivalsunited.com"

#: Pfade unter /festivals/, die keine Einzelveranstaltung sind — sonst stünde
#: ein Festival namens „Festivals" in den Daten.
KEINE_DETAILS = {"calendar", "countries", "lists", "genres", "months",
                 "cities", "venues", "artists", "search", "upcoming",
                 "new", "top", "magazine"}

#: „/festivals/name", „/festivals/name/2026" und die seltene Zweitausgabe
#: „/festivals/name/2026/2"
DETAIL = re.compile(r"https://www\.festivalsunited\.com/festivals/"
                    r"[a-z0-9\-]+(?:/\d{4}(?:/\d)?)?")

WAEHRUNGEN = r"€|EUR|CHF|GBP|DKK|SEK|NOK|PLN|HUF|CZK"
_PREIS = re.compile(rf"\bab\s+((?:{WAEHRUNGEN})\s*[\d.,]+|[\d.,]+\s*(?:{WAEHRUNGEN}))", re.I)
_PREIS_BLATT = re.compile(r'"price"\s*:\s*"([\d.]+)"\s*,\s*"priceCurrency"\s*:\s*"([A-Z]{3})"')
_START = re.compile(r'"startDate"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"')
_ENDE = re.compile(r'"endDate"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"')
_ZEITRAUM = re.compile(r"(\d{2}\.\d{2}\.\d{4})(?:\s*-\s*(\d{2}\.\d{2}\.\d{4}))?")
_KAPAZITAET = re.compile(r"Kapazität:\s*(?:ca\.?\s*)?([\d.\s]{3,12})")
_PUNKT = re.compile(r'"latitude"\s*:\s*(-?\d+\.?\d*)\s*,\s*"longitude"\s*:\s*(-?\d+\.?\d*)')
_SPIELSTAETTE = re.compile(r'"@type"\s*:\s*"Place"\s*,\s*"name"\s*:\s*"([^"]{2,80})"')
_JAHR = re.compile(r"\b(?:19|20)\d\d\b")


def slug(adresse: str) -> str:
    return adresse.rsplit("/festivals/", 1)[1].split("/")[0]


def lineup_aus_karten(s) -> list[str]:
    """Headliner und übrige Acts aus den Line-Up-Karten.

    Erkannt an ihrer Auszeichnung: Headliner sind fett und stehen auf einer
    Zeile, die übrigen Acts tragen `text-primary font-weight-normal` und enden
    mit einem Zeilenumbruch.
    """
    namen: dict[str, None] = {}
    for span in s.find_all("span"):
        cls = set(span.get("class") or [])
        if "text-secondary" in cls:
            continue
        style = (span.get("style") or "").replace(" ", "")
        headliner = "font-weight-bold" in cls and "white-space:nowrap" in style
        act = {"text-primary", "font-weight-normal"} <= cls and \
            getattr(span.next_sibling, "name", None) == "br"
        if (headliner or act) and span.find_parent("div", class_="card-body"):
            if valid_band(nm := clean(span.get_text())):
                namen[nm] = None
    return list(namen)


class FestivalsUnited(Quelle):
    name = "festivalsunited"
    startseite = FU
    zweck = "Lineups, Preise und ein Datenblatt je Seite"

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Detailseiten aus der Sitemap — und aus den Länderseiten, die sie auslässt.

        Die Sitemap ist nach Jahrgängen geteilt (upcoming, historic-JAHR); über
        die Länderseiten kommen 30 Seiten dazu, die dort fehlen — darunter das
        Exit Festival in Novi Sad.
        """
        index = netz.fetch(f"{FU}/sitemap.xml")
        if not index:
            netz.melde("festivalsunited: Sitemap nicht ladbar")
            return []
        links: dict[str, None] = {}
        for karte in sitemap_adressen(index):
            jahr = re.search(r"historic-(\d{4})", karte)
            if "festival" not in karte or (jahr and int(jahr.group(1)) < seit):
                continue
            for loc in sitemap_adressen(netz.fetch(karte)):
                if DETAIL.fullmatch(loc) and slug(loc) not in KEINE_DETAILS:
                    links[loc] = None

        laender = re.findall(r"<loc>(https://www\.festivalsunited\.com/festivals/"
                             r"countries/([a-z\-]+))</loc>",
                             netz.fetch(f"{FU}/sitemap-listings.xml") or "")
        for land, kuerzel in laender:
            if kuerzel == "international":          # Sammelseite, kein Land
                continue
            for adresse in set(DETAIL.findall(netz.fetch(land) or "")):
                if slug(adresse) not in KEINE_DETAILS:
                    links.setdefault(adresse, None)
        return list(links)

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        h1 = s.find("h1")
        if not (roh := clean(h1.get_text()) if h1 else ""):
            return None
        jahr, name = jahr_aus(roh), ohne_jahr(roh)
        text = re.sub(r"\n{2,}", "\n", s.get_text("\n", strip=True))

        # Abgesagt? Der Hinweis steht oft auch bei anderen Jahrgängen in der
        # Ausgabenliste; gewertet wird nur der Kopfbereich und der Klartext,
        # der diese Ausgabe nennt.
        abgesagt = bool(re.search(re.escape(roh) + r"\s+wurde abgesagt", text, re.I))
        if not abgesagt and (kopf := h1.find_parent(["section", "div"])):
            abgesagt = bool(re.search(r"\bAbgesagt\b", kopf.get_text(" ", strip=True), re.I))
        if not abgesagt:
            abgesagt = bool(re.search(r'"eventStatus"\s*:\s*"[^"]*EventCancelled"', html))

        von, bis, hinweis, jahr = self._termin(text, jahr)
        if not von and (sm := _START.search(html)) and (not jahr or sm[1] == jahr):
            von = zeit.aus_iso(f"{sm[1]}-{sm[2]}-{sm[3]}")
            em = _ENDE.search(html)
            bis = zeit.aus_iso(f"{em[1]}-{em[2]}-{em[3]}") if em else von
            hinweis, jahr = "", jahr or sm[1]

        # „Tickets ab 85,00 EUR" und „Tickets ab € 85,00"; sonst das Datenblatt
        preis = "ab " + clean(pm.group(1)).rstrip(".,;") if (pm := _PREIS.search(text)) else ""
        if not preis and (pm := _PREIS_BLATT.search(html)) and \
                (wert := betrag(pm.group(1))) is not None:
            preis = f"ab {pm.group(2)} " + f"{wert:.2f}".replace(".", ",")

        stadt, land, plz = self._ort(text, html)
        gm = _PUNKT.search(html)
        vm = _SPIELSTAETTE.search(html)
        # Trägt die Spielstätte den Namen des Festivals, sagt sie nichts
        ort = clean(vm.group(1)) if vm and clean(vm.group(1)).casefold() != name.casefold() else ""
        bm = _KAPAZITAET.search(html)

        return fund(
            self.name, url, name, von=von, bis=bis, jahr=jahr,
            stadt=stadt, land=land, ort=ort, plz=plz,
            lat=float(gm.group(1)) if gm else None, lon=float(gm.group(2)) if gm else None,
            preis=preis,
            webseite=erster_link(s, ausser="festivalsunited.com",
                                 text=r"offizielle|website|webseite|homepage",
                                 titel=r"offizielle|website|homepage"),
            genre=self._genre(text, html), besucher=bm.group(1) if bm else "",
            hinweis=hinweis, abgesagt=abgesagt, lineup=lineup_aus_karten(s),
        )

    def _termin(self, text: str, jahr: str):
        """Seiten ohne bestätigte Neuauflage zeigen den Termin der letzten
        Ausgabe — es gewinnt der Treffer, dessen Jahr zum Titel passt."""
        zeitraeume = [(m.group(1), m.group(2) or m.group(1)) for m in _ZEITRAUM.finditer(text)]
        if not zeitraeume:
            return None, None, ("Termin noch nicht veröffentlicht" if jahr else ""), jahr
        if jahr:
            if (treffer := next((r for r in zeitraeume if r[0][-4:] == jahr), None)):
                return zeit.aus_deutsch(treffer[0]), zeit.aus_deutsch(treffer[1]), "", jahr
            return None, None, f"Termin offen; letzte gefundene Ausgabe {zeitraeume[0][0]}", jahr
        von, bis = zeit.aus_deutsch(zeitraeume[0][0]), zeit.aus_deutsch(zeitraeume[0][1])
        return von, bis, "", (str(von.year) if von else "")

    def _ort(self, text: str, html: str):
        stadt = land = ""
        if (lm := re.search(r"\d{2}\.\d{2}\.\d{4}\s*/\s*([^\n]+)", text)):
            stadt = clean(lm.group(1))
        if (cm := re.search(r"\bin\s+([A-ZÄÖÜ][^\n,]{1,40}?)\s*\((\w{2})\)", text)):
            stadt = stadt or clean(cm.group(1))
            land = cm.group(2).upper()
        # Ein Jahr im Ortsfeld heißt: Dort steht eine Ausgabe, kein Ort
        # („Immergut Festival 2026", „Lovebox Festival 2020").
        if _JAHR.search(stadt):
            stadt = ""

        # Das Datenblatt nennt oft Ort und Postleitzahl, die im Fließtext
        # fehlen; die Postleitzahl trifft den Zustellbereich am genauesten.
        ort_m = re.search(r'"addressLocality"\s*:\s*"([^"]{2,60})"', html)
        plz_m = re.search(r'"postalCode"\s*:\s*"([^"]{2,12})"', html)
        plz = clean(plz_m.group(1)).replace(" ", "") if plz_m else ""
        if not stadt and ort_m:
            stadt = clean(ort_m.group(1))
        # „Verschiedene Orte" ist der Hinweis auf wechselnde Spielstätten —
        # dann gilt auch keine aus dem Datenblatt.
        if re.fullmatch(r"(?i)(verschiedene|diverse|mehrere) orte", stadt.strip()):
            stadt = ""

        # Der Fließtext nennt das Land nur bei europäischen Ausgaben
        # zuverlässig; die eingebettete Anschrift und der Link auf die
        # Länderliste sagen es immer. „europe"/„international" sind
        # Sammelseiten.
        if not land and (jm := re.search(r'"addressCountry"\s*:\s*"([^"]{2,40})"', html)):
            land = land_code(clean(jm.group(1)))
        if not land:
            for km in re.finditer(r'/festivals/countries/([a-z\-]{2,30})"', html):
                if (s := km.group(1).replace("-", " ")) not in ("europe", "international"):
                    land = land_code(s)
                    break
        return stadt, land, plz

    def _genre(self, text: str, html: str) -> str:
        # „… ist ein Rock Festival" nennt die Richtung, „… ist ein Angebot von
        # Live Nation Festival" den Veranstalter.
        genre = ""
        if (gm := re.search(r"ist ein ([A-Za-zÄÖÜäöü&\- ]{3,40}?) Festival", text)) \
                and not re.match(r"(?i)angebot\b", gm.group(1).strip()):
            genre = clean(gm.group(1))
        # Der Kopfblock nennt die Stile ausdrücklich („Multi-Genre: Rock,
        # Metal, Punk UVM"), der Fließtext oft nur „genreübergreifend".
        if (km := re.search(r"(?:Multi-Genre|Genre)\s*<[^>]*>([^<]{3,120})<", html)):
            if (stile := re.sub(r"(?i)\s*\bUVM\.?\s*$", "", clean(km.group(1)))):
                genre = genres_vereinen(stile, genre)
        return genre
