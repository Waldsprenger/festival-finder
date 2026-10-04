"""Aus site/ eine einzige, in sich geschlossene HTML-Datei.

Eine veröffentlichte Einzelseite darf keine externen Dateien nachladen. CSS,
Daten und Skripte stehen deshalb inline, die Geodaten gleich hinter den Daten
(die Seite lädt sie sonst nach), und die beiden Rechtstexte als Abschnitte.
Welche Skripte in welcher Reihenfolge, steht in `index.html`.
"""

import re

from ..pfade import SITE, schreib_text
from .seitenteile import skripte, stile

ZIEL = SITE / "artifact.html"


def lies(name: str) -> str:
    """Eine Datei aus site/; was fehlt (config.js), bleibt leer."""
    pfad = SITE / name
    return pfad.read_text(encoding="utf-8") if pfad.exists() else ""


def html_ascii(text: str) -> str:
    """Sonderzeichen als HTML-Entities."""
    return text.encode("ascii", "xmlcharrefreplace").decode("ascii")


def js_ascii(text: str) -> str:
    """Sonderzeichen als \\uXXXX — Entities wirken im <script> nicht, und die
    Einzeldatei hat keinen <head> für eine Zeichensatzangabe."""
    raus = []
    for ch in text:
        cp = ord(ch)
        if cp < 128:
            raus.append(ch)
        elif cp > 0xFFFF:                       # Ersatzzeichenpaar
            v = cp - 0x10000
            raus.append(f"\\u{0xD800 + (v >> 10):04x}\\u{0xDC00 + (v & 0x3FF):04x}")
        else:
            raus.append(f"\\u{cp:04x}")
    return "".join(raus)


def artikel_von(html: str) -> str:
    m = re.search(r'<article class="legal">(.*?)</article>', html, re.S)
    # Rückverweise auf index.html ergeben in der Einzelseite keinen Sinn
    return re.sub(r'<a class="back".*?</a>', "", m.group(1) if m else "", flags=re.S).strip()


def bauen() -> dict:
    css = "\n".join(lies(d) for d in stile())
    # orte.js bleibt draußen: zehn Megabyte für eine Ortssuche, die dort ohnehin
    # keinen fremden Dienst erreichen darf.
    namen = []
    for d in skripte():
        if d != "orte.js":
            namen.append(d)
            if d == "data.js":
                namen.append("geo.js")
    bloecke = "\n".join(f"<script>\n{js_ascii(inhalt)}\n</script>"
                        for d in namen if (inhalt := lies(d)))

    m = re.search(r"<body[^>]*>(.*)</body>", lies("index.html"), re.S)
    koerper = re.sub(r"<script[^>]*></script>\s*", "", m.group(1) if m else "")
    # Fußnavigation zeigt auf die Abschnitte derselben Seite
    koerper = (koerper.replace('href="impressum.html"', 'href="#impressum"')
                      .replace('href="datenschutz.html"', 'href="#datenschutz"'))
    rechtstexte = (f'\n<section class="legal" id="impressum">\n'
                   f'{artikel_von(lies("impressum.html"))}\n</section>\n'
                   f'<section class="legal" id="datenschutz">\n'
                   f'{artikel_von(lies("datenschutz.html"))}\n</section>\n')

    doc = f"""<title>Festival Finder &#8212; Lineup-Abgleich weltweit</title>
<style>
/* Die Seite ist bewusst durchgehend dunkel (Konzertplakat) und uebernimmt
   keine helle Darstellung des Betrachters. */
:root {{ color-scheme: dark; }}
html, body {{ background: #0b0b0d; }}
{html_ascii(css)}
</style>
{html_ascii(koerper)}
{html_ascii(rechtstexte)}
{bloecke}
"""
    schreib_text(ZIEL, doc)
    return {"mb": ZIEL.stat().st_size / 1e6, "skripte": namen, "stile": stile()}
