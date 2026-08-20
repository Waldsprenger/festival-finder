"""Baut aus site/ eine einzelne, in sich geschlossene HTML-Datei.

Veroeffentlichte Artifacts duerfen keine externen Dateien nachladen und
bestehen aus genau einer Seite. Deshalb werden CSS, Daten und Skript inline
gesetzt und die beiden Rechtstexte als Abschnitte angehaengt.

Ergebnis: site/artifact.html
"""

from __future__ import annotations

import re

from gemeinsam import SITE

OUT = SITE / "artifact.html"


def read(name: str, pflicht: bool = True) -> str:
    """Liest eine Datei aus site/. Nicht zwingende fehlen sang- und klanglos."""
    pfad = SITE / name
    if not pflicht and not pfad.exists():
        return ""
    return pfad.read_text(encoding="utf-8")


def html_ascii(text: str) -> str:
    """Sonderzeichen als HTML-Entities."""
    return text.encode("ascii", "xmlcharrefreplace").decode("ascii")


def js_ascii(text: str) -> str:
    """Sonderzeichen als \\uXXXX - Entities wirken im <script> nicht.

    Die Einzeldatei hat keinen <head>, in den eine Zeichensatz-Angabe passen
    wuerde. Ohne diese Absicherung haengt die Darstellung von Umlauten davon ab,
    was der ausliefernde Server als Charset mitschickt.
    """
    out = []
    for ch in text:
        cp = ord(ch)
        if cp < 128:
            out.append(ch)
        elif cp > 0xFFFF:                       # Ersatzzeichenpaar
            v = cp - 0x10000
            out.append(f"\\u{0xD800 + (v >> 10):04x}\\u{0xDC00 + (v & 0x3FF):04x}")
        else:
            out.append(f"\\u{cp:04x}")
    return "".join(out)


def body_of(html: str) -> str:
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    return m.group(1) if m else html


def article_of(html: str) -> str:
    m = re.search(r'<article class="legal">(.*?)</article>', html, re.S)
    text = m.group(1) if m else ""
    # Rueckverweise auf index.html ergeben in der Einzelseite keinen Sinn
    return re.sub(r'<a class="back".*?</a>', "", text, flags=re.S).strip()


def main() -> None:
    fonts = read("fonts.css")
    css = read("style.css")
    i18n = read("i18n.js")
    # Ohne config.js laeuft die Seite ebenfalls - app.js prueft window.CONFIG
    config = read("config.js", pflicht=False)
    data = read("data.js")
    karte = read("karte.js")
    app = read("app.js")

    main_body = body_of(read("index.html"))
    main_body = re.sub(r"<script[^>]*></script>\s*", "", main_body)
    # Fussnavigation zeigt auf die Abschnitte derselben Seite
    main_body = main_body.replace('href="impressum.html"', 'href="#impressum"')
    main_body = main_body.replace('href="datenschutz.html"', 'href="#datenschutz"')

    legal = f"""
<section class="legal" id="impressum">
{article_of(read('impressum.html'))}
</section>
<section class="legal" id="datenschutz">
{article_of(read('datenschutz.html'))}
</section>
"""

    main_body = html_ascii(main_body)
    legal = html_ascii(legal)
    css = html_ascii(css)
    data = js_ascii(data)
    karte = js_ascii(karte)
    app = js_ascii(app)
    i18n = js_ascii(i18n)
    config = js_ascii(config)

    doc = f"""<title>Festival Finder &#8212; Lineup-Abgleich f&#252;r Europa</title>
<style>
/* Die Seite ist bewusst durchgehend dunkel gestaltet (Konzertplakat-Look)
   und uebernimmt deshalb keine helle Darstellung des Betrachters. */
:root {{ color-scheme: dark; }}
html, body {{ background: #0b0b0d; }}
{fonts}
{css}
</style>
{main_body}
{legal}
<script>
{config}
</script>
<script>
{i18n}
</script>
<script>
{data}
</script>
<script>
{karte}
</script>
<script>
{app}
</script>
"""

    OUT.write_text(doc, encoding="utf-8")
    print(f"{OUT}  ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
