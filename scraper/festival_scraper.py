"""Scraper fuer europaeische Festivals (festivalticker.de + festivalsunited.com).

Sammelt Name, Datum, Ort, Preis, offizielle Webseite und Lineup,
fuehrt die Quellen zusammen und normalisiert Bandnamen.

Aufruf:
    python festival_scraper.py            # alles (Listen + Details)
    python festival_scraper.py --limit 20 # Testlauf mit wenigen Details
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import re
import sys
import threading
import time
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemeinsam import (  # noqa: E402  (Pfad muss vorher stehen)
    BASE, CACHE, DATA as OUT, HEADERS, ausser_europa, land_code)

FT = "https://www.festivalticker.de"
FU = "https://www.festivalsunited.com"
FA = "https://www.festival-alarm.com"

# Jahrgaenge, die abgeklopft werden. Die Obergrenze waechst mit der Zeit mit,
# damit kuenftige Jahre (2028, 2029 ...) ohne Codeaenderung erfasst werden.
JAHR_HEUTE = date.today().year
JAHRE = range(2006, JAHR_HEUTE + 6)
MONATE = ["januar", "februar", "maerz", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "dezember"]

# Saemtliche Listenseiten von festivalticker. Die Jahresarchive zeigen jeweils
# nur 40 Eintraege - mehr gibt die Seite fuer vergangene Jahre nicht her.
FT_LISTS = (
    [f"{FT}/alle-festivals/", f"{FT}/alle-festivals-ab-jetzt/",
     f"{FT}/festivals-in-deutschland/", f"{FT}/internationale-festivals/",
     f"{FT}/laufende-festivals/", f"{FT}/neue-festivals/"]
    + [f"{FT}/festivals-{m}/" for m in MONATE]
    + [f"{FT}/festivals-{j}/" for j in JAHRE]
    + [f"{FT}/{j}/" for j in JAHRE]
)

# festivalsunited pflegt eine Sitemap - der vollstaendige Weg ueber alle Jahre
FU_SITEMAP = f"{FU}/sitemap.xml"

# Pfade unter /festivals/, die keine Einzelveranstaltung sind
FU_KEINE_DETAILS = {"calendar", "countries", "lists", "genres", "months",
                    "cities", "venues", "artists", "search", "upcoming",
                    "new", "top", "magazine"}

# festival-alarm listet je Jahrgang eine Uebersichtsseite, die Adressen baut
# fa_collect_links selbst aus JAHRE.

_throttle = threading.Semaphore(4)
_session = threading.local()
FAILED: list[str] = []


def session() -> requests.Session:
    s = getattr(_session, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        _session.s = s
    return s


MAX_AGE_H = 24.0     # per --max-age gesetzt; aelterer Cache wird neu geladen


def fetch(url: str, retries: int = 3) -> str | None:
    """GET mit Plattencache; gibt None zurueck, wenn die Seite nicht ladbar ist."""
    key = hashlib.sha1(url.encode()).hexdigest() + ".html"
    path = CACHE / key
    if path.exists() and path.stat().st_size > 0:
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if MAX_AGE_H <= 0 or age_h < MAX_AGE_H:
            return path.read_text(encoding="utf-8", errors="replace")
    for attempt in range(retries):
        try:
            with _throttle:
                r = session().get(url, timeout=45)
                time.sleep(0.3)
            if r.status_code in (404, 410):
                return None
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            path.write_text(r.text, encoding="utf-8", errors="replace")
            return r.text
        except Exception as exc:
            if attempt == retries - 1:
                FAILED.append(f"{url} ({exc.__class__.__name__})")
                return None
            time.sleep(2.0 * (attempt + 1))
    return None


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Normalisierung
# --------------------------------------------------------------------------

BAND_NOISE = re.compile(
    r"^(uvm|u\.v\.m\.|und viele mehr|alle artists|t\.b\.a\.?|tba|mehr|close|"
    r"line ?-?up|weitere|special guest[s]?|support|n/a|-{1,3})$", re.I)

REPLACEMENTS = {
    "&": " and ", "+": " and ", "’": "'", "´": "'", "`": "'",
    "–": "-", "—": "-", "…": "",
}


def _fold(value: str) -> str:
    """Aggressiver Schluessel fuer den Namensvergleich."""
    v = unicodedata.normalize("NFKD", value.lower())
    v = "".join(c for c in v if not unicodedata.combining(c))
    # Buchstaben, die NFKD nicht zerlegt - sonst fielen sie ersatzlos weg und
    # "Aħna" wuerde zu "Ana"
    for a, b in (("ß", "ss"), ("ø", "o"), ("æ", "ae"), ("œ", "oe"), ("đ", "d"),
                 ("ħ", "h"), ("ł", "l"), ("ı", "i"), ("þ", "th"), ("ð", "d")):
        v = v.replace(a, b)
    for a, b in REPLACEMENTS.items():
        v = v.replace(a, b)
    v = re.sub(r"\b(feat|ft|featuring|vs|with|und|and)\b", " and ", v)
    v = re.sub(r"[^a-z0-9]+", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    v = re.sub(r"^(the|die|der|das|los|las|les)\s+", "", v)
    v = re.sub(r"\s+(band|live|dj ?set|djset|acoustic)$", "", v)
    return v.strip()


# Abkuerzungen, die keine Normalisierung erkennen kann. Die Zuordnung steht in
# data/band_aliase.json und laesst sich dort ohne Codeaenderung erweitern.
# Vorsicht bei Kuerzeln: "TBS" ist hier belegt, weil das Zeltfestival Ruhr beide
# Schreibweisen im selben Lineup fuehrt - anderswo kann dasselbe Kuerzel eine
# andere Band meinen.
def _lade_aliase() -> tuple[dict[str, str], dict[str, str]]:
    pfad = OUT / "band_aliase.json"
    if not pfad.exists():
        return {}, {}
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    schluessel = {_fold(k): v for k, v in roh.items()}
    ziele = {_fold(v): v for v in roh.values()}
    return schluessel, ziele


ALIAS_KEY, ALIAS_NAME = _lade_aliase()


def band_key(name: str) -> str:
    k = _fold(name)
    ziel = ALIAS_KEY.get(k)
    if ziel:
        k = _fold(ziel)
    # Getrennt- und Zusammenschreibung meint dieselbe Band ("1000 Mods" und
    # "1000mods"). Bei kurzen Namen bleibt die Trennung erhalten, weil dort
    # verschiedene Acts zusammenfielen ("B-One" und "Bone").
    eng = k.replace(" ", "")
    return eng if len(eng) >= 5 else k


def festival_key(name: str) -> str:
    v = _fold(name)
    v = re.sub(r"\b(19|20)\d{2}\b", " ", v)
    v = re.sub(r"\b(festival|fest|open air|openair|open|air)\b", " ", v)
    return re.sub(r"\s+", " ", v).strip() or _fold(name)


BAND_DATE = re.compile(r"^\d{1,2}\.\s?\d{1,2}\.\d{2,4}\b")

# Reste aus Beschreibungstexten, die keine Bandnamen sind
BAND_FELD = re.compile(r"\b(?:VVK|AK|Kategorie:|Preis:|Besucher:|Camping|"
                       r"Rahmenprogramm|zum kompletten Programm)\b", re.I)
BAND_SATZ = re.compile(r"\b(?:ist|sind|wird|werden|findet|treffen|startet|sorgen|"
                       r"bestätigt|außerdem)\b", re.I)


def valid_band(name: str) -> bool:
    n = clean(name)
    if len(n) < 2 or len(n) > 90:
        return False
    if BAND_NOISE.match(n):
        return False
    if not re.search(r"[A-Za-zÀ-ÿ0-9]", n):
        return False
    # Datumsangaben aus dem Fliesstext sind keine Bands:
    # "26. 7.2026" oder "04.07.2026 Auch der zweite Festivaltag"
    if BAND_DATE.match(n):
        return False
    # Bruchstuecke aus Beschreibungs- und Preisfeldern aussortieren.
    # Satzwoerter erst ab einer Laenge pruefen, die kein Bandname mehr hat -
    # "Werden Wir Uns Wiedersehen" soll nicht durchfallen.
    if BAND_FELD.search(n):
        return False
    if len(n.split()) >= 6 and BAND_SATZ.search(n):
        return False
    return True


def canonical_band(variants: list[str]) -> str:
    """Waehlt die haeufigste, bei Gleichstand die laengste/sauberste Schreibweise."""
    counts: dict[str, int] = {}
    for v in variants:
        counts[v] = counts.get(v, 0) + 1
    def score(item):
        name, cnt = item
        # Grossbuchstabe am Anfang zuerst: sonst gewaenne bei Akronymen wie
        # B.O.S.C.H. die durchgehend kleingeschriebene Variante.
        beginnt_gross = name[:1].isupper()
        has_case = name != name.lower() and name != name.upper()
        return (cnt, beginnt_gross, has_case, -name.count("."), len(name))
    return max(counts.items(), key=score)[0]


# --------------------------------------------------------------------------
# festivalticker.de
# --------------------------------------------------------------------------

def _iso_to_de(value: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else ""


def ft_collect_seeds(since: int = 0) -> dict[str, dict]:
    """Stammdaten je Festival aus den Listenseiten (Name, Datum, Ort, Land, Stil)."""
    seeds: dict[str, dict] = {}
    for url in FT_LISTS:
        html = fetch(url)
        if not html:
            # Kuenftige Jahrgaenge existieren noch nicht - das ist kein Fehler
            jahr = re.search(r"/(?:festivals-)?(\d{4})/?$", url)
            if not (jahr and int(jahr.group(1)) > JAHR_HEUTE + 1):
                print(f"  ! Liste nicht ladbar: {url}", file=sys.stderr)
            continue
        for ev in soup(html).find_all("tbody", class_="vevent"):
            a = ev.find("a", class_="summary")
            if not a or not a.get("href"):
                continue
            link = urljoin(url, a["href"])
            start = ev.find("span", class_="dtstart")
            end = ev.find("span", class_="dtend")

            def val(node):
                if not node:
                    return ""
                vt = node.find("span", class_="value-title")
                return _iso_to_de(vt.get("title", "")) if vt else ""

            date_from = val(start)
            date_to = val(end) or date_from
            loc = ev.find("span", class_="location")
            place = clean(loc.get_text()) if loc else ""
            city = re.sub(r"^\d[\w\- ]*?\s+", "", place).strip() or place
            cm = re.search(r"Land:\s*(\w{2,})", ev.get_text(" ", strip=True))
            if since and date_from and int(date_from[-4:]) < since:
                continue
            style = ev.find("span", title=True)
            seeds[link] = {
                "name": clean(a.get_text()),
                "date_from": date_from,
                "date_to": date_to,
                "city": city,
                "country": (cm.group(1).upper() if cm else ""),
                "genre": clean(style.get("title")) if style else "",
            }
    return seeds


FT_LABELS = ["Stil", "Kategorie", "Preis", "Besucher", "Location", "Plz",
             "Ort", "Strasse", "Land", "Website", "Bands", "Zeiten", "Veranstalter"]

FT_BANDS_END = re.compile(
    r"\s*(?:Neues zu:|Kommentare zu:|Zurück\b|Zum Festivalplaner|\bclose\b|"
    r"Kategorie:|Preis:|Besucher:|Location:|Stil:|Plz:|Ort:|Strasse:|Land:|Website:)")

# Fallback fuer Bandlisten ohne Komma, die stattdessen die Bauform
# "Bandname (Stilbeschreibung)" aneinanderreihen.
FT_BANDS_PAREN = re.compile(r"([^()]+?)\s*\(([^()]{2,60})\)")

# ... oder als Ablaufplan "17:30 Band 19:45 Band" bzw. "18:00 Uhr Band"
FT_BANDS_TIME = re.compile(r"\b\d{1,2}[:.]\d{2}\s*(?:Uhr)?\s*")


def ft_split_bands(blob: str) -> list[str]:
    if not blob:
        return []
    blob = FT_BANDS_END.split(blob)[0].strip()
    if not blob:
        return []

    if "," in blob:
        return [clean(p) for p in blob.split(",") if valid_band(p)]

    # Kein Komma: Die Klammer hinter jedem Namen dient als Trenner.
    # Erst ab zwei Treffern ist das Muster belastbar.
    paare = FT_BANDS_PAREN.findall(blob)
    if len(paare) >= 2:
        namen = [clean(n) for n, _ in paare]
        rest = clean(blob[blob.rfind(")") + 1:])
        if rest:
            namen.append(rest)
        namen = [n for n in namen if valid_band(n) and len(n) <= 60]
        if len(namen) >= 2:
            return namen

    # Ablaufplan mit Uhrzeiten als Trenner
    if len(FT_BANDS_TIME.findall(blob)) >= 2:
        namen = [clean(t) for t in FT_BANDS_TIME.split(blob)]
        namen = [n for n in namen if valid_band(n) and len(n) <= 60]
        if len(namen) >= 2:
            return namen

    # Sonst gibt es keinen verlaesslichen Trenner. Eine Aufteilung nach
    # Leerzeichen wuerde raten und aus "Nebula Allstars" die Band "Nebula"
    # machen - lieber kein Lineup als ein erfundenes. Als einzelner Act gilt
    # der Block nur, wenn er auch wie ein einzelner Name aussieht.
    # "Deep Purple Manfred Mann's Earth Band" sind zwei Acts ohne Trenner -
    # deshalb gilt der Block nur bei kurzer, namensartiger Form als ein Act.
    if valid_band(blob) and len(blob) <= 30 and len(blob.split()) <= 4:
        return [clean(blob)]
    return []


def ft_parse_detail(url: str, html: str, seed: dict | None = None) -> dict | None:
    seed = seed or {}
    s = soup(html)
    name = seed.get("name") or (clean(s.title.get_text()) if s.title else "")
    if not name:
        h2 = s.find("h2")
        name = clean(h2.get_text()) if h2 else ""
    name = re.sub(r"^\d+\.\s*", "", name)             # "35. Wacken Open Air"
    name = re.sub(r"\s+(19|20)\d{2}$", "", name).strip()
    if not name:
        return None

    # Abgesagte Termine: durchgestrichene Ueberschrift plus roter Hinweis
    titel = s.find("h2")
    cancelled = bool(titel and "line-through" in (titel.get("class") or []))

    text = s.get_text("\n", strip=True)
    if re.search(r"wurde abgesagt", text, re.I):
        cancelled = True

    dm = re.search(r"Vom:\s*(\d{2}\.\d{2}\.\d{4})\s*bis:\s*(\d{2}\.\d{2}\.\d{4})", text)
    if dm:
        date_from, date_to = dm.group(1), dm.group(2)
    else:
        one = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
        date_from = date_to = one.group(1) if one else ""
    date_from = seed.get("date_from") or date_from
    date_to = seed.get("date_to") or date_to

    fields: dict[str, str] = {}
    website = ""
    bands: list[str] = []

    for tr in s.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 2:
            continue
        label = clean(tds[0].get_text()).rstrip(":")
        if label not in FT_LABELS:
            continue
        value_td = tds[1]
        if label == "Website":
            a = value_td.find("a", href=True)
            if a:
                website = ft_resolve_website(urljoin(url, a["href"].strip())).strip()
            continue
        if label == "Bands":
            bands.extend(ft_split_bands(clean(value_td.get_text())))
            continue
        val = clean(value_td.get_text())
        # "Stil" wird auf der Seite gekuerzt + vollstaendig ausgegeben
        val = re.sub(r"\s*\.{2,}\s*mehr\s*", " ", val)
        val = re.sub(r"\s*close\s*$", "", val).strip(" ,.")
        fields.setdefault(label, val)

    if not bands:
        flat = clean(s.get_text(" ", strip=True))
        m = re.search(r"\bBands:\s*(.+)$", flat)
        if m:
            bands = ft_split_bands(m.group(1))

    place = ", ".join(x for x in [fields.get("Location", ""), fields.get("Ort", ""),
                                  fields.get("Land", "")] if x)
    return {
        "source": "festivalticker",
        "source_url": url,
        "name": name,
        "date_from": date_from,
        "date_to": date_to,
        "year": date_from[-4:] if date_from else "",
        "city": fields.get("Ort", "") or seed.get("city", ""),
        "country": fields.get("Land", "") or seed.get("country", ""),
        "venue": fields.get("Location", ""),
        "plz": fields.get("Plz", ""),
        "location": place or seed.get("city", ""),
        "price": fields.get("Preis", ""),
        "website": website,
        "genre": fields.get("Stil", "") or seed.get("genre", "") or fields.get("Kategorie", ""),
        "visitors": fields.get("Besucher", ""),
        "note": "",
        "cancelled": cancelled,
        "lineup": bands,
    }


def ft_resolve_website(link: str) -> str:
    """festivalticker verlinkt extern ueber /link/?url=... bzw. Redirects."""
    q = parse_qs(urlparse(link).query)
    for key in ("url", "u", "link", "goto"):
        if key in q and q[key]:
            return q[key][0].strip()
    if "festivalticker.de" not in urlparse(link).netloc:
        return link
    try:
        with _throttle:
            r = session().head(link, allow_redirects=True, timeout=20)
        if "festivalticker.de" not in urlparse(r.url).netloc:
            return r.url
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------
# festivalsunited.com
# --------------------------------------------------------------------------

def fu_collect_links(since: int) -> list[str]:
    """Alle Festivalseiten aus der Sitemap.

    Die Sitemap ist nach Jahrgaengen aufgeteilt (upcoming plus historic-JAHR),
    deshalb laesst sich der Zeitraum ohne einen einzigen ueberfluessigen Abruf
    eingrenzen.
    """
    index = fetch(FU_SITEMAP)
    if not index:
        print("  ! Sitemap nicht ladbar", file=sys.stderr)
        return []

    links: dict[str, None] = {}
    for sub in re.findall(r"<loc>([^<]+)</loc>", index):
        if "festival" not in sub:
            continue
        jahr = re.search(r"historic-(\d{4})", sub)
        if jahr and int(jahr.group(1)) < since:
            continue
        html = fetch(sub)
        if not html:
            continue
        for loc in re.findall(r"<loc>([^<]+)</loc>", html):
            # nur Detailseiten, keine Magazinartikel und keine Buchstabenlisten
            m = re.fullmatch(r"https://www\.festivalsunited\.com/festivals/"
                             r"([a-z0-9\-]+)(?:/\d{4})?", loc)
            # "/festivals/calendar/2026" sieht wie eine Detailseite aus, ist aber
            # eine Uebersicht - sonst landet ein Festival namens "Festivals" in
            # den Daten
            if m and m.group(1) not in FU_KEINE_DETAILS:
                links[loc] = None
    return list(links)


# --------------------------------------------------------------------------
# festival-alarm.com
# --------------------------------------------------------------------------

def fa_collect_links(since: int) -> list[str]:
    links: dict[str, None] = {}
    for jahr in JAHRE:
        if jahr < since:
            continue
        html = fetch(f"{FA}/Festivals-{jahr}")
        if not html:
            continue
        for href in re.findall(rf'href="(/Festivals-{jahr}/[^"]+)"', html):
            links[urljoin(FA, href)] = None
    return list(links)


# Die Werte stehen im Quelltext ueber mehrere Zeilen verteilt, deshalb wird der
# Text zuerst zu einer Zeile geglaettet und jedes Feld bis zur naechsten
# bekannten Beschriftung gelesen.
FA_FELDER = {
    "preis":     r"Festivalticket \(ab\):\s*(.*?)\s*(?:Tagesticket|Ticketshop|Teilnehmer)",
    "stadt":     r"Stadt:\s*(.*?)\s*(?:Bundesland:|Land:)",
    "land":      r"\bLand:\s*(.*?)\s*(?:Veranstaltungsplatz|Wo:|Örtlichkeit|Camping)",
    "genre":     r"Genres:\s*(.*?)\s*(?:Gründung|Festivalausgabe|Besucher)",
    "besucher":  r"Besucher:\s*(.*?)\s*(?:Sonstiges|Weiterführende|Webseite)",
    "acts":      r"Künstler:\s*(.*?)\s*(?:Anreise|Wie komme)",
}

FA_LEER = re.compile(r"^(keine daten|unbekannt|-|)$", re.I)


def fa_parse_detail(url: str, html: str, seed: dict | None = None) -> dict | None:
    s = soup(html)
    h1 = s.find("h1")
    roh = clean(h1.get_text(" ", strip=True)) if h1 else ""
    if not roh:
        return None

    # "Baltic Open Air 19.08. - 21.08.2026"
    dm = re.search(r"(\d{2}\.\d{2}\.)\s*-\s*(\d{2}\.\d{2}\.\d{4})|(\d{2}\.\d{2}\.\d{4})", roh)
    date_from = date_to = ""
    if dm and dm.group(2):
        jahr = dm.group(2)[-4:]
        date_from, date_to = dm.group(1) + jahr, dm.group(2)
    elif dm and dm.group(3):
        date_from = date_to = dm.group(3)
    name = clean(roh[:dm.start()]) if dm else roh
    name = re.sub(r"[\s\-–|]+$", "", name)
    if not name:
        return None

    flach = clean(s.get_text(" ", strip=True))

    feld: dict[str, str] = {}
    for name_feld, muster in FA_FELDER.items():
        m = re.search(muster, flach, re.S)
        wert = clean(m.group(1)) if m else ""
        if wert and not FA_LEER.match(wert):
            feld[name_feld] = wert

    stadt_roh = feld.get("stadt", "")
    plz_m = re.match(r"\s*(\d{4,5})\b", stadt_roh)
    plz = plz_m.group(1) if plz_m else ""
    ort = clean(re.sub(r"^\d{4,5}\s*", "", stadt_roh))
    preis = feld.get("preis", "")
    if preis:
        preis = clean(preis.replace("ca.", "").replace("€", "EUR"))
        preis = "" if not re.search(r"\d", preis) else preis
    if preis and not preis.lower().startswith("ab"):
        preis = f"ab {preis}"

    bands = [clean(b) for b in feld.get("acts", "").split(",") if valid_band(b)]

    website = ""
    for li in s.find_all(["li", "div", "p"]):
        if "Webseite" not in li.get_text():
            continue
        a = li.find("a", href=True)
        if a and a["href"].startswith("http") and "awin1.com" not in a["href"] \
                and "festival-alarm" not in a["href"]:
            website = a["href"].strip()
            break

    return {
        "source": "festivalalarm",
        "source_url": url,
        "name": name,
        "date_from": date_from,
        "date_to": date_to,
        "year": date_from[-4:] if date_from else "",
        "city": ort,
        "country": feld.get("land", ""),
        "venue": "",
        "plz": plz,
        "location": ", ".join(x for x in [ort, feld.get("land", "")] if x),
        "price": preis,
        "website": website,
        "genre": feld.get("genre", ""),
        "visitors": re.sub(r"\D", "", feld.get("besucher", "")),
        "note": "",
        "cancelled": False,
        "lineup": bands,
    }


def fu_extract_lineup(s: BeautifulSoup) -> list[str]:
    """Headliner-Spans + vollstaendige Actliste aus den Line-Up-Karten.

    Die Lineup-Karten stehen nicht zwingend neben der Ueberschrift, daher
    werden sie ueber ihre Auszeichnung erkannt:
      * Headliner: fett, inline 'white-space:nowrap'
      * uebrige Acts: span.text-primary.font-weight-normal, gefolgt von <br/>
    """
    names: dict[str, None] = {}
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
            names[nm] = None
    return list(names)


def fu_parse_detail(url: str, html: str) -> dict | None:
    s = soup(html)
    h1 = s.find("h1")
    raw_name = clean(h1.get_text()) if h1 else ""
    if not raw_name:
        return None
    ym = re.search(r"\b(20\d{2})\b", raw_name)
    year = ym.group(1) if ym else ""
    name = re.sub(r"\s*\b20\d{2}\b\s*$", "", raw_name).strip()

    text = re.sub(r"\n{2,}", "\n", s.get_text("\n", strip=True))

    # Abgesagt? Der Hinweis "Abgesagt" steht auf vielen Seiten auch bei anderen
    # Jahrgaengen in der Ausgabenliste. Gewertet wird deshalb nur der Status im
    # Kopfbereich sowie der Klartext, der den Namen dieser Ausgabe nennt.
    cancelled = bool(re.search(re.escape(raw_name) + r"\s+wurde abgesagt", text, re.I))
    if not cancelled:
        kopf = h1.find_parent(["section", "div"])
        if kopf and re.search(r"\bAbgesagt\b", kopf.get_text(" ", strip=True), re.I):
            cancelled = True

    # Seiten ohne bestaetigte Neuauflage zeigen das Datum der letzten Ausgabe.
    # Deshalb bevorzugt der Treffer, dessen Jahr zur Ausgabe im Titel passt.
    ranges = [(m.group(1), m.group(2) or m.group(1)) for m in
              re.finditer(r"(\d{2}\.\d{2}\.\d{4})(?:\s*-\s*(\d{2}\.\d{2}\.\d{4}))?", text)]
    note = ""
    date_from = date_to = ""
    if ranges:
        match = next((r for r in ranges if r[0][-4:] == year), None) if year else None
        if match:
            date_from, date_to = match
        elif year:
            note = f"Termin offen; letzte gefundene Ausgabe {ranges[0][0]}"
        else:
            date_from, date_to = ranges[0]
    elif year:
        note = "Termin noch nicht veröffentlicht"
    if not year and date_from:
        year = date_from[-4:]

    pm = re.search(r"(?:ab|kosten(?:ten)?\s+ab)\s+((?:EUR|CHF|GBP|USD|DKK|SEK|NOK|PLN|HUF|CZK)\s*[\d.,]+)",
                   text, re.I)
    price = clean(pm.group(1)).rstrip(".,;") if pm else ""
    if price:
        price = "ab " + price

    city = country = ""
    lm = re.search(r"\d{2}\.\d{2}\.\d{4}\s*/\s*([^\n]+)", text)
    if lm:
        city = clean(lm.group(1))
    cm = re.search(r"\bin\s+([A-ZÄÖÜ][^\n,]{1,40}?)\s*\((\w{2})\)", text)
    if cm:
        city = city or clean(cm.group(1))
        country = cm.group(2).upper()

    # Der Fliesstext nennt das Land nur bei europaeischen Ausgaben zuverlaessig.
    # Zwei stille Quellen auf derselben Seite sagen es immer: die eingebettete
    # Adresse und der Link auf die Laenderliste. Ohne sie stand das Suwannee
    # Hulaween aus Florida ohne Land in der Datei - und blieb damit drin,
    # obwohl nur Europa gesammelt wird.
    if not country:
        jm = re.search(r'"addressCountry"\s*:\s*"([^"]{2,40})"', html)
        if jm:
            country = land_code(clean(jm.group(1)))
    if not country:
        # "europe" und "international" sind Sammelseiten, keine Laender
        for km in re.finditer(r'/festivals/countries/([a-z\-]{2,30})"', html):
            slug = km.group(1).replace("-", " ")
            if slug not in ("europe", "international"):
                country = land_code(slug)
                break

    website = ""
    for a in s.find_all("a", href=True):
        href = a["href"]
        label = clean(a.get_text()).lower()
        if "festivalsunited.com" in href or href.startswith("/"):
            continue
        if re.search(r"offizielle|website|webseite|homepage", label) or \
           re.search(r"offizielle|website|homepage", clean(a.get("title", "")), re.I):
            website = href.strip()
            break

    lineup = fu_extract_lineup(s)

    # "... ist ein Rock Festival" nennt die Richtung, "... ist ein Angebot von
    # Live Nation Festival" dagegen den Veranstalter. Ohne diese Grenze stand
    # bei 14 Festivals der Anbieter als Genre.
    genre = ""
    gm = re.search(r"ist ein ([A-Za-zÄÖÜäöü&\- ]{3,40}?) Festival", text)
    if gm and not re.match(r"(?i)angebot\b", gm.group(1).strip()):
        genre = clean(gm.group(1))

    return {
        "source": "festivalsunited",
        "source_url": url,
        "name": name,
        "date_from": date_from,
        "date_to": date_to,
        "year": year,
        "city": city,
        "country": country,
        "venue": "",
        "plz": "",
        "location": ", ".join(x for x in [city, country] if x),
        "price": price,
        "website": website,
        "genre": genre,
        "visitors": "",
        "note": note,
        "cancelled": cancelled,
        "lineup": lineup,
    }


# --------------------------------------------------------------------------
# Zusammenfuehren
# --------------------------------------------------------------------------

def scrape(urls: list[str], parser, label: str, seeds: dict | None = None) -> list[dict]:
    results: list[dict] = []
    done = 0
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, u): u for u in urls}
        for fut in cf.as_completed(futures):
            u = futures[fut]
            done += 1
            if done % 100 == 0:
                print(f"  {label}: {done}/{len(urls)}", flush=True)
            html = fut.result()
            if not html:
                continue
            try:
                rec = parser(u, html, seeds[u]) if seeds else parser(u, html)
            except Exception as exc:
                print(f"  ! Parsefehler {u}: {exc}", file=sys.stderr)
                continue
            if rec and rec["name"]:
                results.append(rec)
    return results


def build_band_registry(records: list[dict]) -> tuple[dict[str, str], dict]:
    variants: dict[str, list[str]] = {}
    for rec in records:
        for b in rec["lineup"]:
            variants.setdefault(band_key(b), []).append(clean(b))
    # Ein hinterlegter Alias schlaegt die Mehrheitsregel: sonst gewaenne bei
    # gleicher Haeufigkeit die Abkuerzung statt des ausgeschriebenen Namens.
    registry = {k: ALIAS_NAME.get(k) or canonical_band(v)
                for k, v in variants.items() if k}
    distinct = {k: sorted(set(v)) for k, v in variants.items() if k}
    stats = {
        "roh_schreibweisen": sum(len(v) for v in distinct.values()),
        "gruppen": len(registry),
        "vereinheitlicht": sum(len(v) - 1 for v in distinct.values() if len(v) > 1),
        "beispiele": [(registry[k], v) for k, v in distinct.items() if len(v) > 1][:400],
    }
    return registry, stats


def city_key(value: str) -> str:
    v = re.sub(r"\b\d{4,6}\b", " ", value or "")       # PLZ entfernen
    return _fold(v)


def genre_merge(*werte: str) -> str:
    """Genres aller Quellen sammeln; doppelte Angaben fallen weg.

    Frueher gewann die erste gefuellte Quelle und die uebrigen verfielen. Bei
    "Rock im Park" blieb so das festivalsunited-Wort "genreuebergreifendes"
    stehen, waehrend festival-alarm acht konkrete Richtungen nennt. Die
    Vereinigung ist naeher an der Wahrheit als jede Quelle allein - und der
    Abgleich ohne Gross-/Kleinschreibung raeumt die Wiederholungen weg, die
    einzelne Quellseiten in ihrer eigenen Aufzaehlung haben.
    """
    gesehen: dict[str, str] = {}
    for wert in werte:
        for teil in (wert or "").split(","):
            teil = clean(teil)
            if teil:
                gesehen.setdefault(teil.casefold(), teil)
    return ", ".join(gesehen.values())


def tag_zahl(datum: str) -> int:
    """TT.MM.JJJJ als vergleichbare Zahl; 0, wenn nichts dasteht."""
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", datum or "")
    return int(m.group(3) + m.group(2) + m.group(1)) if m else 0


def zeitraum_ueberlappt(a: dict, b: dict) -> bool:
    """Ueberschneiden sich die beiden Termine?

    Die Quellen zaehlen den Anreise- oder Warmup-Tag verschieden: Das Neuborn
    Open Air steht bei festivalticker ab dem 27.08., bei den beiden anderen ab
    dem 28.08. Ein Ueberlapp erfasst solche Faelle, ohne zwei Feste zu
    verschmelzen, die Wochen auseinander liegen.
    """
    a0, b0 = tag_zahl(a["date_from"]), tag_zahl(b["date_from"])
    if not a0 or not b0:
        return False
    a1, b1 = tag_zahl(a["date_to"]) or a0, tag_zahl(b["date_to"]) or b0
    return a0 <= b1 and b0 <= a1


def name_deckt_sich(ka: str, kb: str) -> bool:
    """Strenger Namensvergleich fuer Termine, die nicht am selben Tag beginnen.

    Ein gemeinsames Wort genuegt hier nicht: "METAStadt Open Air Wien" und
    "Afrika Tage Wien" teilen sich die Stadt im Namen und sind zwei
    Veranstaltungen. Verlangt wird, dass ein Name vollstaendig im anderen
    steckt ("Neuborn" in "NOAF Neuborn") oder beide ohne Leerzeichen gleich
    sind ("R.O.I. Rock On Isens" und "ROI Rock On Isens").
    """
    ta, tb = set(ka.split()), set(kb.split())
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    return ka.replace(" ", "") == kb.replace(" ", "")


def merge(records: list[dict], registry: dict[str, str]) -> list[dict]:
    """Zusammenfuehren in zwei Stufen.

    1. Exakt: gleicher Festivalname + Jahr + Stadt. Damit bleiben Tour-Formate
       wie das Irish Spring Festival (30 Staedte) getrennte Eintraege.
    2. Quellenabgleich: gibt es zu Name+Jahr genau einen Eintrag je Quelle,
       werden diese verbunden, auch wenn die Ortsschreibweise abweicht.
    """
    merged: dict[tuple[str, str, str], dict] = {}
    for rec in records:
        if ausser_europa(rec["country"]):
            continue
        key = (festival_key(rec["name"]), rec.get("year", ""), city_key(rec["city"]))
        cur = merged.get(key)
        if cur is None:
            cur = {
                "name": rec["name"],
                "year": rec.get("year", ""),
                "date_from": rec["date_from"],
                "date_to": rec["date_to"],
                "city": rec["city"],
                "country": land_code(rec["country"]),
                "venue": rec["venue"],
                "plz": rec.get("plz", ""),
                "location": rec["location"],
                "price": rec["price"],
                "website": rec["website"],
                "genre": rec["genre"],
                "visitors": rec["visitors"],
                "note": rec.get("note", ""),
                "cancelled": bool(rec.get("cancelled")),
                "sources": {},
                "source_order": {"festivalticker": 0, "festivalsunited": 1}
                                .get(rec["source"], 2),
                "_bands": {},
            }
            merged[key] = cur
        # laengerer/gefuellter Wert gewinnt; das Genre sammelt statt zu ersetzen
        for field in ("date_from", "date_to", "city", "venue", "plz",
                      "location", "price", "website", "visitors", "note"):
            if not cur[field] and rec.get(field):
                cur[field] = rec[field]
        cur["genre"] = genre_merge(cur["genre"], rec.get("genre", ""))
        if not cur["country"]:
            cur["country"] = land_code(rec["country"])
        if len(rec["name"]) > len(cur["name"]) and rec["source"] == "festivalticker":
            cur["name"] = rec["name"]
        # Eine Absage aus einer Quelle genuegt
        cur["cancelled"] = cur["cancelled"] or bool(rec.get("cancelled"))
        cur["sources"][rec["source"]] = rec["source_url"]
        for b in rec["lineup"]:
            k = band_key(b)
            if k:
                cur["_bands"][k] = registry.get(k, clean(b))

    # Stufe 2: eindeutige Quellenpaare ueber abweichende Ortsschreibweisen hinweg
    by_name: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in merged.items():
        by_name.setdefault((key[0], key[1]), []).append((key, rec))
    for group in by_name.values():
        if len(group) < 2:
            continue
        # Jede Gruppe muss aus genau einer Quelle stammen und die Quellen
        # muessen sich unterscheiden - sonst waeren es echte Parallelveranstaltungen.
        if any(len(rec["sources"]) != 1 for _, rec in group):
            continue
        quellen = [next(iter(rec["sources"])) for _, rec in group]
        if len(set(quellen)) != len(quellen):
            continue

        group = sorted(group, key=lambda kr: kr[1]["source_order"])
        _, keep = group[0]
        for drop_key, drop in group[1:]:
            for field in ("date_from", "date_to", "city", "country", "venue",
                          "location", "price", "website", "visitors", "note"):
                if not keep[field] and drop[field]:
                    keep[field] = drop[field]
            keep["genre"] = genre_merge(keep["genre"], drop["genre"])
            keep["cancelled"] = keep["cancelled"] or drop["cancelled"]
            keep["sources"].update(drop["sources"])
            keep["_bands"].update(drop["_bands"])
            merged.pop(drop_key, None)

    # Stufe 3: gleiche Veranstaltung, unterschiedlich benannt.
    # "Kosmos Festival" (festivalticker) und "Kosmos Festival Chemnitz"
    # (festivalsunited) sind dasselbe. Verlangt werden verschiedene Quellen,
    # gleiche Stadt, gleicher Starttermin und ein gemeinsamer Namensbestandteil.
    # Der Starttermin ist der entscheidende Schutz: "Winter Wutzrock" im Februar
    # und "Wutzrock" im August teilen Stadt und Namen, sind aber zwei Feste.
    # Gruppiert wird nur nach Jahr und Starttermin; die Stadt wird anschliessend
    # paarweise geprueft, damit auch "Oberndorf" und "Oberndorf am Neckar"
    # zusammenfinden.
    slots: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in merged.items():
        if rec["date_from"] and rec["city"]:
            slots.setdefault((rec["year"], rec["date_from"]), []).append((key, rec))

    for group in slots.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            ka, a = group[i]
            if ka not in merged:
                continue
            for j in range(i + 1, len(group)):
                kb, b = group[j]
                if kb not in merged or ka not in merged:
                    continue
                if set(a["sources"]) & set(b["sources"]):
                    continue
                if not (set(ka[0].split()) & set(kb[0].split())):
                    continue
                # Bei identischem Namensschluessel und identischem Starttermin
                # aus verschiedenen Quellen ist es dieselbe Veranstaltung, auch
                # wenn die Quellen den Ort verschieden benennen (Nachbarort,
                # Gemeinde statt Ortsteil). Tourformate mit gleichem Namen am
                # selben Tag stammen aus derselben Quelle und sind oben schon
                # ausgeschlossen.
                if ka[0] != kb[0]:
                    sa, sb = ka[2], kb[2]
                    if not (sa == sb or sa.startswith(sb + " ") or sb.startswith(sa + " ")):
                        continue
                keep, drop, drop_key = ((a, b, kb) if a["source_order"] <= b["source_order"]
                                        else (b, a, ka))
                for field in ("date_from", "date_to", "city", "country", "venue",
                              "location", "price", "website", "visitors", "note"):
                    if not keep[field] and drop[field]:
                        keep[field] = drop[field]
                keep["genre"] = genre_merge(keep["genre"], drop["genre"])
                keep["cancelled"] = keep["cancelled"] or drop["cancelled"]
                keep["sources"].update(drop["sources"])
                keep["_bands"].update(drop["_bands"])
                merged.pop(drop_key, None)
                if drop_key == ka:
                    break

    # Stufe 4: dieselbe Veranstaltung, von den Quellen einen Tag versetzt datiert.
    # Stufe 3 verlangt denselben Starttermin - daran scheiterte das Neuborn Open
    # Air, das festivalticker ab dem 27.08. fuehrt und die beiden anderen Quellen
    # ab dem 28.08.; uebrig blieben zwei Eintraege mit 17 und mit 4 Bands.
    # Statt des Termins schuetzt hier der strengere Namensvergleich: gleiche
    # Stadt, ueberlappender Zeitraum, verschiedene Quellen und ein Name, der
    # vollstaendig im anderen steckt.
    orte: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in merged.items():
        if rec["date_from"] and rec["city"]:
            orte.setdefault((rec["year"], city_key(rec["city"])), []).append((key, rec))

    for group in orte.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            ka, a = group[i]
            if ka not in merged:
                continue
            for j in range(i + 1, len(group)):
                kb, b = group[j]
                if kb not in merged or ka not in merged:
                    continue
                if set(a["sources"]) & set(b["sources"]):
                    continue
                if not zeitraum_ueberlappt(a, b):
                    continue
                if not name_deckt_sich(ka[0], kb[0]):
                    continue
                keep, drop, drop_key = ((a, b, kb) if a["source_order"] <= b["source_order"]
                                        else (b, a, ka))
                for field in ("date_from", "date_to", "city", "country", "venue",
                              "location", "price", "website", "visitors", "note"):
                    if not keep[field] and drop[field]:
                        keep[field] = drop[field]
                # Der frueheste Beginn und das spaeteste Ende gelten: die Quellen
                # nennen unterschiedliche Teile desselben Festivals.
                if tag_zahl(drop["date_from"]) and (
                        not tag_zahl(keep["date_from"])
                        or tag_zahl(drop["date_from"]) < tag_zahl(keep["date_from"])):
                    keep["date_from"] = drop["date_from"]
                if tag_zahl(drop["date_to"]) > tag_zahl(keep["date_to"]):
                    keep["date_to"] = drop["date_to"]
                keep["genre"] = genre_merge(keep["genre"], drop["genre"])
                keep["cancelled"] = keep["cancelled"] or drop["cancelled"]
                keep["sources"].update(drop["sources"])
                keep["_bands"].update(drop["_bands"])
                merged.pop(drop_key, None)
                if drop_key == ka:
                    break

    out = []
    for rec in merged.values():
        rec.pop("source_order", None)
        # einheitliche Ortsangabe: Ortsname und Laenderkuerzel
        rec["location"] = ", ".join(x for x in [rec["city"], rec["country"]] if x)
        lineup = sorted(set(rec.pop("_bands").values()), key=str.casefold)
        rec["lineup"] = lineup
        rec["lineup_count"] = len(lineup)
        rec["sources"] = rec["sources"]
        out.append(rec)
    out.sort(key=lambda r: (r["year"] or r["date_from"][-4:] or "9999",
                            r["date_from"][3:5] if r["date_from"] else "99",
                            r["date_from"][:2] if r["date_from"] else "99",
                            r["name"].casefold()))
    return out


def write_outputs(festivals: list[dict]) -> None:
    import csv

    (OUT / "festivals.json").write_text(
        json.dumps(festivals, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUT / "festivals.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Name", "Jahr", "Von", "Bis", "Ort", "Land", "Venue", "Preis",
                    "Webseite", "Genre", "Besucher", "Abgesagt", "Hinweis",
                    "Anzahl Acts", "Lineup", "Quellen"])
        for f in festivals:
            w.writerow([f["name"], f["year"], f["date_from"], f["date_to"], f["city"],
                        f["country"], f["venue"], f["price"], f["website"], f["genre"],
                        f["visitors"], "ja" if f["cancelled"] else "",
                        f.get("note", ""), f["lineup_count"],
                        ", ".join(f["lineup"]), " | ".join(f["sources"].values())])

    with (OUT / "lineups.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Band", "Festival", "Von", "Bis", "Ort", "Land"])
        for f in festivals:
            for b in f["lineup"]:
                w.writerow([b, f["name"], f["date_from"], f["date_to"],
                            f["city"], f["country"]])

    # Bands ueber mehrere Festivals hinweg
    bands: dict[str, list[str]] = {}
    for f in festivals:
        for b in f["lineup"]:
            bands.setdefault(b, []).append(f["name"])
    with (OUT / "bands.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Band", "Anzahl Festivals", "Festivals"])
        for b, fs in sorted(bands.items(), key=lambda kv: (-len(kv[1]), kv[0].casefold())):
            w.writerow([b, len(fs), ", ".join(sorted(set(fs)))])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="nur N Detailseiten je Quelle")
    ap.add_argument("--max-age", type=float, default=24.0,
                    help="Cache-Alter in Stunden, ab dem neu geladen wird (0 = nie)")
    ap.add_argument("--since", type=int, default=date.today().year,
                    help="fruehester Jahrgang; 2006 holt das komplette Archiv")
    args = ap.parse_args()

    global MAX_AGE_H
    MAX_AGE_H = args.max_age

    t0 = time.time()
    print(f"Sammle Detail-Links ab Jahrgang {args.since} ...", flush=True)
    ft_seeds = ft_collect_seeds(args.since)
    ft_links = list(ft_seeds)
    fu_links = fu_collect_links(args.since)
    fa_links = fa_collect_links(args.since)
    print(f"  festivalticker {len(ft_links)} | festivalsunited {len(fu_links)} | "
          f"festival-alarm {len(fa_links)}", flush=True)
    if args.limit:
        ft_links = ft_links[:args.limit]
        fu_links = fu_links[:args.limit]
        fa_links = fa_links[:args.limit]

    records = scrape(ft_links, ft_parse_detail, "festivalticker", ft_seeds)
    records += scrape(fu_links, fu_parse_detail, "festivalsunited")
    records += scrape(fa_links, fa_parse_detail, "festival-alarm")
    print(f"Datensaetze: {len(records)}", flush=True)

    registry, bstats = build_band_registry(records)
    festivals = merge(records, registry)
    write_outputs(festivals)
    (OUT / "band_normalisierung.json").write_text(
        json.dumps(bstats, ensure_ascii=False, indent=2), encoding="utf-8")

    abgesagt = sum(1 for f in festivals if f["cancelled"])
    both = sum(1 for f in festivals if len(f["sources"]) > 1)
    acts = len({b for f in festivals for b in f["lineup"]})
    print(f"\nFestivals gesamt : {len(festivals)}")
    print(f"  davon in beiden Quellen: {both}")
    print(f"  mit Lineup            : {sum(1 for f in festivals if f['lineup'])}")
    print(f"  abgesagt              : {abgesagt}")
    print(f"Acts (normalisiert)     : {acts}")
    print(f"  Rohschreibweisen      : {bstats['roh_schreibweisen']}, davon "
          f"{bstats['vereinheitlicht']} auf eine Schreibweise vereinheitlicht")
    if FAILED:
        print(f"Nicht ladbar: {len(FAILED)} Seiten (siehe data/failed.txt)")
        (OUT / "failed.txt").write_text("\n".join(FAILED), encoding="utf-8")
    print(f"Dauer: {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
