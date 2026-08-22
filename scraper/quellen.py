"""Die zwölf Verzeichnisse: Adressen einsammeln, Detailseiten auslesen.

Jede Quelle liefert dieselbe Art Datensatz (`datensatz()`), damit das
Zusammenführen sie nicht auseinanderhalten muss. Was sie unterscheidet, steht
im Kopf ihres Abschnitts: wie man an ihre Adressen kommt und wo ihre
Eigenheiten liegen.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qs, urljoin, urlparse

from gemeinsam import (JAHR_HEUTE, JAHRE, ist_land, koordinate_passt_zum_land,
                       land_code)
from netz import fetch, endziel, json_ld_events, melde, sitemap_adressen, soup
from text import (KNOPFBESCHRIFTUNG, MONATE, besucherzahl, betrag, clean,
                  datum_de, datum_englisch, festival_name, genres_vereinen,
                  monat_nummer, plz_und_stadt, preis_text, valid_band)

FT = "https://www.festivalticker.de"      # dichteste Abdeckung für Deutschland
FU = "https://www.festivalsunited.com"    # Lineups, Preise, Datenblatt je Seite
FA = "https://www.festival-alarm.com"     # Spielstätte, Besucherzahl, Preise
FH = "https://www.festivalhopper.de"      # deutschsprachig, Lineups als Verweise
FP = "https://festapp.io"                 # Frankreich, Italien, Spanien
WF = "https://wannafest.com"              # Elektronisches, Benelux
FL = "https://festivalflyer.com"          # Großbritannien und Irland
FF = "https://www.festivalfinder.eu"      # European Festivals Association
FB = "https://www.festivalabroad.com"     # weltweit, mit Koordinaten und Genres
JB = "https://www.jambase.com"            # Nordamerika, mit vollen Lineups
FV = "https://www.festivism.com"          # Nachschlagewerk ohne Termine
FN = "https://festivalnetworks.com"       # 624 Festivals in einer Datei


# --------------------------------------------------------------------------
# Der gemeinsame Datensatz
# --------------------------------------------------------------------------

def datensatz(quelle: str, url: str, name: str, *, date_from: str = "",
              date_to: str = "", year: str = "", city: str = "", country: str = "",
              venue: str = "", plz: str = "", price: str = "", website: str = "",
              genre: str = "", visitors: str = "", note: str = "",
              cancelled: bool = False, lineup: list[str] | None = None,
              lat: float | None = None, lon: float | None = None) -> dict:
    """Ein Fund, wie ihn alle Quellen abliefern.

    Hier wird geradegezogen, was sonst jede Quelle einzeln beachten müsste —
    und hier steht die Plausibilitätsprüfung, die für alle acht gilt:

    * Der Name folgt der Liste in `data/festival_aliase.json`, falls er dort
      steht — für Fälle, die kein Buchstabenvergleich findet.
    * Das Jahr richtet sich nach dem Termin. Steht im Titel ein anderes als im
      Datum ("Sommer im Park Gera 2027" mit Termin im August 2026), gilt der
      Termin — er ist die genauere Angabe.
    * Das Land als Kürzel, nicht als Name: "Deutschland" und "DE" sind
      dieselbe Angabe und sollen auch dieselbe Schreibweise haben.
    * Die Besucherzahl ist eine einzelne, plausible Zahl — oder keine.
    * Ein Act steht einmal im Lineup, auch wenn er an zwei Tagen spielt.
    * Der Preis nennt eine Zahl oder freien Eintritt; "Pop Punk" ist kein Preis.
    * Steht die Postleitzahl im Ortsfeld ("104 45 Athen"), gehört sie ins
      Postleitzahlfeld.
    * Eine Koordinate muss auf der Erde liegen, nicht bei null Grad null - und
      in dem Land, das die Quelle nennt. Sonst steht Lollapalooza Berlin in
      Chicago und das LongLake Festival Lugano in Buenos Aires.
    """
    if not koordinate_plausibel(lat, lon) or not koordinate_passt_zum_land(
            lat, lon, country):
        lat = lon = None
    city, plz = plz_und_stadt(city, plz)
    return {
        "source": quelle,
        "source_url": url,
        "name": festival_name(name),
        "date_from": date_from,
        "date_to": date_to or date_from,
        "year": date_from[-4:] if date_from else year,
        "city": city,
        # Als Kürzel, gleich hier: Sechs Leser lieferten "DE", zwei
        # "Deutschland", und geradegezogen wurde es erst beim Zusammenführen.
        # Zwei Schreibweisen für dieselbe Sache sind eine Fehlerquelle, auch
        # wenn am Ende beide richtig ankommen.
        "country": land_code(country),
        "venue": venue,
        "plz": plz,
        "lat": lat,
        "lon": lon,
        "price": preis_text(price),
        "website": website,
        "genre": genre,
        "visitors": besucherzahl(visitors),
        "note": note,
        "cancelled": cancelled,
        # Ohne Wiederholungen, Reihenfolge wie geliefert: jambase nennt
        # einzelne Acts zweimal, wenn sie an mehreren Tagen spielen.
        "lineup": list(dict.fromkeys(lineup or [])),
    }


def datum_iso(wert) -> str:
    """"2026-07-03" oder "2026-07-03T18:00" → "03.07.2026"."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(wert or ""))
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else ""


def zahl_oder_nichts(wert) -> float | None:
    """Koordinaten stehen mal als Zahl, mal als Zeichenkette im Datenblatt."""
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def koordinate_plausibel(lat: float | None, lon: float | None) -> bool:
    """Ein Punkt auf der Erde - und nicht der Nullpunkt.

    0/0 liegt im Golf von Guinea und steht in Datenblättern für "kein Wert
    eingetragen". Ein Festival war dort noch nie.
    """
    if lat is None or lon is None:
        return False
    if abs(lat) > 90 or abs(lon) > 180:
        return False
    return not (abs(lat) < 0.01 and abs(lon) < 0.01)


@dataclass(frozen=True)
class Quelle:
    """Eine Quelle: wie man ihre Detailseiten findet und wie man sie liest."""
    name: str
    adressen: Callable[[int], list[str]]
    lesen: Callable[..., dict | None]
    #: festivalticker liefert Stammdaten schon in der Liste, die der Leser braucht
    mit_stammdaten: bool = False
    #: Manche Quellen legen alles in eine Datei. Dann gibt es keine Adressen
    #: je Festival, sondern einen Abruf, der alle Datensätze zurückgibt.
    feed: Callable[[int], list[dict]] | None = None


# --------------------------------------------------------------------------
# festivalticker.de — Listenseiten in allen Spielarten
# --------------------------------------------------------------------------
# Sitemap gibt es keine, dafür Jahres-, Monats-, Länder- und Statusarchive.
# Die Jahresarchive zeigen je 40 Einträge; mehr gibt die Seite für vergangene
# Jahrgänge nicht her.

FT_LISTEN = (
    [f"{FT}/alle-festivals/", f"{FT}/alle-festivals-ab-jetzt/",
     f"{FT}/festivals-in-deutschland/", f"{FT}/internationale-festivals/",
     f"{FT}/laufende-festivals/", f"{FT}/neue-festivals/",
     f"{FT}/umsonst-und-draussen/"]
    + [f"{FT}/festivals-{m}/" for m in MONATE]
    + [f"{FT}/festivals-{j}/" for j in JAHRE]
    + [f"{FT}/{j}/" for j in JAHRE]
)

FT_FELDER = ["Stil", "Kategorie", "Preis", "Besucher", "Location", "Plz",
             "Ort", "Land", "Website", "Bands"]

FT_BANDS_ENDE = re.compile(
    r"\s*(?:Neues zu:|Kommentare zu:|Zurück\b|Zum Festivalplaner|\bclose\b|"
    r"Kategorie:|Preis:|Besucher:|Location:|Stil:|Plz:|Ort:|Strasse:|Land:|Website:)")

