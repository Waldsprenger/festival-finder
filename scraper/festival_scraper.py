"""Festivaldaten einsammeln, zusammenführen und ablegen.

    python scraper/festival_scraper.py              # alles, aus dem Cache wo möglich
    python scraper/festival_scraper.py --frisch     # jede Seite neu abrufen
    python scraper/festival_scraper.py --limit 20   # Testlauf mit wenigen Seiten
    python scraper/festival_scraper.py --since 2006 # das komplette Archiv

Was die einzelnen Quellen können, steht in `quellen.py`; wie aus ihren Funden
ein Festival wird, in `zusammenfuehren.py`.

Ergebnis: data/festivals.json plus drei CSV-Ausgaben.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import sys
import time
from datetime import date, datetime
from urllib.parse import urlparse

import netz
from gemeinsam import DATA, EUROPA_CODES, liegt_in_europa, lies_json, schreib_json
from quellen import FT_STAMM, QUELLEN, Quelle
from preisverlauf import verfolgen
import schnappschuss
from text import city_key, festival_key, tag_zahl
from zusammenfuehren import (alias_kollisionen, band_registry, zeitraum_ueberlappt,
                             zusammenfuehren)


#: Seiten, an denen ein Leser gescheitert ist - je Quelle gezaehlt
PARSEFEHLER: dict[str, int] = {}


def einlesen(quelle: Quelle, urls: list[str]) -> list[dict]:
    """Detailseiten einer Quelle parallel holen und auslesen."""
    funde: list[dict] = []
    fertig = 0
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        auftraege = {pool.submit(netz.fetch, u): u for u in urls}
        for auftrag in cf.as_completed(auftraege):
            url = auftraege[auftrag]
            fertig += 1
            if fertig % 100 == 0:
                print(f"  {quelle.name}: {fertig}/{len(urls)}", flush=True)
            html = auftrag.result()
            if not html:
                continue
            try:
                rec = (quelle.lesen(url, html, FT_STAMM.get(url))
                       if quelle.mit_stammdaten else quelle.lesen(url, html))
            except Exception as exc:
                # Ein Fehler kostet dieses Festival, nicht den Lauf. Gezaehlt
                # wird trotzdem: Stille Ausfaelle sind die gefaehrlichsten.
                PARSEFEHLER[quelle.name] = PARSEFEHLER.get(quelle.name, 0) + 1
                netz.melde(f"Parsefehler {url}: {exc}")
                continue
            if rec and rec["name"]:
                funde.append(rec)
    return funde


def haeuser(adressen: list[str]) -> dict[str, int]:
    """Nicht ladbare Adressen je Rechnername — welche Quelle hakt, nicht welche Seite."""
    zaehler: dict[str, int] = {}
    for eintrag in adressen:
        haus = urlparse(eintrag.split(" ")[0]).netloc
        zaehler[haus] = zaehler.get(haus, 0) + 1
    return dict(sorted(zaehler.items(), key=lambda p: -p[1]))


def gruende(adressen: list[str]) -> dict[str, int]:
    """Woran es scheiterte, je Rechnername und Fehlerart.

    Ein abgewiesener Zugriff (HTTPError) ist etwas anderes als eine Leitung,
    die nicht zustande kommt (ConnectionError, Timeout) — und nur das eine
    wäre eine Entscheidung des Betreibers.
    """
    zaehler: dict[str, int] = {}
    for eintrag in adressen:
        adresse, _, art = eintrag.partition(" ")
        schluessel = f"{urlparse(adresse).netloc} {art.strip('()') or 'unbekannt'}"
        zaehler[schluessel] = zaehler.get(schluessel, 0) + 1
    return dict(sorted(zaehler.items(), key=lambda p: -p[1]))


def pruefe_ausbeute(funde: dict[str, int], festivals: int,
                    mitgebracht: dict[str, str] | None = None) -> list[str]:
    """Vergleicht die Ausbeute mit dem letzten Lauf und meldet Einbrüche.

    Ändert eine Quelle ihren Seitenaufbau, liefert ihr Leser plötzlich weniger
    oder nichts mehr — in der Gesamtliste fällt das kaum auf, weil die anderen
    sieben weiter füllen. Ein Fünftel weniger gilt als Einbruch; kleinere
    Schwankungen sind normal, Festivals kommen und gehen.
    """
    stand = DATA / "quellen_stand.json"
    vorher = lies_json(stand, {})
    warnungen = []
    mitgebracht = mitgebracht or {}
    for name, datum in mitgebracht.items():
        # Die Quelle bedient diesen Lauf nicht, ihr Stand liegt aber bei.
        # Zu melden ist deshalb nicht ihr Schweigen, sondern sein Alter.
        tage = schnappschuss.alter_in_tagen(datum)
        if tage is None:
            warnungen.append(f"{name}: mitgebrachter Stand ohne lesbares Datum")
        elif tage > schnappschuss.ALTERSGRENZE_TAGE:
            warnungen.append(f"{name}: mitgebrachter Stand vom {datum} "
                             f"ist {tage} Tage alt")
    for name, jetzt in funde.items():
        if name in mitgebracht:
            continue
        frueher = vorher.get("quellen", {}).get(name)
        if not jetzt:
            # Ohne diesen Fall bleibt die schlimmste Störung stumm: Eine Null
            # ist als Maßstab unbrauchbar (`0 < 0 * 0.8` ist falsch), also
            # meldete der Vergleich nichts - und beim Lauf auf fremden Servern
            # lieferte festivalticker über Monate nichts, ohne dass es auffiel.
            warnungen.append(f"{name}: kein einziger Fund")
        elif frueher and jetzt < frueher * 0.8:
            warnungen.append(f"{name}: {jetzt} statt {frueher} Funde")
    frueher_gesamt = vorher.get("festivals")
    if frueher_gesamt and festivals < frueher_gesamt * 0.8:
        warnungen.append(f"Festivals gesamt: {festivals} statt {frueher_gesamt}")
    # Bei einem Einbruch bleibt der alte Maßstab stehen: Sonst gilt der
    # schlechte Wert ab morgen als normal und die Warnung verstummt, obwohl
    # nichts repariert ist.
    gemerkt = {name: (vorher.get("quellen", {}).get(name, jetzt)
                      if any(name in w for w in warnungen) else jetzt)
               for name, jetzt in funde.items()}
    schreib_json(stand, {"quellen": gemerkt,
                         "festivals": max(festivals, frueher_gesamt or 0)
                         if warnungen else festivals})
    return warnungen


def pruefe_stimmigkeit(festivals: list[dict]) -> list[str]:
    """Widersprüche im Ergebnis finden, bevor sie auf die Seite kommen.

    Nicht "wie beim letzten Mal", sondern "in sich stimmig": Passt das Jahr zum
    Termin, liegt das Ende nicht vor dem Anfang, steckt jede Koordinate in
    Europa, zählt das Lineup richtig? Jeder dieser Punkte war schon einmal
    falsch.
    """
    zaehler: dict[str, int] = {}

    def merke(bedingung: bool, was: str) -> None:
        if not bedingung:
            zaehler[was] = zaehler.get(was, 0) + 1

    for f in festivals:
        merke(bool(f["name"].strip()), "ohne Namen")
        merke(bool(f["sources"]), "ohne Quelle")
        merke(not f["date_from"] or f["year"] == f["date_from"][-4:],
              "Jahr passt nicht zum Termin")
        merke(not (f["date_from"] and f["date_to"])
              or tag_zahl(f["date_to"]) >= tag_zahl(f["date_from"]), "Ende vor Anfang")
        merke(f["lat"] is None or liegt_in_europa(f["lat"], f["lon"]),
              "Koordinate außerhalb Europas")
        merke(f["lineup_count"] == len(f["lineup"]), "Lineup falsch gezählt")
        merke(not f["visitors"] or f["visitors"].isdigit(), "Besucherzahl keine Zahl")
        merke(not f["country"] or f["country"] in EUROPA_CODES, "Land außerhalb Europas")

    # Dubletten: gleicher Name, gleicher Ort, sich überschneidender Termin.
    # Zwei Ausgaben desselben Festivals im selben Jahr gibt es wirklich
    # (Heartbeatz im Juni und im September) - die dürfen bleiben.
    gruppen: dict[tuple[str, str, str], list[dict]] = {}
    for f in festivals:
        schluessel = (festival_key(f["name"]).replace(" ", ""), f["year"],
                      city_key(f["city"]))
        gruppen.setdefault(schluessel, []).append(f)
    for gleiche in gruppen.values():
        for i, a in enumerate(gleiche):
            for b in gleiche[i + 1:]:
                merke(not zeitraum_ueberlappt(a, b), "Dublette übrig geblieben")

    return [f"{n}x {was}" for was, n in sorted(zaehler.items())]


def schreibe_ausgaben(festivals: list[dict]) -> None:
    """JSON für die Webseite, CSV für die Tabellenkalkulation."""
    schreib_json(DATA / "festivals.json", festivals)

    def tabelle(name: str, kopf: list[str], zeilen):
        with (DATA / name).open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(kopf)
            w.writerows(zeilen)

    tabelle("festivals.csv",
            ["Name", "Jahr", "Von", "Bis", "Ort", "Land", "Venue", "Preis",
             "Webseite", "Genre", "Besucher", "Abgesagt", "Hinweis",
             "Preis zum Start", "Anzahl Acts", "Lineup", "Quellen"],
            ([f["name"], f["year"], f["date_from"], f["date_to"], f["city"],
              f["country"], f["venue"], f["price"], f["website"], f["genre"],
              f["visitors"], "ja" if f["cancelled"] else "", f["note"],
              f["price_start"], f["lineup_count"], ", ".join(f["lineup"]),
              " | ".join(f["sources"].values())] for f in festivals))

    tabelle("lineups.csv",
            ["Band", "Festival", "Von", "Bis", "Ort", "Land"],
            ([b, f["name"], f["date_from"], f["date_to"], f["city"], f["country"]]
             for f in festivals for b in f["lineup"]))

    # Acts über mehrere Festivals hinweg - zeigt Mehrfachbuchungen
    bands: dict[str, list[str]] = {}
    for f in festivals:
        for b in f["lineup"]:
            bands.setdefault(b, []).append(f["name"])
    tabelle("bands.csv",
            ["Band", "Anzahl Festivals", "Festivals"],
            ([b, len(fs), ", ".join(sorted(set(fs)))]
             for b, fs in sorted(bands.items(),
                                 key=lambda kv: (-len(kv[1]), kv[0].casefold()))))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0, help="nur N Detailseiten je Quelle")
    ap.add_argument("--max-age", type=float, default=24.0,
                    help="Cache-Alter in Stunden, ab dem neu geladen wird (0 = nie)")
    ap.add_argument("--frisch", action="store_true",
                    help="jede Seite neu abrufen und verwaisten Cache löschen")
    ap.add_argument("--since", type=int, default=date.today().year,
                    help="frühester Jahrgang; 2006 holt das komplette Archiv")
    args = ap.parse_args()

    netz.einstellen(args.max_age, args.frisch)
    t0 = time.time()
    if args.frisch:
        print("Frischer Lauf: der Seitencache wird übergangen.", flush=True)

    print(f"Sammle Detail-Links ab Jahrgang {args.since} ...", flush=True)
    adressen = {q.name: q.adressen(args.since) for q in QUELLEN}
    print("  " + " | ".join(f"{name} {len(u)}" for name, u in adressen.items()),
          flush=True)

    records: list[dict] = []
    funde: dict[str, int] = {}
    mitgebracht: dict[str, str] = {}
    for quelle in QUELLEN:
        urls = adressen[quelle.name]
        gefunden = einlesen(quelle, urls[:args.limit] if args.limit else urls)
        funde[quelle.name] = len(gefunden)
        if gefunden:
            # Was dieser Lauf erreicht hat, bekommt der nächste mit, der es
            # nicht erreicht. Ein Teillauf (--limit) taugt dafür nicht.
            if not args.limit and schnappschuss.schreiben(quelle.name, gefunden):
                print(f"  Stand von {quelle.name} abgelegt "
                      f"({schnappschuss.datei(quelle.name).stat().st_size / 1e6:.2f} MB)")
        else:
            gefunden, stand = schnappschuss.lesen(quelle.name)
            if gefunden:
                mitgebracht[quelle.name] = stand
                print(f"  {quelle.name} antwortet nicht - Stand vom {stand} "
                      f"mit {len(gefunden)} Datensätzen")
        records += gefunden
    print(f"Datensätze: {len(records)}", flush=True)

    doppelt = alias_kollisionen(records)
    if doppelt:
        print("  Kürzel als eigener Act im Programm, Alias bleibt aus: "
              + ", ".join(x.upper() for x in doppelt))
    registry, bandstatistik = band_registry(records)
    festivals = zusammenfuehren(records, registry)

    # Vergangene Ausgaben aussortieren: Über die Länderseiten tauchen Seiten
    # auf, deren letzte Ausgabe Jahre zurückliegt ("Weekend Festival Baltic
    # 2018"). Einträge ohne Termin bleiben - das sind angekündigte Festivals
    # ohne bestätigtes Datum, keine vergangenen.
    vorher = len(festivals)
    festivals = [f for f in festivals
                 if not f["date_from"] or int(f["date_from"][-4:]) >= args.since]
    if vorher != len(festivals):
        print(f"  {vorher - len(festivals)} Einträge älter als {args.since} verworfen")

    # Preise mit dem letzten Lauf vergleichen, bevor geprüft und geschrieben wird
    preise = verfolgen(festivals)

    for widerspruch in pruefe_stimmigkeit(festivals):
        print(f"  ! Widerspruch in den Daten: {widerspruch}", file=sys.stderr)

    schreibe_ausgaben(festivals)
    schreib_json(DATA / "band_normalisierung.json", bandstatistik)

    # Nur bei einem vollständigen Lauf vergleichen - ein Testlauf mit --limit
    # liefert naturgemäß weniger.
    warnungen: list[str] = []
    if not args.limit:
        warnungen = pruefe_ausbeute(funde, len(festivals), mitgebracht)
        for warnung in warnungen:
            print(f"  ! Einbruch gegenüber dem letzten Lauf: {warnung}", file=sys.stderr)

    # Der Zustand des Laufs geht mit auf die Webseite. Auf dem eigenen Rechner
    # steht er im Protokoll - beim Lauf auf fremden Servern kommt niemand an
    # dessen Protokoll heran, und eine Quelle, die dort nichts liefert, fiele
    # sonst nur als kleinere Zahl auf.
    schreib_json(DATA / "lauf.json", {
        "stand": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M%z"),
        "quellen": funde,
        "mitgebrachter_stand": mitgebracht,
        "festivals": len(festivals),
        "warnungen": warnungen,
        "nicht_ladbar": len(netz.FEHLGESCHLAGEN),
        "nicht_ladbar_je_haus": haeuser(netz.FEHLGESCHLAGEN),
        "nicht_ladbar_grund": gruende(netz.FEHLGESCHLAGEN),
        "meldungen": netz.MELDUNGEN[:40],
    })

    acts = len({b for f in festivals for b in f["lineup"]})
    print(f"Preise beobachtet        : {preise['beobachtet']}, "
          f"seit dem ersten Mal geändert: {preise['geändert']}")
    print(f"\nFestivals gesamt        : {len(festivals)}")
    print(f"  aus mehreren Quellen  : {sum(1 for f in festivals if len(f['sources']) > 1)}")
    print(f"  mit Lineup            : {sum(1 for f in festivals if f['lineup'])}")
    print(f"  abgesagt              : {sum(1 for f in festivals if f['cancelled'])}")
    print(f"Acts (normalisiert)     : {acts}")
    print(f"  Rohschreibweisen      : {bandstatistik['roh_schreibweisen']}, davon "
          f"{bandstatistik['vereinheitlicht']} auf eine Schreibweise vereinheitlicht")
    if PARSEFEHLER:
        print("Nicht lesbare Seiten: "
              + ", ".join(f"{q} {n}" for q, n in sorted(PARSEFEHLER.items())))
    if netz.FEHLGESCHLAGEN:
        print(f"Nicht ladbar: {len(netz.FEHLGESCHLAGEN)} Seiten (siehe data/failed.txt)")
        (DATA / "failed.txt").write_text("\n".join(netz.FEHLGESCHLAGEN), encoding="utf-8")
    if args.frisch and not args.limit:
        # Alles Verlinkte wurde soeben geschrieben; was seit einer Woche
        # niemand angefasst hat, ist verwaist. Bei --limit wird nichts
        # gelöscht - dann war der Lauf ja absichtlich unvollständig.
        weg, mb = netz.cache_aufraeumen(t0 - 7 * 24 * 3600)
        print(f"Cache aufgeräumt: {weg} verwaiste Seiten gelöscht ({mb:.1f} MB)")
    print(f"Dauer: {time.time() - t0:.0f}s -> {DATA}")


if __name__ == "__main__":
    main()
