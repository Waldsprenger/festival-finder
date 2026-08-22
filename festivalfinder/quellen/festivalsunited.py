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
from .basis import Quelle

FU = "https://www.festivalsunited.com"

#: Pfade unter /festivals/, die keine Einzelveranstaltung sind
KEINE_DETAILS = {"calendar", "countries", "lists", "genres", "months",
                 "cities", "venues", "artists", "search", "upcoming",
                 "new", "top", "magazine"}

#: „/festivals/name", „/festivals/name/2026" und die seltene Zweitausgabe
#: „/festivals/name/2026/2"
DETAIL = re.compile(r"https://www\.festivalsunited\.com/festivals/"
                    r"[a-z0-9\-]+(?:/\d{4}(?:/\d)?)?")

#: Währungen, die im Fließtext vorkommen
WAEHRUNGEN = r"€|EUR|CHF|GBP|DKK|SEK|NOK|PLN|HUF|CZK"


def slug(adresse: str) -> str:
    return adresse.rsplit("/festivals/", 1)[1].split("/")[0]


def lineup_aus_karten(s) -> list[str]:
    """Headliner und übrige Acts aus den Line-Up-Karten.

    Die Karten stehen nicht zwingend neben der Überschrift, daher werden sie
    über ihre Auszeichnung erkannt: Headliner sind fett und stehen auf einer
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
        if not (headliner or act):
            continue
        if not span.find_parent("div", class_="card-body"):
            continue
        nm = clean(span.get_text())
        if valid_band(nm):
            namen[nm] = None
    return list(namen)


class FestivalsUnited(Quelle):
    name = "festivalsunited"
    startseite = FU
    zweck = "Lineups, Preise und ein Datenblatt je Seite"

    def _laender(self, netz: Abrufer) -> list[str]:
        """Länderseiten; „international" ist eine Sammelseite, kein Land."""
        seiten = re.findall(r"<loc>(https://www\.festivalsunited\.com/festivals/"
                            r"countries/([a-z\-]+))</loc>",
                            netz.fetch(f"{FU}/sitemap-listings.xml") or "")
        return [u for u, s in seiten if s != "international"]

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Detailseiten aus der Sitemap — und aus den Länderseiten, die sie auslässt.

        Die Sitemap ist nach Jahrgängen aufgeteilt (upcoming plus
        historic-JAHR), deshalb lässt sich der Zeitraum ohne einen einzigen
        überflüssigen Abruf eingrenzen. Über die Länderseiten kommen 30
        Detailseiten dazu, die in der Sitemap fehlen — darunter das Exit
        Festival in Novi Sad.
        """
        index = netz.fetch(f"{FU}/sitemap.xml")
        if not index:
            netz.melde("festivalsunited: Sitemap nicht ladbar")
            return []

        links: dict[str, None] = {}
        for unterkarte in sitemap_adressen(index):
            if "festival" not in unterkarte:
                continue
            jahr = re.search(r"historic-(\d{4})", unterkarte)
            if jahr and int(jahr.group(1)) < seit:
                continue
            for loc in sitemap_adressen(netz.fetch(unterkarte)):
                # „/festivals/calendar/2026" sieht wie eine Detailseite aus,
                # ist aber eine Übersicht — sonst landet ein Festival namens
                # „Festivals" in den Daten.
                if DETAIL.fullmatch(loc) and slug(loc) not in KEINE_DETAILS:
                    links[loc] = None

        for land in self._laender(netz):
            for adresse in set(DETAIL.findall(netz.fetch(land) or "")):
                if slug(adresse) not in KEINE_DETAILS:
                    links.setdefault(adresse, None)
        return list(links)

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        s = soup(html)
        h1 = s.find("h1")
        roh = clean(h1.get_text()) if h1 else ""
        if not roh:
            return None
        ym = re.search(r"\b(20\d{2})\b", roh)
        jahr = ym.group(1) if ym else ""
        name = re.sub(r"\s*\b20\d{2}\b\s*$", "", roh).strip()

        text = re.sub(r"\n{2,}", "\n", s.get_text("\n", strip=True))

        # Abgesagt? Der Hinweis steht auf vielen Seiten auch bei anderen
        # Jahrgängen in der Ausgabenliste. Gewertet wird deshalb nur der Status
        # im Kopfbereich sowie der Klartext, der diese Ausgabe nennt.
        abgesagt = bool(re.search(re.escape(roh) + r"\s+wurde abgesagt", text, re.I))
        if not abgesagt:
            kopf = h1.find_parent(["section", "div"])
            if kopf and re.search(r"\bAbgesagt\b", kopf.get_text(" ", strip=True), re.I):
                abgesagt = True

        von, bis, hinweis, jahr = self._termin(text, jahr)

        # „Tickets ab 85,00 EUR" und „Tickets ab € 85,00"
        pm = re.search(rf"\bab\s+((?:{WAEHRUNGEN})\s*[\d.,]+|[\d.,]+\s*(?:{WAEHRUNGEN}))",
                       text, re.I)
        preis = "ab " + clean(pm.group(1)).rstrip(".,;") if pm else ""

        stadt, land, plz = self._ort(text, html)
        webseite = self._webseite(s)
        ort = self._spielstaette(html, name)
        lat, lon = self._punkt(html)

        if not preis:
            pm2 = re.search(r'"price"\s*:\s*"([\d.]+)"\s*,\s*'
                            r'"priceCurrency"\s*:\s*"([A-Z]{3})"', html)
            wert = betrag(pm2.group(1)) if pm2 else None
            if wert is not None:
                preis = f"ab {pm2.group(2)} " + f"{wert:.2f}".replace(".", ",")

        if not von:
            sm = re.search(r'"startDate"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"', html)
            if sm and (not jahr or sm[1] == jahr):
                von = zeit.aus_iso(f"{sm[1]}-{sm[2]}-{sm[3]}")
                em = re.search(r'"endDate"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"', html)
                bis = zeit.aus_iso(f"{em[1]}-{em[2]}-{em[3]}") if em else von
                hinweis = ""
                jahr = jahr or sm[1]

        if not abgesagt and re.search(r'"eventStatus"\s*:\s*"[^"]*EventCancelled"', html):
            abgesagt = True

        bm = re.search(r"Kapazität:\s*(?:ca\.?\s*)?([\d.\s]{3,12})", html)

        return fund(
            self.name, url, name,
            von=von, bis=bis, jahr=jahr,
            stadt=stadt, land=land, ort=ort, plz=plz, lat=lat, lon=lon,
            preis=preis, webseite=webseite, genre=self._genre(text, html),
            besucher=bm.group(1) if bm else "",
            hinweis=hinweis, abgesagt=abgesagt, lineup=lineup_aus_karten(s),
        )

    # ---------------- Einzelteile ----------------

    def _termin(self, text: str, jahr: str):
        """Seiten ohne bestätigte Neuauflage zeigen das Datum der letzten Ausgabe.

        Deshalb gewinnt der Treffer, dessen Jahr zur Ausgabe im Titel passt.
        """
        zeitraeume = [(m.group(1), m.group(2) or m.group(1)) for m in re.finditer(
            r"(\d{2}\.\d{2}\.\d{4})(?:\s*-\s*(\d{2}\.\d{2}\.\d{4}))?", text)]
        if not zeitraeume:
            return None, None, ("Termin noch nicht veröffentlicht" if jahr else ""), jahr

        treffer = next((r for r in zeitraeume if r[0][-4:] == jahr), None) if jahr else None
        if treffer:
            von, bis = zeit.aus_deutsch(treffer[0]), zeit.aus_deutsch(treffer[1])
            return von, bis, "", (jahr or (str(von.year) if von else ""))
        if jahr:
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

        # Das Datenblatt nennt bei 83 Festivals auch Ort und Postleitzahl, die
        # im Fließtext fehlen. Die Postleitzahl ist der bessere Weg: Sie trifft
        # den Zustellbereich, während ein Ortsname erst gefunden werden muss —
        # und in den Quellen schon mal „Madgeburg" heißt.
        ort_m = re.search(r'"addressLocality"\s*:\s*"([^"]{2,60})"', html)
        plz_m = re.search(r'"postalCode"\s*:\s*"([^"]{2,12})"', html)
        plz = clean(plz_m.group(1)).replace(" ", "") if plz_m else ""
        if not stadt and ort_m:
            stadt = clean(ort_m.group(1))

        # „Verschiedene Orte" ist kein Ort, sondern der Hinweis auf wechselnde
        # Spielstätten — als Ortsname fände ihn keine Suche.
        if re.fullmatch(r"(?i)verschiedene orte|diverse orte|mehrere orte", stadt.strip()):
            stadt = ""

        # Manche Einträge tragen die Postleitzahl im Ortsfeld („55116 Mainz").
        if (vorn := re.match(r"^\s*(\d{4,5})\s+([A-Za-zÄÖÜäöü].*)$", stadt)):
            plz = plz or vorn.group(1)
            stadt = clean(vorn.group(2))

        # Der Fließtext nennt das Land nur bei europäischen Ausgaben
        # zuverlässig. Zwei stille Quellen auf derselben Seite sagen es immer:
        # die eingebettete Adresse und der Link auf die Länderliste. Ohne sie
        # stand das Suwannee Hulaween aus Florida ohne Land in der Datei.
        if not land:
            if (jm := re.search(r'"addressCountry"\s*:\s*"([^"]{2,40})"', html)):
                land = land_code(clean(jm.group(1)))
        if not land:
            # „europe" und „international" sind Sammelseiten, keine Länder
            for km in re.finditer(r'/festivals/countries/([a-z\-]{2,30})"', html):
                s = km.group(1).replace("-", " ")
                if s not in ("europe", "international"):
                    land = land_code(s)
                    break
        return stadt, land, plz

    def _webseite(self, s) -> str:
        for a in s.find_all("a", href=True):
            href = a["href"]
            if "festivalsunited.com" in href or href.startswith("/"):
                continue
            if re.search(r"offizielle|website|webseite|homepage",
                         clean(a.get_text()).lower()) \
                    or re.search(r"offizielle|website|homepage",
                                 clean(a.get("title", "")), re.I):
                return href.strip()
        return ""

    def _spielstaette(self, html: str, name: str) -> str:
        vm = re.search(r'"@type"\s*:\s*"Place"\s*,\s*"name"\s*:\s*"([^"]{2,80})"', html)
        if vm and clean(vm.group(1)).casefold() != name.casefold():
            # Trägt die Spielstätte denselben Namen wie das Festival, sagt sie nichts
            return clean(vm.group(1))
        return ""

    def _punkt(self, html: str):
        gm = re.search(r'"latitude"\s*:\s*(-?\d+\.?\d*)\s*,\s*'
                       r'"longitude"\s*:\s*(-?\d+\.?\d*)', html)
        return (float(gm.group(1)), float(gm.group(2))) if gm else (None, None)

    def _genre(self, text: str, html: str) -> str:
        # „… ist ein Rock Festival" nennt die Richtung, „… ist ein Angebot von
        # Live Nation Festival" dagegen den Veranstalter. Ohne diese Grenze
        # stand bei 14 Festivals der Anbieter als Genre.
        genre = ""
        gm = re.search(r"ist ein ([A-Za-zÄÖÜäöü&\- ]{3,40}?) Festival", text)
        if gm and not re.match(r"(?i)angebot\b", gm.group(1).strip()):
            genre = clean(gm.group(1))

        # Der Kopfblock nennt die Stile ausdrücklich („Multi-Genre: Rock, Metal,
        # Punk UVM"), während der Fließtext nur „genreübergreifendes Festival"
        # sagt. Beim Reload Festival 2027 blieb deshalb nur die Sammelkategorie.
        if (km := re.search(r"(?:Multi-Genre|Genre)\s*<[^>]*>([^<]{3,120})<", html)):
            stile = re.sub(r"(?i)\s*\bUVM\.?\s*$", "", clean(km.group(1)))
            if stile:
                genre = genres_vereinen(stile, genre)
        return genre