# Bandlisten ohne Komma reihen "Bandname (Stilbeschreibung)" aneinander …
# Der Namensteil ist begrenzt: Unbegrenzt (`[^()]+?`) sucht das Muster in einem
# Text ohne Klammern von jeder Stelle aus bis zum Ende - bei einem Ablaufplan
# mit 4.000 Uhrzeiten waren das 64 Sekunden, bei 10.000 über sechs Minuten.
FT_BANDS_KLAMMER = re.compile(r"([^()]{1,80}?)\s*\(([^()]{2,60})\)")
# … oder stehen als Ablaufplan "17:30 Band 19:45 Band" da.
FT_BANDS_UHRZEIT = re.compile(r"\b\d{1,2}[:.]\d{2}\s*(?:Uhr)?\s*")

#: Stammdaten je Detailseite, aus den Listen gelesen
FT_STAMM: dict[str, dict] = {}


def ft_adressen(since: int) -> list[str]:
    """Stammdaten je Festival aus den Listenseiten (Name, Datum, Ort, Land, Stil)."""
    FT_STAMM.clear()
    for url in FT_LISTEN:
        html = fetch(url)
        if not html:
            # Künftige Jahrgänge existieren noch nicht - das ist kein Fehler.
            # Auch das kommende Jahr zählt dazu: festivalticker führt es unter
            # /festivals-2027/, aber nicht unter /2027/.
            jahr = re.search(r"/(?:festivals-)?(\d{4})/?$", url)
            if not (jahr and int(jahr.group(1)) > JAHR_HEUTE):
                melde(f"Liste nicht ladbar: {url}")
            continue
        for ev in soup(html).find_all("tbody", class_="vevent"):
            a = ev.find("a", class_="summary")
            if not a or not a.get("href"):
                continue

            def wert(node):
                vt = node.find("span", class_="value-title") if node else None
                return datum_de(vt.get("title", "")) if vt else ""

            date_from = wert(ev.find("span", class_="dtstart"))
            date_to = wert(ev.find("span", class_="dtend")) or date_from
            # Nach dem Ende, nicht nach dem Beginn: Ein Fest vom 29.12. bis
            # zum 1.1. läuft am Neujahrstag noch, sein Beginn liegt aber im
            # alten Jahr - so fiele es genau dann heraus, wenn es stattfindet.
            if since and date_to and int(date_to[-4:]) < since:
                continue
            loc = ev.find("span", class_="location")
            place = clean(loc.get_text()) if loc else ""
            cm = re.search(r"Land:\s*(\w{2,})", ev.get_text(" ", strip=True))
            stil = ev.find("span", title=True)
            FT_STAMM[urljoin(url, a["href"])] = {
                "name": clean(a.get_text()),
                "date_from": date_from,
                "date_to": date_to,
                "city": re.sub(r"^\d[\w\- ]*?\s+", "", place).strip() or place,
                "country": (cm.group(1).upper() if cm else ""),
                "genre": clean(stil.get("title")) if stil else "",
            }
    return list(FT_STAMM)


def ft_bands(blob: str) -> list[str]:
    """Bandnamen aus einem Textblock, ohne zu raten."""
    blob = FT_BANDS_ENDE.split(blob)[0].strip() if blob else ""
    if not blob:
        return []

    if "," in blob:
        return [clean(p) for p in blob.split(",") if valid_band(p)]

    # Kein Komma: Die Klammer hinter jedem Namen dient als Trenner.
    # Erst ab zwei Treffern ist das Muster belastbar. Ohne Klammer im Text
    # braucht es gar nicht erst zu suchen.
    paare = FT_BANDS_KLAMMER.findall(blob) if "(" in blob and ")" in blob else []
    if len(paare) >= 2:
        namen = [clean(n) for n, _ in paare]
        rest = clean(blob[blob.rfind(")") + 1:])
        if rest:
            namen.append(rest)
        namen = [n for n in namen if valid_band(n) and len(n) <= 60]
        if len(namen) >= 2:
            return namen

    # Ablaufplan mit Uhrzeiten als Trenner
    if len(FT_BANDS_UHRZEIT.findall(blob)) >= 2:
        namen = [clean(t) for t in FT_BANDS_UHRZEIT.split(blob)]
        namen = [n for n in namen if valid_band(n) and len(n) <= 60]
        if len(namen) >= 2:
            return namen

    # Sonst gibt es keinen verlässlichen Trenner. Eine Aufteilung nach
    # Leerzeichen würde raten und aus "Nebula Allstars" die Band "Nebula"
    # machen - lieber kein Lineup als ein erfundenes. "Deep Purple Manfred
    # Mann's Earth Band" sind zwei Acts ohne Trenner, deshalb gilt der Block
    # nur bei kurzer, namensartiger Form als ein einzelner Act.
    if valid_band(blob) and len(blob) <= 30 and len(blob.split()) <= 4:
        return [clean(blob)]
    return []


def ft_website(link: str) -> str:
    """festivalticker verlinkt extern über /link/?url=… bzw. eine Weiterleitung."""
    q = parse_qs(urlparse(link).query)
    for key in ("url", "u", "link", "goto"):
        if q.get(key):
            return q[key][0].strip()
    if "festivalticker.de" not in urlparse(link).netloc:
        return link
    return endziel(link, "festivalticker.de")


def ft_lesen(url: str, html: str, stamm: dict | None = None) -> dict | None:
    stamm = stamm or {}
    s = soup(html)
    name = stamm.get("name") or (clean(s.title.get_text()) if s.title else "")
    if not name:
        h2 = s.find("h2")
        name = clean(h2.get_text()) if h2 else ""
    name = re.sub(r"^\d+\.\s*", "", name)             # "35. Wacken Open Air"
    name = re.sub(r"\s+(19|20)\d{2}$", "", name).strip()
    if not name:
        return None

    # Abgesagte Termine: durchgestrichene Überschrift plus roter Hinweis
    titel = s.find("h2")
    text = s.get_text("\n", strip=True)
    cancelled = bool(titel and "line-through" in (titel.get("class") or [])) \
        or bool(re.search(r"wurde abgesagt", text, re.I))

    dm = re.search(r"Vom:\s*(\d{2}\.\d{2}\.\d{4})\s*bis:\s*(\d{2}\.\d{2}\.\d{4})", text)
    if dm:
        date_from, date_to = dm.group(1), dm.group(2)
    else:
        eins = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
        date_from = date_to = eins.group(1) if eins else ""

    felder: dict[str, str] = {}
    website = ""
    bands: list[str] = []
    for tr in s.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 2:
            continue
        label = clean(tds[0].get_text()).rstrip(":")
        if label not in FT_FELDER:
            continue
        if label == "Website":
            a = tds[1].find("a", href=True)
            if a:
                website = ft_website(urljoin(url, a["href"].strip())).strip()
        elif label == "Bands":
            bands.extend(ft_bands(clean(tds[1].get_text())))
        else:
            # "Stil" steht gekürzt und vollständig auf der Seite
            wert = clean(tds[1].get_text())
            wert = re.sub(r"\s*\.{2,}\s*mehr\s*", " ", wert)
            felder.setdefault(label, re.sub(r"\s*close\s*$", "", wert).strip(" ,."))

    if not bands:
        m = re.search(r"\bBands:\s*(.+)$", clean(s.get_text(" ", strip=True)))
        if m:
            bands = ft_bands(m.group(1))

    return datensatz(
        "festivalticker", url, name,
        date_from=stamm.get("date_from") or date_from,
        date_to=stamm.get("date_to") or date_to,
        city=felder.get("Ort", "") or stamm.get("city", ""),
        country=felder.get("Land", "") or stamm.get("country", ""),
        venue=felder.get("Location", ""),
        plz=felder.get("Plz", ""),
        price=felder.get("Preis", ""),
        website=website,
        genre=felder.get("Stil", "") or stamm.get("genre", "") or felder.get("Kategorie", ""),
        visitors=felder.get("Besucher", ""),
        cancelled=cancelled,
        lineup=bands,
    )


