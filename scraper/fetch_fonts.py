"""Laedt die Display-Schrift und legt sie als data-URI in site/fonts.css ab.

Die veroeffentlichte Seite darf keine externen Dateien nachladen, und
Systemschriften wie Impact fehlen auf Android. Anton (SIL Open Font License)
sorgt geraeteuebergreifend fuer dasselbe Plakat-Schriftbild.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import requests

SITE = Path(__file__).resolve().parent.parent / "site"
OUT = SITE / "fonts.css"

# Ein moderner Browser-UA liefert woff2 statt des viel groesseren ttf
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

FAMILIES = [("Anton", "https://fonts.googleapis.com/css2?family=Anton&display=swap")]


def main() -> None:
    blocks = []
    for name, css_url in FAMILIES:
        css = requests.get(css_url, headers=UA, timeout=60).text
        # nur die lateinische Teilmenge - spart rund zwei Drittel der Groesse
        chunks = re.findall(r"/\*\s*([\w\-\[\]]+)\s*\*/\s*(@font-face\s*\{.*?\})", css, re.S)
        block = next((b for sub, b in chunks if sub == "latin"), None)
        if block is None:
            block = re.search(r"@font-face\s*\{.*?\}", css, re.S).group(0)

        url = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
        data = requests.get(url, headers=UA, timeout=60).content
        b64 = base64.b64encode(data).decode()
        block = re.sub(r"url\(https://[^)]+\.woff2\)",
                       f"url(data:font/woff2;base64,{b64})", block)
        blocks.append(f"/* {name} - SIL Open Font License 1.1 */\n{block}")
        print(f"  {name}: {len(data) / 1024:.0f} KB woff2")

    OUT.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    print(f"{OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
