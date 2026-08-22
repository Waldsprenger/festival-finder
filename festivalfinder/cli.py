"""Ein Einstiegspunkt für alles.

    python -m festivalfinder alles            der komplette Lauf
    python -m festivalfinder alles --frisch   jede Seite neu holen
    python -m festivalfinder sammeln          nur Daten sammeln
    python -m festivalfinder bauen            nur die Seite bauen
    python -m festivalfinder verzeichnis      Ortsverzeichnis erneuern
    python -m festivalfinder karte            Kartengrenzen erneuern
    python -m festivalfinder schrift          Schrift einbetten

Vorher waren das neun Skripte, die einander unter blankem Namen importierten
und über `sys.path` zueinander fanden. Jetzt ist es ein Paket mit einer Tür.
"""

import argparse
import sys
import time
from datetime import date, datetime
from urllib.parse import urlparse

from . import ausgabe, pruefung, sammeln
from .bund import lauf
from .netz import Abrufer
from .pfade import DATA, schreib_json, schreib_text
from .werkzeug import gazetteer, geokodieren, preisverlauf, schriften, weltkarte


# --------------------------------------------------------------------------
# Sammeln
# --------------------------------------------------------------------------

def _haeuser(adressen: list[str]) -> dict[str, int]:
    """Nicht ladbare Adressen je Rechnername — welche Quelle hakt, nicht welche Seite."""
    zaehler: dict[str, int] = {}
    for eintrag in adressen:
        haus = urlparse(eintrag.split(" ")[0]).netloc
        zaehler[haus] = zaehler.get(haus, 0) + 1
    return dict(sorted(zaehler.items(), key=lambda p: -p[1]))


def _gruende(adressen: list[str]) -> dict[str, int]:
    """Woran es scheiterte, je Rechnername und Fehlerart.

    Ein abgewiesener Zugriff (HTTPError) ist etwas anderes als eine Leitung,
    die nicht zustande kommt (ConnectionError, Timeout) — und nur das eine wäre
    eine Entscheidung des Betreibers.
    """
    zaehler: dict[str, int] = {}
    for eintrag in adressen:
        adresse, _, art = eintrag.partition(" ")
        schluessel = f"{urlparse(adresse).netloc} {art.strip('()') or 'unbekannt'}"
        zaehler[schluessel] = zaehler.get(schluessel, 0) + 1
    return dict(sorted(zaehler.items(), key=lambda p: -p[1]))


