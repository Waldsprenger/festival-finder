"""Die Display-Schrift als data-URI in site/fonts.css.

Die veröffentlichte Seite darf keine externen Dateien nachladen, und
Systemschriften wie Impact fehlen auf Android. Anton (SIL Open Font License)
sorgt geräteübergreifend für dasselbe Plakat-Schriftbild.
"""

import base64
import re

import requests

from ..netz import HEADERS
from ..pfade import SITE, schreib_text

ZIEL = SITE / "fonts.css"

FAMILIEN = [("Anton", "https://fonts.googleapis.com/css2?family=Anton&display=swap")]


def bauen() -> dict:
    bloecke = []
    groessen = {}
    for name, css_url in FAMILIEN:
        # Ein moderner Browser-UA liefert woff2 statt des viel größeren ttf
        css = requests.get(css_url, headers=HEADERS, timeout=60).text
        # nur die lateinische Teilmenge — spart rund zwei Drittel der Größe
        teile = re.findall(r"/\*\s*([\w\-\[\]]+)\s*\*/\s*(@font-face\s*\{.*?\})",
                           css, re.S)
        block = next((b for sub, b in teile if sub == "latin"), None)
        if block is None:
            block = re.search(r"@font-face\s*\{.*?\}", css, re.S).group(0)

        url = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
        daten = requests.get(url, headers=HEADERS, timeout=60).content
        b64 = base64.b64encode(daten).decode()
        block = re.sub(r"url\(https://[^)]+\.woff2\)",
                       f"url(data:font/woff2;base64,{b64})", block)
        bloecke.append(f"/* {name} - SIL Open Font License 1.1 */\n{block}")
        groessen[name] = len(daten) / 1024

    schreib_text(ZIEL, "\n\n".join(bloecke) + "\n")
    return {"schriften": groessen, "kb": ZIEL.stat().st_size / 1024}