# --------------------------------------------------------------------------
# festivalsunited.com — Sitemap je Jahrgang plus Länderseiten
# --------------------------------------------------------------------------
# Die ergiebigste Quelle: Lineups, Preise und auf jeder Seite ein
# maschinenlesbares Datenblatt (JSON-LD), das Lücken des Fließtexts füllt.

# Pfade unter /festivals/, die keine Einzelveranstaltung sind
FU_KEINE_DETAILS = {"calendar", "countries", "lists", "genres", "months",
                    "cities", "venues", "artists", "search", "upcoming",
                    "new", "top", "magazine"}

#: "/festivals/name", "/festivals/name/2026" und die seltene Zweitausgabe
#: "/festivals/name/2026/2"
FU_DETAIL = re.compile(r"https://www\.festivalsunited\.com/festivals/"
                       r"[a-z0-9\-]+(?:/\d{4}(?:/\d)?)?")


def fu_slug(adresse: str) -> str:
    return adresse.rsplit("/festivals/", 1)[1].split("/")[0]


def fu_laender() -> list[str]:
    """Länderseiten; die außereuropäischen spart der Lauf sich.

    "international" ist eine Sammelseite, kein Land - alles andere kommt mit,
    von Argentinien bis Neuseeland.
    """
    seiten = re.findall(r"<loc>(https://www\.festivalsunited\.com/festivals/"
                        r"countries/([a-z\-]+))</loc>",
                        fetch(f"{FU}/sitemap-listings.xml") or "")
    return [u for u, slug in seiten if slug != "international"]


def fu_adressen(since: int) -> list[str]:
    """Detailseiten aus der Sitemap — und aus den Länderseiten, die sie auslässt.

    Die Sitemap ist nach Jahrgängen aufgeteilt (upcoming plus historic-JAHR),
    deshalb lässt sich der Zeitraum ohne einen einzigen überflüssigen Abruf
    eingrenzen. Über die Länderseiten kommen 30 Detailseiten dazu, die in der
    Sitemap fehlen — darunter das Exit Festival in Novi Sad.
    """
    index = fetch(f"{FU}/sitemap.xml")
    if not index:
        melde("festivalsunited: Sitemap nicht ladbar")
        return []

    links: dict[str, None] = {}
    for unterkarte in sitemap_adressen(index):
        if "festival" not in unterkarte:
            continue
        jahr = re.search(r"historic-(\d{4})", unterkarte)
        if jahr and int(jahr.group(1)) < since:
            continue
        for loc in sitemap_adressen(fetch(unterkarte)):
            # "/festivals/calendar/2026" sieht wie eine Detailseite aus, ist
            # aber eine Übersicht - sonst landet ein Festival namens
            # "Festivals" in den Daten.
            if FU_DETAIL.fullmatch(loc) and fu_slug(loc) not in FU_KEINE_DETAILS:
                links[loc] = None

    for land in fu_laender():
        for adresse in set(FU_DETAIL.findall(fetch(land) or "")):
            if fu_slug(adresse) not in FU_KEINE_DETAILS:
                links.setdefault(adresse, None)
    return list(links)