def befehl_sammeln(args) -> int:
    netz = Abrufer(max_age_h=args.max_age, frisch=args.frisch)
    t0 = time.time()
    if args.frisch:
        print("Frischer Lauf: der Seitencache wird übergangen.", flush=True)

    funde, ergebnis = sammeln.funde_sammeln(netz, args.since, limit=args.limit)
    namen, bandstatistik, doppelt, kuerzel = lauf.vorbereiten(funde)
    if doppelt:
        print("  Kürzel als eigener Act im Programm, Alias bleibt aus: "
              + ", ".join(x.upper() for x in doppelt))

    festivals = lauf.zusammenfuehren(funde, namen, kuerzel)

    # Vergangene Ausgaben aussortieren: Über die Länderseiten tauchen Seiten
    # auf, deren letzte Ausgabe Jahre zurückliegt („Weekend Festival Baltic
    # 2018"). Einträge ohne Termin bleiben — das sind angekündigte Festivals
    # ohne bestätigtes Datum —, es sei denn, ihr Name nennt ein vergangenes
    # Jahr.
    vorher = len(festivals)
    festivals = [f for f in festivals
                 if (not f.von or (f.bis or f.von).year >= args.since)
                 and not pruefung.gewesene_ausgabe(f, args.since)]
    if vorher != len(festivals):
        print(f"  {vorher - len(festivals)} Einträge älter als {args.since} verworfen")

    # Preise vergleichen, bevor geprüft und geschrieben wird
    preise = preisverlauf.verfolgen(festivals)

    for widerspruch in pruefung.stimmigkeit(festivals):
        print(f"  ! Widerspruch in den Daten: {widerspruch}", file=sys.stderr)

    ausgabe.dateien.schreiben(festivals)
    schreib_json(DATA / "band_normalisierung.json", bandstatistik)

    # Nur bei einem vollständigen Lauf vergleichen — ein Testlauf mit --limit
    # liefert naturgemäß weniger.
    warnungen: list[str] = []
    if not args.limit:
        warnungen = pruefung.ausbeute(ergebnis.funde, len(festivals),
                                      ergebnis.mitgebracht)
        for warnung in warnungen:
            print(f"  ! Einbruch gegenüber dem letzten Lauf: {warnung}",
                  file=sys.stderr)

    # Der Zustand des Laufs geht mit auf die Webseite. Auf dem eigenen Rechner
    # steht er im Protokoll — beim Lauf auf fremden Servern kommt niemand an
    # dessen Protokoll heran, und eine Quelle, die dort nichts liefert, fiele
    # sonst nur als kleinere Zahl auf.
    schreib_json(DATA / "lauf.json", {
        "stand": datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M%z"),
        "quellen": ergebnis.funde,
        "mitgebrachter_stand": ergebnis.mitgebracht,
        "festivals": len(festivals),
        "warnungen": warnungen,
        "nicht_ladbar": len(netz.fehlgeschlagen),
        "nicht_ladbar_je_haus": _haeuser(netz.fehlgeschlagen),
        "nicht_ladbar_grund": _gruende(netz.fehlgeschlagen),
        "meldungen": netz.meldungen[:40],
    })

    acts = len({b for f in festivals for b in f.lineup})
    print(f"Preise beobachtet        : {preise['beobachtet']}, "
          f"seit dem ersten Mal geändert: {preise['geändert']}")
    print(f"\nFestivals gesamt        : {len(festivals)}")
    print(f"  aus mehreren Quellen  : {sum(1 for f in festivals if len(f.quellen) > 1)}")
    print(f"  mit Lineup            : {sum(1 for f in festivals if f.lineup)}")
    print(f"  abgesagt              : {sum(1 for f in festivals if f.abgesagt)}")
    print(f"Acts (normalisiert)     : {acts}")
    print(f"  Rohschreibweisen      : {bandstatistik['roh_schreibweisen']}, davon "
          f"{bandstatistik['vereinheitlicht']} auf eine Schreibweise vereinheitlicht")
    if ergebnis.parsefehler:
        print("Nicht lesbare Seiten: "
              + ", ".join(f"{q} {n}" for q, n in sorted(ergebnis.parsefehler.items())))
    if netz.fehlgeschlagen:
        print(f"Nicht ladbar: {len(netz.fehlgeschlagen)} Seiten (siehe data/failed.txt)")
        schreib_text(DATA / "failed.txt", "\n".join(netz.fehlgeschlagen))
    if args.frisch and not args.limit:
        # Alles Verlinkte wurde soeben geschrieben; was seit einer Woche
        # niemand angefasst hat, ist verwaist.
        weg, mb = netz.aufraeumen(t0 - 7 * 24 * 3600)
        print(f"Cache aufgeräumt: {weg} verwaiste Seiten gelöscht ({mb:.1f} MB)")
    print(f"Dauer: {time.time() - t0:.0f}s -> {DATA}")
    return 0


# --------------------------------------------------------------------------
# Bauen
# --------------------------------------------------------------------------

def _festivals_lesen():
    """Den zuletzt gesammelten Bestand einlesen — für die Bauschritte allein."""
    from .kern import zeit
    from .kern.festival import Festival
    from .pfade import lies_json

    raus = []
    for d in lies_json(DATA / "festivals.json", []) or []:
        f = Festival(
            name=d["name"], jahr=d["year"],
            von=zeit.aus_deutsch(d["date_from"]), bis=zeit.aus_deutsch(d["date_to"]),
            stadt=d["city"], land=d["country"], ort=d["venue"], plz=d["plz"],
            lat=d["lat"], lon=d["lon"], preis=d["price"], webseite=d["website"],
            genre=d["genre"], besucher=d["visitors"], hinweis=d["note"],
            abgesagt=d["cancelled"], quellen=dict(d["sources"]),
            preis_start=d["price_start"], preis_start_seit=d["price_start_seit"])
        f.bands = {b: b for b in d["lineup"]}
        raus.append(f)
    return raus


def befehl_bauen(args) -> int:
    festivals = _festivals_lesen()
    if not festivals:
        print("data/festivals.json ist leer - erst sammeln.", file=sys.stderr)
        return 1

    z = ausgabe.uebersicht.bauen(festivals)
    print(f"uebersicht.html  ({z['mb']:.1f} MB, {z['festivals']} Festivals)")

    z = ausgabe.daten_js.bauen(festivals)
    print(f"orte.js   ({z['orte_js_mb']:.1f} MB zum Nachladen: "
          f"{z['welt_orte']} Orte, {z['welt_plz']} Postleitzahlen)")
    print(f"data.js   ({z['data_js_mb']:.1f} MB)")
    print(f"  Koordinaten aus Postleitzahl: {z['aus_plz']}, aus dem Geo-Cache: "
          f"{z['aus_cache']}, aus dem Ortsverzeichnis: {z['aus_ortsverzeichnis']}, "
          f"aus der Quellseite: {z['aus_quelle']}")
    print(f"  Festivals {z['festivals']} | mit Koordinaten {z['mit_koordinaten']} | "
          f"mit Preis in EUR {z['mit_preis']} | Acts {z['acts']} | "
          f"Orte {z['orte']} | PLZ {z['plz']}")
    print(f"  Genre zugeordnet {z['mit_genre']} | Bandkürzel {z['bandkuerzel']}")
    print(f"  Grenzen: Entfernung bis {z['max_km']} km (ab {ausgabe.daten_js.REF_PLZ}), "
          f"Preis bis {z['max_preis']} EUR, Kalender ab {z['ab_datum'] or 'unbegrenzt'}")

    z = ausgabe.pwa.bauen()
    print(f"manifest.webmanifest, sw.js ({len(z['vorrat'])} Dateien im Vorrat)")

    z = ausgabe.artefakt.bauen()
    print(f"artifact.html  ({z['mb']:.2f} MB, {len(z['skripte'])} Skripte)")
    return 0


