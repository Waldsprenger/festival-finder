"""Stichprobe gegen die offiziellen Festivalseiten.

    python scraper/pruefe_offiziell.py [Anzahl]        # Zufallsstichprobe
    python scraper/pruefe_offiziell.py --name Wacken   # gezielt ein Festival

Geprueft wird der Starttermin. Belastbar ist dabei nur das maschinenlesbare
Datenblatt der Seite (schema.org/Event); blosse Datumsangaben im Fliesstext
gehoeren genauso oft zu Nachrichten, Vorjahren oder Nebenveranstaltungen.

Wichtig ist der Jahresbezug: Die offizielle Seite zeigt die naechste Ausgabe,
unser Bestand fuehrt jede Ausgabe einzeln. Verglichen wird deshalb nur, was
zum selben Jahrgang gehoert - sonst meldet die Pruefung jede Seite als
Abweichung, die schon ein Jahr weiter ist.

Die Seiten werden einzeln mit einer Sekunde Abstand geholt, robots.txt wird
vorher gefragt. Geschrieben wird nichts; das Ergebnis geht auf die Konsole.
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemeinsam import DATA  # noqa: E402

UA = ("FestivalFinder/1.0 (Datenabgleich, privates Projekt; "
      "Kontakt: waldsprenger@gmail.com)")

BLATT = re.compile(r'"startDate"\s*:\s*"(\d{4}-\d{2}-\d{2})')
TEXT = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(20\d{2})")
SKRIPT = re.compile(r"<script.*?</script>|<style.*?</style>", re.S)


def robots_erlaubt(session: requests.Session, url: str) -> bool:
    teile = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = session.get(f"{teile.scheme}://{teile.netloc}/robots.txt", timeout=8)
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    except Exception:
        return True                      # keine robots.txt erreichbar: erlaubt
    return rp.can_fetch(UA, url)


def termine(html: str) -> tuple[set[str], set[str]]:
    """(aus dem Datenblatt, aus dem Fliesstext) als JJJJ-MM-TT."""
    blatt = set(BLATT.findall(html))
    text = {f"{j}-{int(m):02d}-{int(t):02d}"
            for t, m, j in TEXT.findall(SKRIPT.sub(" ", html))}
    return blatt, text


def unser_datum(f: dict) -> str:
    tag, monat, jahr = f["date_from"].split(".")
    return f"{jahr}-{monat}-{tag}"


def main() -> None:
    args = sys.argv[1:]
    festivals = json.loads((DATA / "festivals.json").read_text(encoding="utf-8"))
    kandidaten = [f for f in festivals
                  if f["website"].startswith("http") and f["date_from"]]

    if args and args[0] == "--name":
        suche = " ".join(args[1:]).casefold()
        auswahl = [f for f in kandidaten if suche in f["name"].casefold()]
    else:
        anzahl = int(args[0]) if args else 40
        random.shuffle(kandidaten)
        auswahl = kandidaten[:anzahl]

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "de,en"})

    deckt, weicht, nur_text, ohne, fehler, gesperrt = 0, 0, 0, 0, 0, 0
    auffaellig = []

    for i, f in enumerate(auswahl, 1):
        url = f["website"]
        print(f"  {i}/{len(auswahl)}", end="\r", flush=True)
        try:
            if not robots_erlaubt(session, url):
                gesperrt += 1
                continue
            r = session.get(url, timeout=15)
            time.sleep(1.0)
            if r.status_code >= 400:
                fehler += 1
                continue
            r.encoding = r.apparent_encoding or "utf-8"
        except Exception:
            fehler += 1
            continue

        unser = unser_datum(f)
        blatt, text = termine(r.text)
        # Nur derselbe Jahrgang ist vergleichbar
        blatt_jahr = {d for d in blatt if d[:4] == unser[:4]}
        text_jahr = {d for d in text if d[:4] == unser[:4]}

        if blatt_jahr:
            if unser in blatt_jahr:
                deckt += 1
            else:
                weicht += 1
                auffaellig.append((f["name"], unser, sorted(blatt_jahr)[:3], url))
        elif text_jahr:
            nur_text += 1
            if unser not in text_jahr:
                auffaellig.append((f["name"], unser,
                                   ["Fliesstext: " + ", ".join(sorted(text_jahr)[:3])], url))
        else:
            ohne += 1

    print(f"\nGeprueft: {len(auswahl)}")
    print(f"  Datenblatt bestaetigt den Termin: {deckt}")
    print(f"  Datenblatt weicht ab:             {weicht}")
    print(f"  nur Fliesstextdaten:              {nur_text}")
    print(f"  Seite nennt kein Datum des Jahrgangs: {ohne}")
    print(f"  nicht erreichbar: {fehler} | per robots.txt gesperrt: {gesperrt}")
    if auffaellig:
        print("\nZum Nachsehen:")
        for name, unser, gefunden, url in auffaellig:
            print(f"  {name[:36]:36} | unser {unser} | Seite {', '.join(gefunden)}")
            print(f"      {url}")


if __name__ == "__main__":
    main()
