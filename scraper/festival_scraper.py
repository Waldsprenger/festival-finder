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
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "cache"
OUT = BASE / "data"
CACHE.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

FT = "https://www.festivalticker.de"
FU = "https://www.festivalsunited.com"

FT_LISTS = [f"{FT}/alle-festivals/", f"{FT}/festivals-2027/"]
FU_LISTS = [f"{FU}/festivals/countries/europe", f"{FU}/festivals/countries/germany"]

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
    v = v.replace("ß", "ss").replace("ø", "o").replace("æ", "ae").replace("đ", "d")
    for a, b in REPLACEMENTS.items():
        v = v.replace(a, b)
    v = re.sub(r"\b(feat|ft|featuring|vs|with|und|and)\b", " and ", v)
    v = re.sub(r"[^a-z0-9]+", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    v = re.sub(r"^(the|die|der|das|los|las|les)\s+", "", v)
    v = re.sub(r"\s+(band|live|dj ?set|djset|acoustic)$", "", v)
    return v.strip()


def band_key(name: str) -> str:
    return _fold(name)


def festival_key(name: str) -> str:
    v = _fold(name)
    v = re.sub(r"\b(19|20)\d{2}\b", " ", v)
    v = re.sub(r"\b(festival|fest|open air|openair|open|air)\b", " ", v)
    return re.sub(r"\s+", " ", v).strip() or _fold(name)


def valid_band(name: str) -> bool:
    n = clean(name)
    if len(n) < 2 or len(n) > 90:
        return False
    if BAND_NOISE.match(n):
        return False
    if not re.search(r"[A-Za-zÀ-ÿ0-9]", n):
        return False
    return True


def canonical_band(variants: list[str]) -> str:
    """Waehlt die haeufigste, bei Gleichstand die laengste/sauberste Schreibweise."""
    counts: dict[str, int] = {}
    for v in variants:
        counts[v] = counts.get(v, 0) + 1
    def score(item):
        name, cnt = item
        has_case = name != name.lower() and name != name.upper()
        return (cnt, has_case, -name.count("."), len(name))
    return max(counts.items(), key=score)[0]


# --------------------------------------------------------------------------
# festivalticker.de
# --------------------------------------------------------------------------

def _iso_to_de(value: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else ""


def ft_collect_seeds() -> dict[str, dict]:
    """Stammdaten je Festival aus den Listenseiten (Name, Datum, Ort, Land, Stil)."""
    seeds: dict[str, dict] = {}
    for url in FT_LISTS:
        html = fetch(url)
        if not html:
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

FT_BANDS_END = re.compile(r"\s*(?:Neues zu:|Kommentare zu:|Zurück\b|Zum Festivalplaner)")


def ft_split_bands(blob: str) -> list[str]:
    if not blob:
        return []
    blob = FT_BANDS_END.split(blob)[0]
    return [clean(p) for p in blob.split(",") if valid_band(p)]


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

    text = s.get_text("\n", strip=True)
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
                website = ft_resolve_website(urljoin(url, a["href"]))
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
        "location": place or seed.get("city", ""),
        "price": fields.get("Preis", ""),
        "website": website,
        "genre": fields.get("Stil", "") or seed.get("genre", "") or fields.get("Kategorie", ""),
        "visitors": fields.get("Besucher", ""),
        "note": "",
        "lineup": bands,
    }


def ft_resolve_website(link: str) -> str:
    """festivalticker verlinkt extern ueber /link/?url=... bzw. Redirects."""
    q = parse_qs(urlparse(link).query)
    for key in ("url", "u", "link", "goto"):
        if key in q and q[key]:
            return q[key][0]
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

def fu_collect_links() -> list[str]:
    links: dict[str, None] = {}
    for url in FU_LISTS:
        html = fetch(url)
        if not html:
            print(f"  ! Liste nicht ladbar: {url}", file=sys.stderr)
            continue
        for a in soup(html).find_all("a", href=True):
            href = a["href"]
            if re.match(r"^/festivals/[a-z0-9\-]+(?:/\d{4})?$", href):
                links[urljoin(FU, href)] = None
    return list(links)


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

    website = ""
    for a in s.find_all("a", href=True):
        href = a["href"]
        label = clean(a.get_text()).lower()
        if "festivalsunited.com" in href or href.startswith("/"):
            continue
        if re.search(r"offizielle|website|webseite|homepage", label) or \
           re.search(r"offizielle|website|homepage", clean(a.get("title", "")), re.I):
            website = href
            break

    lineup = fu_extract_lineup(s)

    genre = ""
    gm = re.search(r"ist ein ([A-Za-zÄÖÜäöü&\- ]{3,40}?) Festival", text)
    if gm:
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
        "location": ", ".join(x for x in [city, country] if x),
        "price": price,
        "website": website,
        "genre": genre,
        "visitors": "",
        "note": note,
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
    registry = {k: canonical_band(v) for k, v in variants.items() if k}
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


def merge(records: list[dict], registry: dict[str, str]) -> list[dict]:
    """Zusammenfuehren in zwei Stufen.

    1. Exakt: gleicher Festivalname + Jahr + Stadt. Damit bleiben Tour-Formate
       wie das Irish Spring Festival (30 Staedte) getrennte Eintraege.
    2. Quellenabgleich: gibt es zu Name+Jahr genau einen Eintrag je Quelle,
       werden diese verbunden, auch wenn die Ortsschreibweise abweicht.
    """
    merged: dict[tuple[str, str, str], dict] = {}
    for rec in records:
        key = (festival_key(rec["name"]), rec.get("year", ""), city_key(rec["city"]))
        cur = merged.get(key)
        if cur is None:
            cur = {
                "name": rec["name"],
                "year": rec.get("year", ""),
                "date_from": rec["date_from"],
                "date_to": rec["date_to"],
                "city": rec["city"],
                "country": rec["country"],
                "venue": rec["venue"],
                "location": rec["location"],
                "price": rec["price"],
                "website": rec["website"],
                "genre": rec["genre"],
                "visitors": rec["visitors"],
                "note": rec.get("note", ""),
                "sources": {},
                "source_order": 0 if rec["source"] == "festivalticker" else 1,
                "_bands": {},
            }
            merged[key] = cur
        # laengerer/gefuellter Wert gewinnt
        for field in ("date_from", "date_to", "city", "country", "venue",
                      "location", "price", "website", "genre", "visitors", "note"):
            if not cur[field] and rec[field]:
                cur[field] = rec[field]
        if len(rec["name"]) > len(cur["name"]) and rec["source"] == "festivalticker":
            cur["name"] = rec["name"]
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
        if len(group) != 2:
            continue
        (ka, a), (kb, b) = group
        if set(a["sources"]) & set(b["sources"]) or len(a["sources"]) != 1 or len(b["sources"]) != 1:
            continue
        keep, drop, drop_key = (a, b, kb) if a["source_order"] <= b["source_order"] else (b, a, ka)
        for field in ("date_from", "date_to", "city", "country", "venue",
                      "location", "price", "website", "genre", "visitors", "note"):
            if not keep[field] and drop[field]:
                keep[field] = drop[field]
        keep["sources"].update(drop["sources"])
        keep["_bands"].update(drop["_bands"])
        merged.pop(drop_key, None)

    # Stufe 3: gleiche Veranstaltung, unterschiedlich benannt.
    # "Kosmos Festival" (festivalticker) und "Kosmos Festival Chemnitz"
    # (festivalsunited) sind dasselbe. Verlangt werden verschiedene Quellen,
    # gleiche Stadt, gleicher Starttermin und ein gemeinsamer Namensbestandteil.
    # Der Starttermin ist der entscheidende Schutz: "Winter Wutzrock" im Februar
    # und "Wutzrock" im August teilen Stadt und Namen, sind aber zwei Feste.
    slots: dict[tuple[str, str, str], list[tuple]] = {}
    for key, rec in merged.items():
        if rec["date_from"] and rec["city"]:
            slots.setdefault((rec["year"], key[2], rec["date_from"]), []).append((key, rec))

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
                keep, drop, drop_key = ((a, b, kb) if a["source_order"] <= b["source_order"]
                                        else (b, a, ka))
                for field in ("date_from", "date_to", "city", "country", "venue",
                              "location", "price", "website", "genre", "visitors", "note"):
                    if not keep[field] and drop[field]:
                        keep[field] = drop[field]
                keep["sources"].update(drop["sources"])
                keep["_bands"].update(drop["_bands"])
                merged.pop(drop_key, None)
                if drop_key == ka:
                    break

    out = []
    for rec in merged.values():
        rec.pop("source_order", None)
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
                    "Webseite", "Genre", "Besucher", "Hinweis", "Anzahl Acts",
                    "Lineup", "Quellen"])
        for f in festivals:
            w.writerow([f["name"], f["year"], f["date_from"], f["date_to"], f["city"],
                        f["country"], f["venue"], f["price"], f["website"], f["genre"],
                        f["visitors"], f.get("note", ""), f["lineup_count"],
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
    args = ap.parse_args()

    global MAX_AGE_H
    MAX_AGE_H = args.max_age

    t0 = time.time()
    print("Sammle Detail-Links ...", flush=True)
    ft_seeds = ft_collect_seeds()
    ft_links = list(ft_seeds)
    fu_links = fu_collect_links()
    print(f"  festivalticker: {len(ft_links)} | festivalsunited: {len(fu_links)}", flush=True)
    if args.limit:
        ft_links, fu_links = ft_links[:args.limit], fu_links[:args.limit]

    records = scrape(ft_links, ft_parse_detail, "festivalticker", ft_seeds)
    records += scrape(fu_links, fu_parse_detail, "festivalsunited")
    print(f"Datensaetze: {len(records)}", flush=True)

    registry, bstats = build_band_registry(records)
    festivals = merge(records, registry)
    write_outputs(festivals)
    (OUT / "band_normalisierung.json").write_text(
        json.dumps(bstats, ensure_ascii=False, indent=2), encoding="utf-8")

    both = sum(1 for f in festivals if len(f["sources"]) > 1)
    acts = len({b for f in festivals for b in f["lineup"]})
    print(f"\nFestivals gesamt : {len(festivals)}")
    print(f"  davon in beiden Quellen: {both}")
    print(f"  mit Lineup            : {sum(1 for f in festivals if f['lineup'])}")
    print(f"Acts (normalisiert)     : {acts}")
    print(f"  Rohschreibweisen      : {bstats['roh_schreibweisen']}, davon "
          f"{bstats['vereinheitlicht']} auf eine Schreibweise vereinheitlicht")
    if FAILED:
        print(f"Nicht ladbar: {len(FAILED)} Seiten (siehe data/failed.txt)")
        (OUT / "failed.txt").write_text("\n".join(FAILED), encoding="utf-8")
    print(f"Dauer: {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
