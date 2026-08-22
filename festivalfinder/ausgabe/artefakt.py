"""Aus site/ eine einzige, in sich geschlossene HTML-Datei.

Veröffentlichte Artifacts dürfen keine externen Dateien nachladen und bestehen
aus genau einer Seite. Deshalb werden CSS, Daten und Skripte inline gesetzt und
die beiden Rechtstexte als Abschnitte angehängt.

Welche Dateien und in welcher Reihenfolge, steht nicht hier, sondern in
`index.html` — sonst vergisst diese Datei beim nächsten neuen Skript eines.
"""

import re

from ..pfade import SITE, schreib_text
from .seitenteile import skripte, stile

ZIEL = SITE / "artifact.html"


def lies(name: str, pflicht: bool = True) -> str:
    """Liest eine Datei aus site/. Nicht zwingende fehlen sang- und klanglos."""
    pfad = SITE / name
    if not pflicht and not pfad.exists():
        return ""
    return pfad.read_text(encoding="utf-8")


def html_ascii(text: str) -> str:
    """Sonderzeichen als HTML-Entities."""
    return text.encode("ascii", "xmlcharrefreplace").decode("ascii")


def js_ascii(text: str) -> str:
    """Sonderzeichen als \\uXXXX — Entities wirken im <script> nicht.

    Die Einzeldatei hat keinen <head>, in den eine Zeichensatz-Angabe passen
    würde. Ohne diese Absicherung hängt die Darstellung von Umlauten davon ab,
    was der ausliefernde Server als Charset mitschickt.
    """
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


def koerper_von(html: str) -> str:
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    return m.group(1) if m else html


def artikel_von(html: str) -> str:
    m = re.search(r'<article class="legal">(.*?)</article>', html, re.S)
    text = m.group(1) if m else ""
    # Rückverweise auf index.html ergeben in der Einzelseite keinen Sinn
    return re.sub(r'<a class="back".*?</a>', "", text, flags=re.S).strip()


def bauen() -> dict:
    css = "\n".join(lies(d) for d in stile())
    # orte.js bleibt draußen: zehn Megabyte, die die Einzelseite verdoppeln
    # würden, für eine Ortssuche, die dort ohnehin keinen fremden Dienst
    # erreichen darf.
    js = [(d, lies(d, pflicht=(d != "config.js")))
          for d in skripte() if d != "orte.js"]

    koerper = koerper_von(lies("index.html"))
    koerper = re.sub(r"<script[^>]*></script>\s*", "", koerper)
    # Fußnavigation zeigt auf die Abschnitte derselben Seite
    koerper = koerper.replace('href="impressum.html"', 'href="#impressum"')
    koerper = koerper.replace('href="datenschutz.html"', 'href="#datenschutz"')

    rechtstexte = f"""
<section class="legal" id="impressum">
{artikel_von(lies('impressum.html'))}
</section>
<section class="legal" id="datenschutz">
{artikel_von(lies('datenschutz.html'))}
</section>
"""

    bloecke = "\n".join(f"<script>\n{js_ascii(inhalt)}\n</script>"
                        for _name, inhalt in js if inhalt)

    doc = f"""<title>Festival Finder &#8212; Lineup-Abgleich weltweit</title>
<style>
/* Die Seite ist bewusst durchgehend dunkel gestaltet (Konzertplakat-Look)
   und uebernimmt deshalb keine helle Darstellung des Betrachters. */
:root {{ color-scheme: dark; }}
html, body {{ background: #0b0b0d; }}
{html_ascii(css)}
</style>
{html_ascii(koerper)}
{html_ascii(rechtstexte)}
{bloecke}
"""
    schreib_text(ZIEL, doc)
    return {"mb": ZIEL.stat().st_size / 1e6,
            "skripte": [n for n, _ in js], "stile": stile()}