# --------------------------------------------------------------------------
# Werkzeuge
# --------------------------------------------------------------------------

def befehl_verzeichnis(args) -> int:
    z = gazetteer.bauen(Abrufer())
    print(f"laender.json ({z['laender']}) | gazetteer.json ({z['orte_klein']} Orte) | "
          f"laender_rahmen.json ({z['rahmen']}) | plz.json ({z['plz_dach']})")
    print(f"verortung.json: {z['plz_welt']} Postleitzahlen, {z['orte_fein']} Orte, "
          f"{z['plz_nachladen']} zum Nachladen")
    return 0


def befehl_karte(args) -> int:
    for name, z in weltkarte.bauen(Abrufer()).items():
        print(f"{name:<16} {z['was']:<18} {z['mb']:>5.2f} MB, "
              f"{z['ringe']:>5} Ringe, {z['punkte']:>7} Punkte")
    return 0


def befehl_schrift(args) -> int:
    z = schriften.bauen()
    for name, kb in z["schriften"].items():
        print(f"  {name}: {kb:.0f} KB woff2")
    print(f"fonts.css  ({z['kb']:.0f} KB)")
    return 0


def befehl_orte(args) -> int:
    z = geokodieren.auffuellen(_festivals_lesen())
    print(f"fertig: {z['mit_koordinaten']}/{z['im_cache']} Orte mit Koordinaten")
    return 0


# --------------------------------------------------------------------------

#: Der komplette Lauf, in der Reihenfolge, in der die Schritte aufeinander bauen
ALLES = [
    ("Festivaldaten", befehl_sammeln),
    # Das Ortsverzeichnis steht vor der Geokodierung: Was dort schon drinsteht,
    # muss nicht bei Nominatim erfragt werden.
    ("Ortsverzeichnis", befehl_verzeichnis),
    ("Ortskoordinaten", befehl_orte),
    # Kartengrenzen und Schrift ändern sich kaum und laufen aus dem Cache. Sie
    # stehen trotzdem hier, damit ein frischer Klon vollständig baut.
    ("Kartengrenzen", befehl_karte),
    ("Schrift", befehl_schrift),
    ("Webseite", befehl_bauen),
]


def befehl_alles(args) -> int:
    fehler = 0
    for name, funktion in ALLES:
        print(f"\n=== {name} " + "=" * (60 - len(name)), flush=True)
        t0 = time.time()
        try:
            code = funktion(args)
        except Exception as exc:
            # Ein Schritt, der scheitert, hält die übrigen nicht auf: Der
            # Bestand von gestern ist besser als kein Bestand.
            print(f"[{name}] FEHLER: {exc.__class__.__name__}: {exc}", file=sys.stderr)
            fehler += 1
            continue
        fehler += bool(code)
        print(f"[{name}] {'ok' if not code else 'FEHLER'} nach {time.time()-t0:.0f}s")
    return 1 if fehler else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="festivalfinder",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0,
                    help="nur N Detailseiten je Quelle")
    ap.add_argument("--max-age", type=float, default=24.0,
                    help="Cache-Alter in Stunden, ab dem neu geladen wird (0 = nie)")
    ap.add_argument("--frisch", action="store_true",
                    help="jede Seite neu abrufen und verwaisten Cache löschen")
    ap.add_argument("--since", type=int, default=date.today().year,
                    help="frühester Jahrgang; 2006 holt das komplette Archiv")
    ap.add_argument("befehl", nargs="?", default="alles",
                    choices=["alles", "sammeln", "bauen", "verzeichnis", "karte",
                             "schrift", "orte"])
    args = ap.parse_args(argv)

    befehle = {"alles": befehl_alles, "sammeln": befehl_sammeln,
               "bauen": befehl_bauen, "verzeichnis": befehl_verzeichnis,
               "karte": befehl_karte, "schrift": befehl_schrift,
               "orte": befehl_orte}
    return befehle[args.befehl](args)