def fu_lineup(s) -> list[str]:
    """Headliner und übrige Acts aus den Line-Up-Karten.

    Die Karten stehen nicht zwingend neben der Überschrift, daher werden sie
    über ihre Auszeichnung erkannt: Headliner sind fett und stehen auf einer
    Zeile, die übrigen Acts tragen `text-primary font-weight-normal` und
    enden mit einem Zeilenumbruch.
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


def fu_lesen(url: str, html: str) -> dict | None:
    s = soup(html)
    h1 = s.find("h1")
    roh = clean(h1.get_text()) if h1 else ""
    if not roh:
        return None
    ym = re.search(r"\b(20\d{2})\b", roh)
    year = ym.group(1) if ym else ""
    name = re.sub(r"\s*\b20\d{2}\b\s*$", "", roh).strip()

    text = re.sub(r"\n{2,}", "\n", s.get_text("\n", strip=True))

    # Abgesagt? Der Hinweis steht auf vielen Seiten auch bei anderen
    # Jahrgängen in der Ausgabenliste. Gewertet wird deshalb nur der Status im
    # Kopfbereich sowie der Klartext, der den Namen dieser Ausgabe nennt.
    cancelled = bool(re.search(re.escape(roh) + r"\s+wurde abgesagt", text, re.I))
    if not cancelled:
        kopf = h1.find_parent(["section", "div"])
        if kopf and re.search(r"\bAbgesagt\b", kopf.get_text(" ", strip=True), re.I):
            cancelled = True

    # Seiten ohne bestätigte Neuauflage zeigen das Datum der letzten Ausgabe.
    # Deshalb gewinnt der Treffer, dessen Jahr zur Ausgabe im Titel passt.
    zeitraeume = [(m.group(1), m.group(2) or m.group(1)) for m in
                  re.finditer(r"(\d{2}\.\d{2}\.\d{4})(?:\s*-\s*(\d{2}\.\d{2}\.\d{4}))?", text)]
    note = ""
    date_from = date_to = ""
    if zeitraeume:
        treffer = next((r for r in zeitraeume if r[0][-4:] == year), None) if year else None
        if treffer:
            date_from, date_to = treffer
        elif year:
            note = f"Termin offen; letzte gefundene Ausgabe {zeitraeume[0][0]}"
        else:
            date_from, date_to = zeitraeume[0]
    elif year:
        note = "Termin noch nicht veröffentlicht"
    if not year and date_from:
        year = date_from[-4:]

    # "Tickets ab 85,00 EUR" und "Tickets ab € 85,00"
    waehrungen = r"€|EUR|CHF|GBP|DKK|SEK|NOK|PLN|HUF|CZK"
    pm = re.search(rf"\bab\s+((?:{waehrungen})\s*[\d.,]+|[\d.,]+\s*(?:{waehrungen}))",
                   text, re.I)
    price = "ab " + clean(pm.group(1)).rstrip(".,;") if pm else ""

    city = country = ""
    lm = re.search(r"\d{2}\.\d{2}\.\d{4}\s*/\s*([^\n]+)", text)
    if lm:
        city = clean(lm.group(1))
    cm = re.search(r"\bin\s+([A-ZÄÖÜ][^\n,]{1,40}?)\s*\((\w{2})\)", text)
    if cm:
        city = city or clean(cm.group(1))
        country = cm.group(2).upper()

    # Das Datenblatt nennt bei 83 Festivals auch Ort und Postleitzahl, die im
    # Fließtext fehlen. Die Postleitzahl ist der bessere Weg: Sie trifft den
    # Zustellbereich, während ein Ortsname erst gefunden werden muss - und in
    # den Quellen schon mal "Madgeburg" heißt.
    ort_m = re.search(r'"addressLocality"\s*:\s*"([^"]{2,60})"', html)
    plz_m = re.search(r'"postalCode"\s*:\s*"([^"]{2,12})"', html)
    plz = clean(plz_m.group(1)).replace(" ", "") if plz_m else ""
    if not city and ort_m:
        city = clean(ort_m.group(1))

    # "Verschiedene Orte" ist kein Ort, sondern der Hinweis auf wechselnde
    # Spielstätten - als Ortsname fände ihn keine Suche.
    if re.fullmatch(r"(?i)verschiedene orte|diverse orte|mehrere orte", city.strip()):
        city = ""

    # Manche Einträge tragen die Postleitzahl im Ortsfeld ("55116 Mainz").
    vorn = re.match(r"^\s*(\d{4,5})\s+([A-Za-zÄÖÜäöü].*)$", city)
    if vorn:
        plz = plz or vorn.group(1)
        city = clean(vorn.group(2))

    # Der Fließtext nennt das Land nur bei europäischen Ausgaben zuverlässig.
    # Zwei stille Quellen auf derselben Seite sagen es immer: die eingebettete
    # Adresse und der Link auf die Länderliste. Ohne sie stand das Suwannee
    # Hulaween aus Florida ohne Land in der Datei - und blieb damit drin,
    # obwohl nur Europa gesammelt wird.
    if not country:
        jm = re.search(r'"addressCountry"\s*:\s*"([^"]{2,40})"', html)
        if jm:
            country = land_code(clean(jm.group(1)))
    if not country:
        # "europe" und "international" sind Sammelseiten, keine Länder
        for km in re.finditer(r'/festivals/countries/([a-z\-]{2,30})"', html):
            slug = km.group(1).replace("-", " ")
            if slug not in ("europe", "international"):
                country = land_code(slug)
                break

    website = ""
    for a in s.find_all("a", href=True):
        href = a["href"]
        if "festivalsunited.com" in href or href.startswith("/"):
            continue
        if re.search(r"offizielle|website|webseite|homepage", clean(a.get_text()).lower()) \
                or re.search(r"offizielle|website|homepage", clean(a.get("title", "")), re.I):
            website = href.strip()
            break

    # Was der Fließtext nicht hergibt, steht oft im Datenblatt: Spielstätte,
    # Koordinaten, Einstiegspreis, Absagestatus. Ergänzt wird nur, was fehlt -
    # der Fließtext beschreibt die dargestellte Ausgabe, das Datenblatt ist
    # gelegentlich veraltet.
    venue = ""
    vm = re.search(r'"@type"\s*:\s*"Place"\s*,\s*"name"\s*:\s*"([^"]{2,80})"', html)
    if vm and clean(vm.group(1)).casefold() != name.casefold():
        # Trägt die Spielstätte denselben Namen wie das Festival, sagt sie nichts
        venue = clean(vm.group(1))

    lat = lon = None
    gm = re.search(r'"latitude"\s*:\s*(-?\d+\.?\d*)\s*,\s*"longitude"\s*:\s*(-?\d+\.?\d*)',
                   html)
    if gm:
        lat, lon = float(gm.group(1)), float(gm.group(2))

    if not price:
        pm2 = re.search(r'"price"\s*:\s*"([\d.]+)"\s*,\s*"priceCurrency"\s*:\s*"([A-Z]{3})"',
                        html)
        wert = betrag(pm2.group(1)) if pm2 else None
        if wert is not None:
            price = f"ab {pm2.group(2)} " + f"{wert:.2f}".replace(".", ",")

    if not date_from:
        sm = re.search(r'"startDate"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"', html)
        if sm and (not year or sm.group(1) == year):
            date_from = f"{sm.group(3)}.{sm.group(2)}.{sm.group(1)}"
            em = re.search(r'"endDate"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"', html)
            date_to = f"{em.group(3)}.{em.group(2)}.{em.group(1)}" if em else date_from
            note = ""
            year = year or sm.group(1)

    if not cancelled and re.search(r'"eventStatus"\s*:\s*"[^"]*EventCancelled"', html):
        cancelled = True

    # "… ist ein Rock Festival" nennt die Richtung, "… ist ein Angebot von Live
    # Nation Festival" dagegen den Veranstalter. Ohne diese Grenze stand bei 14
    # Festivals der Anbieter als Genre.
    genre = ""
    gm2 = re.search(r"ist ein ([A-Za-zÄÖÜäöü&\- ]{3,40}?) Festival", text)
    if gm2 and not re.match(r"(?i)angebot\b", gm2.group(1).strip()):
        genre = clean(gm2.group(1))

    # Der Kopfblock nennt die Stile ausdrücklich ("Multi-Genre: Rock, Metal,
    # Punk UVM"), während der Fließtext nur "genreübergreifendes Festival"
    # sagt. Beim Reload Festival 2027 blieb deshalb nur die Sammelkategorie
    # stehen, obwohl die Seite Rock, Metal und Punk aufführt.
    km = re.search(r"(?:Multi-Genre|Genre)\s*<[^>]*>([^<]{3,120})<", html)
    if km:
        stile = re.sub(r"(?i)\s*\bUVM\.?\s*$", "", clean(km.group(1)))
        if stile:
            genre = genres_vereinen(stile, genre)

    # "Kapazität: ca. 18.000" steht im selben Block
    bm = re.search(r"Kapazität:\s*(?:ca\.?\s*)?([\d.\s]{3,12})", html)  # "ca. 18.000"

    return datensatz(
        "festivalsunited", url, name,
        date_from=date_from, date_to=date_to, year=year,
        city=city, country=country, venue=venue, plz=plz, lat=lat, lon=lon,
        price=price, website=website, genre=genre,
        visitors=bm.group(1) if bm else "",
        note=note, cancelled=cancelled, lineup=fu_lineup(s),
    )


# --------------------------------------------------------------------------
# festival-alarm.com — Jahresseiten und Regionsseiten
# --------------------------------------------------------------------------
# Führt bei den meisten Festivals kein Lineup ("keine Daten"), liefert dafür
# Spielstätte, Besucherzahl und Preise. Die Werte stehen über mehrere Zeilen
# verteilt, deshalb wird der Text zu einer Zeile geglättet und jedes Feld bis
# zur nächsten bekannten Beschriftung gelesen.

FA_FELDER = {
    "preis":     r"Festivalticket \(ab\):\s*(.*?)\s*(?:Tagesticket|Ticketshop|Teilnehmer)",
    "stadt":     r"Stadt:\s*(.*?)\s*(?:Bundesland:|Land:)",
    "land":      r"\bLand:\s*(.*?)\s*(?:Veranstaltungsplatz|Wo:|Örtlichkeit|Camping)",
    "genre":     r"Genres:\s*(.*?)\s*(?:Gründung|Festivalausgabe|Besucher)",
    "besucher":  r"Besucher:\s*(.*?)\s*(?:Sonstiges|Weiterführende|Webseite)",
    "ort_name":  r"Örtlichkeit:\s*(.*?)\s*(?:Camping|Künstler|Anreise)",
    "acts":      r"Künstler:\s*(.*?)\s*(?:Anreise|Wie komme)",
}

FA_LEER = re.compile(r"^(keine daten|unbekannt|-|)$", re.I)


def fa_adressen(since: int) -> list[str]:
    """Jahresseiten; die Regionsseiten fangen auf, was dort fehlt."""
    links: dict[str, None] = {}
    for jahr in JAHRE:
        if jahr < since:
            continue
        html = fetch(f"{FA}/Festivals-{jahr}")
        if not html:
            continue
        for href in re.findall(rf'href="(/Festivals-{jahr}/[^"]+)"', html):
            links[urljoin(FA, href)] = None

        for pfad, code in set(re.findall(
                rf'href="(/festival/region/[^"]+/{jahr}/([A-Z]{{2}}))"', html)):
            if not ist_land(code):
                continue
            for href in re.findall(rf'href="(/Festivals-{jahr}/[^"]+)"',
                                   fetch(urljoin(FA, pfad)) or ""):
                links.setdefault(urljoin(FA, href), None)
    return list(links)


def fa_lesen(url: str, html: str) -> dict | None:
    s = soup(html)
    h1 = s.find("h1")
    roh = clean(h1.get_text(" ", strip=True)) if h1 else ""
    if not roh:
        return None

    # "Baltic Open Air 19.08. - 21.08.2026"
    dm = re.search(r"(\d{2}\.\d{2}\.)\s*-\s*(\d{2}\.\d{2}\.\d{4})|(\d{2}\.\d{2}\.\d{4})", roh)
    date_from = date_to = ""
    if dm and dm.group(2):
        date_from, date_to = dm.group(1) + dm.group(2)[-4:], dm.group(2)
    elif dm and dm.group(3):
        date_from = date_to = dm.group(3)
    name = re.sub(r"[\s\-–|]+$", "", clean(roh[:dm.start()]) if dm else roh)
    if not name:
        return None

    flach = clean(s.get_text(" ", strip=True))
    feld: dict[str, str] = {}
    for schluessel, muster in FA_FELDER.items():
        m = re.search(muster, flach, re.S)
        wert = clean(m.group(1)) if m else ""
        if wert and not FA_LEER.match(wert):
            feld[schluessel] = wert

    stadt_roh = feld.get("stadt", "")
    plz_m = re.match(r"\s*(\d{4,5})\b", stadt_roh)
    preis = feld.get("preis", "")
    if preis:
        preis = clean(preis.replace("ca.", "").replace("€", "EUR"))
        preis = "" if not re.search(r"\d", preis) else preis
        if preis and not preis.lower().startswith("ab"):
            preis = f"ab {preis}"

    website = ""
    for block in s.find_all(["li", "div", "p"]):
        if "Webseite" not in block.get_text():
            continue
        a = block.find("a", href=True)
        if a and a["href"].startswith("http") and "awin1.com" not in a["href"] \
                and "festival-alarm" not in a["href"]:
            website = a["href"].strip()
            break

    return datensatz(
        "festivalalarm", url, name,
        date_from=date_from, date_to=date_to,
        city=clean(re.sub(r"^\d{4,5}\s*", "", stadt_roh)),
        country=feld.get("land", ""),
        venue=feld.get("ort_name", ""),
        plz=plz_m.group(1) if plz_m else "",
        price=preis, website=website, genre=feld.get("genre", ""),
        visitors=feld.get("besucher", ""),
        lineup=[clean(b) for b in feld.get("acts", "").split(",") if valid_band(b)],
    )


# --------------------------------------------------------------------------
# festivalhopper.de — Sitemap, Jahrgang steht in der Adresse
# --------------------------------------------------------------------------

# "28. Summer Breeze 18.08.2027 (Mi) - 21.08.2027 (Sa)"
FH_TERMIN = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s*\(\w{2}\)\s*-\s*(\d{2}\.\d{2}\.\d{4})")
FH_FELDER = {
    "genre":    r"Musikart:[^A-Za-z0-9]*(.*?)\s*(?:Region:|Festivalort:|Besucher:)",
    "region":   r"Region:[^A-Za-z0-9]*(.*?)\s*(?:Festivalort:|Besucher:|Tickets:)",
    "ort":      r"Festivalort:[^A-Za-z0-9]*(.*?)\s*(?:Besucher:|Tickets:|Infos)",
    # Dicht am Wort: "Besucher:[^0-9]*" sprang ueber ganze Absaetze hinweg und
    # holte die naechste Ziffer irgendwo auf der Seite - auf Seiten mit
    # "Besucherinformationen" wurden daraus Zahlen mit 66 Stellen.
    "besucher": r"Besucher:\s{0,3}([\d.]{1,9})",
    "preis":    r"Tickets:[^A-Za-z0-9]*(.*?)\s*(?:Infos zum|Anfahrt|Lineup)",
}


def fh_adressen(since: int) -> list[str]:
    xml = fetch(f"{FH}/sitemap-festivals.xml")
    if not xml:
        melde("festivalhopper: Sitemap nicht ladbar")
        return []
    muster = re.compile(rf"{FH}/festival/([a-z0-9\-]+?)-((?:19|20)\d{{2}})")
    return [loc for loc in sitemap_adressen(xml)
            if (m := muster.fullmatch(loc)) and int(m.group(2)) >= since]


def fh_lesen(url: str, html: str) -> dict | None:
    s = soup(html)
    h1 = s.find("h1")
    roh = clean(h1.get_text()) if h1 else ""
    if not roh:
        return None
    jm = re.search(r"\b(20\d{2})\b", roh)
    name = re.sub(r"\s*\b20\d{2}\b\s*$", "", roh).strip()
    if not name:
        return None

    flach = clean(s.get_text(" ", strip=True))
    tm = FH_TERMIN.search(flach)

    feld = {}
    for schluessel, muster in FH_FELDER.items():
        m = re.search(muster, flach, re.S)
        wert = clean(m.group(1)) if m else ""
        if wert and wert.lower() not in ("unbekannt", "keine angabe", "-"):
            feld[schluessel] = wert

    # "Bayern , 🇩🇪 Deutschland" - das Land steht hinten, mit Flaggenzeichen
    # davor, das kein Buchstabe ist.
    land_roh = feld.get("region", "").split(",")[-1]
    land = land_code(clean(re.sub(r"[^\w ÄÖÜäöüß-]", " ", land_roh)))
    if land and not ist_land(land):
        return None                       # "Bayern" ist kein Land

    # "91550 Dinkelsbühl", aber auch "CH-8152 Glattbrugg" oder "A-1010 Wien"
    ort_roh = feld.get("ort", "")
    plz_m = re.match(r"\s*(?:[A-Z]{1,2}-)?(\d{4,5})\b\s*(.*)$", ort_roh)

    preis = feld.get("preis", "")
    if preis and not re.search(r"\d", preis):
        preis = ""

    # Bandnamen stehen als einzelne Verweise. Die Bandkarten liegen unter
    # /bands/karten/; die kürzeren /bands/-Adressen sind die Menüpunkte der
    # Seite ("Bands A-Z", "Headliner").
    bands = [clean(a.get_text()) for a in s.find_all("a", href=True)
             if "/bands/karten/" in a["href"] and valid_band(a.get_text())]

    website = ""
    for a in s.find_all("a", href=True):
        ziel = a["href"].strip()
        if not ziel.startswith("http") or "festivalhopper" in ziel:
            continue
        if re.search(r"(?i)openstreetmap|facebook|instagram|youtube|twitter|ticket", ziel):
            continue
        if clean(a.get_text()).lower().replace("www.", "") in ziel.lower():
            website = ziel
            break

    date_from = tm.group(1) if tm else ""
    return datensatz(
        "festivalhopper", url, name,
        date_from=date_from, date_to=tm.group(2) if tm else "",
        year=jm.group(1) if jm else "",
        city=clean(plz_m.group(2)) if plz_m else ort_roh,
        country=land,
        plz=plz_m.group(1) if plz_m else "",
        price=preis, website=website, genre=feld.get("genre", ""),
        visitors=feld.get("besucher", ""),
        note="" if date_from else "Termin noch nicht veröffentlicht",
        lineup=bands,
    )


# --------------------------------------------------------------------------
# festapp.io — Sitemaps der Festivals und der einzelnen Ausgaben
# --------------------------------------------------------------------------
# Weltweit, mit Datenblatt je Ausgabe; für die Liste zählt nur Europa.

def fp_adressen(since: int) -> list[str]:
    links: dict[str, None] = {}
    for karte in (f"{FP}/editions/sitemap/0.xml", f"{FP}/festivals/sitemap/0.xml"):
        xml = fetch(karte)
        if not xml:
            melde(f"festapp: {karte} nicht ladbar")
            continue
        for loc in sitemap_adressen(xml):
            m = re.fullmatch(r"https://festapp\.io/festivals/[a-z0-9\-]+(?:/(\d{4}))?", loc)
            if m and not (m.group(1) and int(m.group(1)) < since):
                links[loc] = None
    return list(links)


def acts_aus_datenblatt(d: dict) -> list[str]:
    """performer-Liste eines schema.org-Blocks; Einträge sind Text oder Objekt."""
    namen = []
    for act in (d.get("performer") or []):
        nm = clean(str(act.get("name", "") if isinstance(act, dict) else act))
        if valid_band(nm):
            namen.append(nm)
    return namen


def fp_lesen(url: str, html: str) -> dict | None:
    ereignisse = json_ld_events(html)
    if not ereignisse:
        return None
    d = ereignisse[0]
    roh = clean(str(d.get("name", "")))
    if not roh:
        return None
    jm = re.search(r"\b(20\d{2})\b", roh)

    ort = d.get("location") or {}
    ort = ort if isinstance(ort, dict) else {}
    adresse = ort.get("address") or {}
    adresse = adresse if isinstance(adresse, dict) else {}
    # "Dorfstrasse 22, 3457 Sumiswald, Switzerland": Die Anschrift beginnt oft
    # mit der Straße, deshalb zählt der Ortsname aus location.name. Das Land
    # steht zuverlässig am Ende.
    teile = [t.strip() for t in clean(str(adresse.get("addressLocality", ""))).split(",")
             if t.strip()]
    spielstaette = clean(str(ort.get("name", "")))
    city = spielstaette
    if not city and teile:
        # ohne location.name der vorletzte Teil, ohne führende Postleitzahl
        city = re.sub(r"^[A-Z]{0,2}[-\s]?\d[\w\s-]*?\s+", "",
                      teile[-2] if len(teile) > 1 else teile[0])
    country = land_code(teile[-1]) if len(teile) > 1 else ""
    if not ist_land(country):
        return None                       # ohne erkennbares Land kein Eintrag

    angebot = d.get("offers") or {}
    if isinstance(angebot, list):
        angebot = angebot[0] if angebot else {}
    angebot = angebot if isinstance(angebot, dict) else {}
    wert = betrag(str(angebot.get("price", "")))
    preis = ("" if wert is None else
             f"ab {angebot.get('priceCurrency', 'EUR')} "
             + f"{wert:.2f}".replace(".", ","))

    return datensatz(
        "festapp", url, re.sub(r"\s*\b20\d{2}\b\s*$", "", roh).strip() or roh,
        date_from=datum_de(d.get("startDate")), date_to=datum_de(d.get("endDate")),
        year=jm.group(1) if jm else "",
        city=city, country=country, venue=spielstaette,
        plz=clean(str(adresse.get("postalCode", ""))),
        price=preis, website=clean(str(angebot.get("url", ""))),
        cancelled=str(d.get("eventStatus", "")).endswith("EventCancelled"),
        lineup=acts_aus_datenblatt(d),
    )


# --------------------------------------------------------------------------
# wannafest.com — Sitemap, überwiegend Clubabende
# --------------------------------------------------------------------------
# In einer Stichprobe von 400 Einträgen waren 359 "Indoor", darunter Sachen
# wie "Bootshaus DJ Contest". Ungefiltert hätten rund 1.800 Clubnächte die
# Liste geflutet. Übernommen wird nur, was sich als Festival zu erkennen gibt:
# am Namen oder daran, dass es draußen stattfindet.

WF_DRAUSSEN = {"outdoor", "buiten", "draussen", "draußen", "strand", "beach",
               "boot", "park"}
WF_FESTIVALWORT = re.compile(r"(?i)festival|open ?air|openair|\bfest\b|"
                             r"weekender|\bdagen\b|\bdays\b|\bfestivals\b")


def wf_adressen(since: int) -> list[str]:
    """Die Sitemap nennt die Serveradresse statt des Namens - deshalb ersetzt."""
    xml = fetch(f"{WF}/sitemaps/festivals-1.xml")
    if not xml:
        melde("wannafest: Sitemap nicht ladbar")
        return []
    pfade = {re.sub(r"^https?://[^/]+", "", loc) for loc in sitemap_adressen(xml)}
    return [WF + p for p in pfade if re.fullmatch(r"/festivals/[a-z0-9\-]+", p)]


def wf_land_und_ort(rest: str) -> tuple[str, str]:
    """"Austria Festivalterrein Salzburgring": erst das Land, dann die Spielstätte.

    Das Land kann aus mehreren Wörtern bestehen ("United Kingdom"), deshalb
    von lang nach kurz probiert.
    """
    woerter = rest.split()
    for laenge in (3, 2, 1):
        code = land_code(" ".join(woerter[:laenge]))
        if ist_land(code):
            return code, clean(" ".join(woerter[laenge:]))
    return (land_code(" ".join(woerter[:2])) if woerter else ""), ""


def wf_lesen(url: str, html: str) -> dict | None:
    s = soup(html)
    titel = clean(s.title.get_text()) if s.title else ""
    name = re.sub(r"\s*[-–|]\s*WannaFest\s*$", "", titel).strip()
    if not name:
        return None

    flach = clean(s.get_text(" ", strip=True))
    dm = re.search(r"Date\s+(\w+ \d{1,2}, \d{4})[^A-Za-z]*(?:to\s+(\w+ \d{1,2}, \d{4}))?",
                   flach)
    date_from = datum_englisch(dm.group(1)) if dm else ""
    date_to = datum_englisch(dm.group(2)) if dm and dm.group(2) else ""

    # "Location Plainfeld, Austria Festivalterrein Salzburgring Place Type"
    lm = re.search(r"Location\s+([^,]{2,40}),\s*(.*?)\s*"
                   r"(?:Place Type|Website|Past events)", flach)
    country, venue = wf_land_und_ort(clean(lm.group(2))) if lm else ("", "")
    if not ist_land(country):
        return None

    art = re.search(r"Place Type\s+([A-Za-zÄÖÜäöü]+)", flach)
    draussen = (art.group(1).casefold() in WF_DRAUSSEN) if art else False
    if not draussen and not WF_FESTIVALWORT.search(name):
        return None

    website = ""
    for a in s.find_all("a", href=True):
        if "official" in clean(a.get_text()).lower() and a["href"].startswith("http"):
            website = a["href"].strip()
            break

    return datensatz(
        "wannafest", url, name,
        date_from=date_from, date_to=date_to,
        city=clean(lm.group(1)) if lm else "", country=country,
        venue=venue if len(venue) <= 60 and not KNOPFBESCHRIFTUNG.match(venue) else "",
        website=website,
    )


# --------------------------------------------------------------------------
# festivalflyer.com — nur die Startseite
# --------------------------------------------------------------------------
# Mehr ist nicht erreichbar: Die Sitemap enthält ausschließlich Artikel
# (30.937 Stück), die Übersicht unter /events/ wird im Browser zusammengesetzt,
# und die Detailseiten verweisen nur aufeinander. Die Startseite nennt dafür
# ein Dutzend kommende Festivals mit vollem Datenblatt - über das Jahr
# wechseln sie durch.

def fl_adressen(since: int) -> list[str]:
    html = fetch(f"{FL}/")
    if not html:
        melde("festivalflyer: Startseite nicht ladbar")
        return []
    return list({u.rstrip("/") + "/": None
                 for u in re.findall(rf"{FL}/events/[a-z0-9\-]+/", html)})


def fl_lesen(url: str, html: str) -> dict | None:
    ereignisse = json_ld_events(html)
    if not ereignisse:
        return None
    d = ereignisse[0]
    roh = clean(str(d.get("name", "")))
    if not roh:
        return None
    jm = re.search(r"\b(20\d{2})\b", roh)

    # "Fernhill Farm, Cheddar Road, BS40 6LD Compton Martin, United Kingdom"
    ort = d.get("location")
    if isinstance(ort, list):
        ort = ort[0] if ort else {}
    anschrift = clean(str(ort.get("name", ""))) if isinstance(ort, dict) else ""
    teile = [t.strip() for t in anschrift.split(",") if t.strip()]
    country = land_code(teile[-1]) if len(teile) > 1 else ""
    if not ist_land(country):
        return None
    # britische Postleitzahlen stehen vor dem Ort: "BS40 6LD Compton Martin"
    stadt_roh = teile[-2] if len(teile) > 1 else ""
    venue = teile[0] if len(teile) > 2 else ""

    # Die Beschreibung führt das Lineup, mit Schrägstrich getrennt
    beschreibung = re.sub(r"<[^>]+>", " ", str(d.get("description", "")))
    bands = []
    if "/" in beschreibung:
        for teil in beschreibung.split("/"):
            nm = re.sub(r"(?i)^(line ?up so far\.?|lineup:?)\s*", "",
                        clean(teil).strip("*").strip())
            if valid_band(nm) and len(nm) <= 60:
                bands.append(nm)

    return datensatz(
        "festivalflyer", url, re.sub(r"\s*\b20\d{2}\b\s*$", "", roh).strip() or roh,
        date_from=datum_de(d.get("startDate")), date_to=datum_de(d.get("endDate")),
        year=jm.group(1) if jm else "",
        city=clean(re.sub(r"^[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d?[A-Z]{0,2}\s+", "", stadt_roh)),
        country=country, venue=venue if len(venue) <= 60 else "",
        cancelled=str(d.get("eventStatus", "")).endswith("EventCancelled"),
        lineup=bands,
    )


# --------------------------------------------------------------------------
# festivalfinder.eu — Trefferliste der European Festivals Association
# --------------------------------------------------------------------------
# Klassik, Theater und Osteuropa. Der Filter artDisciplines=music entspricht
# der Suche auf der Seite; ohne ihn kämen Film- und Tanzfestivals mit.

FF_LISTE = re.compile(r'href="(/find-festival-organisations/[a-z0-9\-]+)"')
# "21 Aug 2026 - 30 Nov 2026", danach "Didymoteicho, Greece"
FF_TERMIN = re.compile(r"(\d{1,2} [A-Z][a-z]{2} \d{4})\s*[-–]\s*(\d{1,2} [A-Z][a-z]{2} \d{4})")


def ff_adressen(since: int) -> list[str]:
    """Die Trefferliste blättert über den Pfad: /p2, /p3 und so fort."""
    links: dict[str, None] = {}
    for seite in range(1, 260):
        pfad = f"{FF}/find-festival-organisations" + ("" if seite == 1 else f"/p{seite}")
        html = fetch(f"{pfad}?query&country&daterange&artDisciplines%5B0%5D=music")
        if not html:
            break
        neu = {FF + t for t in FF_LISTE.findall(html)
               if t.rstrip("/") != "/find-festival-organisations"} - set(links)
        if not neu:
            break
        links.update(dict.fromkeys(neu))
    return list(links)


def ff_lesen(url: str, html: str) -> dict | None:
    s = soup(html)
    # Die ersten beiden <h1> gehören dem Cookie-Hinweis, deshalb der Titel.
    # Fehlseiten antworten mit 200, erkennbar nur an ihrem Text.
    titel = clean(s.title.get_text()) if s.title else ""
    name = re.sub(r"\s*[-–|]\s*European Festivals Association\s*$", "", titel)
    if not name or name.lower().startswith("we could not find"):
        return None
    name = re.sub(r"\s*\b20\d{2}\b\s*$", "", name).strip() or name

    flach = clean(s.get_text(" ", strip=True))
    tm = FF_TERMIN.search(flach)
    date_from = datum_englisch(tm.group(1)) if tm else ""

    # Hinter dem Termin stehen Ort und Land: "Didymoteicho, Greece"
    city = country = ""
    if tm:
        om = re.match(r"\s*([^,]{2,40}),\s*([A-Za-zÄÖÜäöü' \-]{3,40}?)\s+"
                      r"(?:Visit|facebook|instagram|X\b|youtube|The |This )",
                      flach[tm.end():tm.end() + 120])
        if om:
            city = clean(om.group(1))
            country = land_code(clean(om.group(2)))
    if not ist_land(country):
        return None

    website = ""
    for a in s.find_all("a", href=True):
        if "visit website" in clean(a.get_text()).lower():
            website = a["href"].strip()
            break

    return datensatz(
        "festivalfinder", url, name,
        date_from=date_from,
        date_to=datum_englisch(tm.group(2)) if tm else "",
        city=city, country=country, website=website,
        note="" if date_from else "Termin noch nicht veröffentlicht",
    )


# --------------------------------------------------------------------------

#: Reihenfolge zählt: Sie entscheidet beim Zusammenführen, wessen Schreibweise
#: gewinnt - die drei gepflegten Verzeichnisse zuerst, die Ergänzungen danach.

# --------------------------------------------------------------------------
# festivalabroad.com — 3.261 Festivals weltweit, jedes mit Datenblatt
# --------------------------------------------------------------------------
# Die vollständigste der neuen Quellen: Termin, Koordinate, offizielle
# Adresse, Kapazität und Genres stehen im Datenblatt der Seite.

def fb_adressen(since: int) -> list[str]:
    """Alle Festivalseiten aus der Sitemap; der Termin steht erst auf der Seite."""
    index = sitemap_adressen(fetch(f"{FB}/sitemap.xml"))
    if not index:
        melde(f"Sitemap nicht ladbar: {FB}")
        return []
    adressen: set[str] = set()
    for karte in index:
        if not karte.endswith(".xml"):
            continue
        for u in sitemap_adressen(fetch(karte)):
            if re.search(r"/festivals/[^/]+$", u):
                adressen.add(u)
    return sorted(adressen)


#: "2000trees – Gloucestershire, United Kingdom 2027"
FB_TITEL = re.compile(r"^(.*?)\s+[–-]\s+(.*?)(?:\s+(\d{4}))?$")


def fb_ohne_datenblatt(url: str, html: str) -> dict | None:
    """Feste, deren nächster Termin noch aussteht.

    Für sie liefert die Seite kein Datenblatt - alles Nötige steht aber im
    Titel: Name, Ort, Land. Ohne Termin, denn den gibt es noch nicht ("TBA -
    last edition: 8 Jul 2026").
    """
    s = soup(html)
    titel = clean(s.title.get_text()) if s.title else ""
    titel = re.sub(r"\s*[|–-]\s*Festival Abroad\s*$", "", titel)
    m = FB_TITEL.match(titel)
    if not m:
        return None
    name = clean(m.group(1))
    ort_land = [t.strip(" .…") for t in (m.group(2) or "").split(",") if t.strip(" .…")]
    if not name or len(ort_land) < 2:
        return None
    # Lange Titel schneidet die Seite mit Auslassungszeichen ab: aus
    # "United States" wird "United State…". Was dann kein Land mehr ergibt,
    # bleibt lieber leer als falsch.
    land = ort_land[-1]
    return datensatz("festivalabroad", url, name,
                     city=ort_land[0], country=land if ist_land(land) else "")


def fb_lesen(url: str, html: str) -> dict | None:
    for d in json_ld_events(html):
        name = clean(str(d.get("name", "")))
        if not name:
            continue
        ort = d.get("location") or {}
        anschrift = ort.get("address") or {}
        geo = ort.get("geo") or {}
        # "Dresden, Germany" - der Ort steht vorn, das Land dahinter
        stadt = clean(str(anschrift.get("addressLocality", ""))).split(",")[0]
        angebot = d.get("offers") or {}
        if isinstance(angebot, list):
            angebot = angebot[0] if angebot else {}
        return datensatz(
            "festivalabroad", url, name,
            date_from=datum_iso(d.get("startDate")),
            date_to=datum_iso(d.get("endDate")),
            city=stadt, country=str(anschrift.get("addressCountry", "")),
            venue=clean(str(ort.get("name", ""))),
            lat=zahl_oder_nichts(geo.get("latitude")),
            lon=zahl_oder_nichts(geo.get("longitude")),
            website=str(d.get("url", "")),
            genre=clean(str(d.get("keywords", ""))),
            visitors=str(d.get("maximumAttendeeCapacity", "") or ""),
            price="Eintritt frei" if d.get("isAccessibleForFree") is True else "",
            cancelled="cancel" in str(d.get("eventStatus", "")).lower())
    return fb_ohne_datenblatt(url, html)


# --------------------------------------------------------------------------
# jambase.com — Nordamerika, mit vollständigen Lineups
# --------------------------------------------------------------------------
# Die Sitemap ist nach Monaten geteilt, der Jahrgang steht am Ende der
# Adresse ("/festival/the-yarnival-2026"). Danach wird gefiltert, sonst holte
# der Lauf 26.000 Seiten, von denen die meisten vergangene Jahrgänge sind.

def jb_adressen(since: int) -> list[str]:
    index = sitemap_adressen(fetch(f"{JB}/sitemap.xml"))
    karten = [k for k in index if "pt-festival" in k]
    if not karten:
        melde(f"Sitemap ohne Festivalkarten: {JB}")
        return []
    adressen: set[str] = set()
    for karte in karten:
        for u in sitemap_adressen(fetch(karte)):
            jahr = re.search(r"-(\d{4})/?$", u)
            if jahr and int(jahr.group(1)) >= since:
                adressen.add(u)
    return sorted(adressen)


#: Adressen, die keine offizielle Festivalseite sind
JB_KEINE_SEITE = re.compile(
    r"(?i)facebook|twitter|x\.com|instagram|tiktok|youtube|spotify|google\.|"
    r"jambase|ticketmaster|seetickets|eventbrite|theticketing|axs\.com|"
    r"bandsintown|linktr\.ee")


def jb_website(html: str) -> str:
    """Die offizielle Seite unter den ausgehenden Verweisen."""
    for a in soup(html).find_all("a", href=True):
        ziel = a["href"].strip()
        if ziel.startswith("http") and not JB_KEINE_SEITE.search(ziel):
            return ziel
    return ""


def jb_lesen(url: str, html: str) -> dict | None:
    for d in json_ld_events(html):
        name = clean(str(d.get("name", "")))
        if not name:
            continue
        ort = d.get("location") or {}
        anschrift = ort.get("address") or {}
        geo = ort.get("geo") or {}
        acts = [clean(str(p.get("name", ""))) for p in (d.get("performer") or [])
                if isinstance(p, dict)]
        # Region statt Land: "NY" gehört zu US, nicht zu Norwegen
        land = str(anschrift.get("addressCountry", ""))
        return datensatz(
            "jambase", url, name,
            date_from=datum_iso(d.get("startDate")),
            date_to=datum_iso(d.get("endDate")),
            city=clean(str(anschrift.get("addressLocality", ""))),
            country=land,
            venue=clean(str(ort.get("name", ""))),
            plz=clean(str(anschrift.get("postalCode", ""))),
            lat=zahl_oder_nichts(geo.get("latitude")),
            lon=zahl_oder_nichts(geo.get("longitude")),
            website=jb_website(html),
            price="Eintritt frei" if d.get("isAccessibleForFree") is True else "",
            lineup=[b for b in acts if valid_band(b)],
            cancelled="cancel" in str(d.get("eventStatus", "")).lower())
    return None


# --------------------------------------------------------------------------
# festivism.com — ein Nachschlagewerk ohne Termine
# --------------------------------------------------------------------------
# 5.207 Festivals aus aller Welt, jedes mit Ort, Land und Gründungsjahr, aber
# ohne Datum. Das ist kein Mangel dieser Quelle, sondern ihr Zweck: Sie führt
# das Fest, nicht seine nächste Ausgabe. Für den Bestand heißt das, dass ihre
# Einträge terminlos bleiben - und in Stufe 6 mit dem datierten Zwilling
# zusammenfinden, wo es einen gibt.

def fv_adressen(since: int) -> list[str]:
    adressen = [u for u in sitemap_adressen(fetch(f"{FV}/sitemap.xml"))
                if re.search(r"/festivals/[^/]+$", u)]
    if not adressen:
        melde(f"Sitemap ohne Festivalseiten: {FV}")
    return sorted(set(adressen))


def fv_lesen(url: str, html: str) -> dict | None:
    for d in json_ld_events(html):
        name = clean(str(d.get("name", "")))
        if not name:
            continue
        ort = d.get("location") or {}
        anschrift = ort.get("address") or {}
        land = str(anschrift.get("addressCountry", ""))
        # "XW" steht bei dieser Quelle für die Spielwelt: Konzerte in Minecraft
        # und Roblox. Die gibt es wirklich - hinfahren kann man nicht.
        if land.upper() == "XW" or "online" in str(
                d.get("eventAttendanceMode", "")).lower():
            return None
        stadt = clean(str(anschrift.get("addressLocality", ""))).split(",")[0]
        return datensatz("festivism", url, name, city=stadt, country=land)
    return None


# --------------------------------------------------------------------------
# festivalnetworks.com — 624 Festivals in einer Datei
# --------------------------------------------------------------------------
# Die Karte der Seite lädt ihre Punkte aus einer JSON-Datei. Die zu lesen ist
# genauer und schonender als 624 Seiten einzeln abzurufen.

#: "27-Aug-26"
FN_DATUM = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{2})$")


def fn_datum(roh: str) -> str:
    m = FN_DATUM.match(clean(roh))
    if not m:
        return ""
    monat = monat_nummer(m.group(2))
    return f"{int(m.group(1)):02d}.{monat:02d}.20{m.group(3)}" if monat else ""


def fn_feed(since: int) -> list[dict]:
    roh = fetch(f"{FN}/data-api.php?r=festivals")
    try:
        eintraege = json.loads(roh or "[]")
    except json.JSONDecodeError:
        melde(f"Datei nicht lesbar: {FN}")
        return []
    funde = []
    for e in eintraege:
        name = clean(str(e.get("Festival Name", "")))
        von = fn_datum(str(e.get("Start Date", "")))
        if not name or (von and int(von[-4:]) < since):
            continue
        preis = e.get("Ticket Price (EUR)")
        funde.append(datensatz(
            "festivalnetworks", f"{FN}/#{name}", name,
            date_from=von, date_to=fn_datum(str(e.get("End Date", ""))),
            city=clean(str(e.get("City/Region", ""))).split(",")[0],
            country=str(e.get("Country", "")),
            lat=zahl_oder_nichts(e.get("Latitude")),
            lon=zahl_oder_nichts(e.get("Longitude")),
            website=str(e.get("Website", "")),
            genre=genres_vereinen(str(e.get("Genre", "")), str(e.get("Sub-Genre", ""))),
            visitors=str(e.get("Capacity", "") or ""),
            price=f"ca. {preis} €" if isinstance(preis, (int, float)) and preis else ""))
    return funde

QUELLEN = [
    Quelle("festivalticker", ft_adressen, ft_lesen, mit_stammdaten=True),
    Quelle("festivalsunited", fu_adressen, fu_lesen),
    Quelle("festivalalarm", fa_adressen, fa_lesen),
    Quelle("festivalhopper", fh_adressen, fh_lesen),
    Quelle("festapp", fp_adressen, fp_lesen),
    Quelle("wannafest", wf_adressen, wf_lesen),
    Quelle("festivalflyer", fl_adressen, fl_lesen),
    Quelle("festivalfinder", ff_adressen, ff_lesen),
    # Weltweit. Sie stehen hinten, weil die deutschsprachigen Quellen die
    # gewohnte Schreibweise deutscher Festivals führen - der Rang entscheidet,
    # welcher Name gewinnt.
    Quelle("festivalabroad", fb_adressen, fb_lesen),
    Quelle("jambase", jb_adressen, jb_lesen),
    Quelle("festivalnetworks", lambda _since: [], lambda *_a: None, feed=fn_feed),
    Quelle("festivism", fv_adressen, fv_lesen),
]

#: Rang je Quelle für das Zusammenführen
RANG = {q.name: i for i, q in enumerate(QUELLEN)}
