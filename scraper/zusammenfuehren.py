"""Aus vielen Funden ein Festival machen.

Acht Quellen beschreiben dieselbe Veranstaltung verschieden: anderer Ort
("Kronach" gegen "Burg Lichtenberg"), anderer Anreisetag, andere Schreibweise
("Reloadfestival"). Sechs Stufen führen sie zusammen, jede mit einer eigenen
Sicherung gegen falsche Treffer — Tour-Formate wie das Irish Spring Festival
laufen unter einem Namen an 30 Orten und müssen getrennt bleiben.
"""

from __future__ import annotations

import difflib

from gemeinsam import ausser_europa, land_code
from quellen import RANG
from text import (ALIAS_KEY, ALIAS_NAME, band_key, canonical_band, city_key,
                  clean, festival_key, fold, genres_vereinen, tag_zahl)


# --------------------------------------------------------------------------
# Bandnamen
# --------------------------------------------------------------------------

def alias_kollisionen(records: list[dict]) -> list[str]:
    """Kürzel abschalten, die eine andere Band meinen.

    Steht ein Kürzel selbst im Programm, gibt es zwei Möglichkeiten. Bei "TBS"
    führen alle betroffenen Festivals zugleich The Butcher Sisters auf —
    dieselbe Band, zweimal geschrieben, das Kürzel gehört also aufgelöst. "LP"
    dagegen teilt sich mit Linkin Park kein einziges Lineup: Das ist die
    Sängerin LP, und ein Alias würde acht Einträge umbenennen.

    Entscheidend ist deshalb nicht das bloße Vorkommen, sondern ob Kürzel und
    ausgeschriebener Name je gemeinsam auf einem Plakat stehen. Geprüft wird je
    Festival, nicht je Quellseite: Die beiden Schreibweisen stehen oft auf den
    Seiten verschiedener Quellen und treffen sich erst hier. Für die Suche auf
    der Webseite bleiben alle Kürzel nutzbar — dort erscheinen dann beide.
    """
    programme: dict[tuple[str, str], set[str]] = {}
    for rec in records:
        schluessel = (festival_key(rec["name"]), rec["year"])
        programme.setdefault(schluessel, set()).update(fold(b) for b in rec["lineup"])

    kollidiert = []
    for kurz, voll in list(ALIAS_KEY.items()):
        voll_gefaltet = fold(voll)
        allein = zusammen = False
        for namen in programme.values():
            if kurz not in namen:
                continue
            if voll_gefaltet in namen:
                zusammen = True
                break
            allein = True
        if allein and not zusammen:
            ALIAS_KEY.pop(kurz)
            kollidiert.append(kurz)
    return sorted(kollidiert)


def band_registry(records: list[dict]) -> tuple[dict[str, str], dict]:
    """Je Bandschlüssel eine verbindliche Schreibweise, plus Statistik."""
    varianten: dict[str, list[str]] = {}
    for rec in records:
        for b in rec["lineup"]:
            varianten.setdefault(band_key(b), []).append(clean(b))
    # Ein hinterlegter Alias schlägt die Mehrheitsregel: sonst gewänne bei
    # gleicher Häufigkeit die Abkürzung statt des ausgeschriebenen Namens.
    registry = {k: ALIAS_NAME.get(k) or canonical_band(v)
                for k, v in varianten.items() if k}
    verschieden = {k: sorted(set(v)) for k, v in varianten.items() if k}
    stats = {
        "roh_schreibweisen": sum(len(v) for v in verschieden.values()),
        "gruppen": len(registry),
        "vereinheitlicht": sum(len(v) - 1 for v in verschieden.values() if len(v) > 1),
        "beispiele": [(registry[k], v) for k, v in verschieden.items() if len(v) > 1][:400],
    }
    return registry, stats


# --------------------------------------------------------------------------
# Vergleiche
# --------------------------------------------------------------------------

def zeitraum_ueberlappt(a: dict, b: dict) -> bool:
    """Überschneiden sich die beiden Termine?

    Die Quellen zählen den Anreise- oder Warmup-Tag verschieden: Das Neuborn
    Open Air steht bei festivalticker ab dem 27.08., bei den beiden anderen ab
    dem 28.08. Ein Überlapp erfasst solche Fälle, ohne zwei Feste zu
    verschmelzen, die Wochen auseinanderliegen.
    """
    a0, b0 = tag_zahl(a["date_from"]), tag_zahl(b["date_from"])
    if not a0 or not b0:
        return False
    a1, b1 = tag_zahl(a["date_to"]) or a0, tag_zahl(b["date_to"]) or b0
    return a0 <= b1 and b0 <= a1


def ort_deckt_sich(a: str, b: str) -> bool:
    """Gemeinde und Ortsteil zählen als derselbe Ort ("Oberndorf am Neckar")."""
    return bool(a and b and (a == b or a.startswith(b + " ") or b.startswith(a + " ")))


def name_deckt_sich(ka: str, kb: str) -> bool:
    """Strenger Namensvergleich für Termine, die nicht am selben Tag beginnen.

    Ein gemeinsames Wort genügt hier nicht: "METAStadt Open Air Wien" und
    "Afrika Tage Wien" teilen sich die Stadt im Namen und sind zwei
    Veranstaltungen. Verlangt wird, dass ein Name vollständig im anderen steckt
    ("Neuborn" in "NOAF Neuborn") oder beide ohne Leerzeichen gleich sind
    ("R.O.I. Rock On Isens" und "ROI Rock On Isens").
    """
    ta, tb = set(ka.split()), set(kb.split())
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    return ka.replace(" ", "") == kb.replace(" ", "")


def schreibweise_gleich(a: str, b: str) -> bool:
    """Meinen zwei Namen dasselbe, nur anders geschrieben?

    "Sonne Mond Sterne" und "SonneMondSterne", "Kunst!Rasen" und "Kunstrasen
    Bonn", "Sziget" und "Szigit" — Leerzeichen, Satzzeichen und Tippfehler
    trennen sonst Einträge, die zusammengehören. Verglichen wird der
    Namensschlüssel ohne Leerzeichen; ein Rumpf von sechs Zeichen schützt kurze
    Namen wie "Wutz" vor Zufallstreffern.
    """
    # Zweimal vergleichen: einmal den Schlüssel, einmal den vollen Namen. Beim
    # "Soerdfest" gegen "Sørdfest" bleibt vom Schlüssel nur "soerd" und "sord"
    # übrig - zu kurz für einen belastbaren Vergleich, während die vollen Namen
    # zu 97 % übereinstimmen.
    return _aehnlich(eng(a), eng(b)) or _aehnlich(fold(a).replace(" ", ""),
                                                  fold(b).replace(" ", ""))


def _aehnlich(x: str, y: str) -> bool:
    if len(x) < 6 or len(y) < 6:
        return False
    if x == y or x.startswith(y) or y.startswith(x):
        return True
    return difflib.SequenceMatcher(None, x, y).ratio() >= 0.82


def eng(name: str) -> str:
    """Namensschlüssel ohne Leerzeichen."""
    return festival_key(name).replace(" ", "")


# --------------------------------------------------------------------------
# Verschmelzen
# --------------------------------------------------------------------------

#: Felder, bei denen der gefüllte Wert den leeren ersetzt
FELDER = ("date_from", "date_to", "city", "country", "venue", "plz",
          "price", "website", "visitors", "note")


def verschmelzen(keep: dict, drop: dict, spanne: bool = False) -> None:
    """Zwei Einträge zu einem: fehlende Angaben, Genres, Quellen, Lineups.

    Mit spanne=True gelten der früheste Beginn und das späteste Ende — die
    Quellen zählen Anreise- und Aufbautage verschieden.
    """
    for feld in FELDER:
        if not keep[feld] and drop[feld]:
            keep[feld] = drop[feld]
    if spanne:
        von_drop, von_keep = tag_zahl(drop["date_from"]), tag_zahl(keep["date_from"])
        if von_drop and (not von_keep or von_drop < von_keep):
            keep["date_from"] = drop["date_from"]
        if tag_zahl(drop["date_to"]) > tag_zahl(keep["date_to"]):
            keep["date_to"] = drop["date_to"]
    keep["genre"] = genres_vereinen(keep["genre"], drop["genre"])
    if keep["lat"] is None and drop["lat"] is not None:
        keep["lat"], keep["lon"] = drop["lat"], drop["lon"]
    keep["cancelled"] = keep["cancelled"] or drop["cancelled"]
    keep["sources"].update(drop["sources"])
    keep["_bands"].update(drop["_bands"])


def _paarweise(merged: dict, gruppen: dict, passt, spanne: bool = False) -> None:
    """Jede Gruppe paarweise prüfen; was zusammengehört, wird verschmolzen.

    Gemeinsam für die Stufen 3 bis 5: Zwei Einträge derselben Quelle bleiben
    immer getrennt — dieselbe Quelle führt kein Festival zweimal, wohl aber
    zwei gleichnamige an verschiedenen Orten.
    """
    for gruppe in gruppen.values():
        if len(gruppe) < 2:
            continue
        for i in range(len(gruppe)):
            ka, a = gruppe[i]
            if ka not in merged:
                continue
            for j in range(i + 1, len(gruppe)):
                kb, b = gruppe[j]
                if kb not in merged or ka not in merged:
                    continue
                if set(a["sources"]) & set(b["sources"]):
                    continue
                if not passt(ka, a, kb, b):
                    continue
                keep, drop, drop_key = ((a, b, kb) if a["_rang"] <= b["_rang"]
                                        else (b, a, ka))
                verschmelzen(keep, drop, spanne)
                merged.pop(drop_key, None)
                if drop_key == ka:
                    break


# --------------------------------------------------------------------------
# Die sechs Stufen
# --------------------------------------------------------------------------

def stufe1_exakt(records: list[dict], registry: dict[str, str]) -> dict:
    """Gleicher Name, gleiches Jahr, gleiche Stadt.

    Die Stadt gehört bewusst zum Schlüssel: Tour-Formate laufen unter einem
    Namen an vielen Orten und sind eigenständige Termine.
    """
    merged: dict[tuple[str, str, str], dict] = {}
    for rec in records:
        if ausser_europa(rec["country"]):
            continue
        key = (festival_key(rec["name"]), rec["year"], city_key(rec["city"]))
        cur = merged.get(key)
        if cur is None:
            cur = {
                "name": rec["name"],
                "year": rec["year"],
                "date_from": rec["date_from"],
                "date_to": rec["date_to"],
                "city": rec["city"],
                "country": rec["country"],
                "venue": rec["venue"],
                "plz": rec["plz"],
                "lat": rec["lat"],
                "lon": rec["lon"],
                "location": "",
                "price": rec["price"],
                "website": rec["website"],
                "genre": rec["genre"],
                "visitors": rec["visitors"],
                "note": rec["note"],
                "cancelled": rec["cancelled"],
                "sources": {},
                "_rang": RANG.get(rec["source"], len(RANG)),
                "_bands": {},
            }
            merged[key] = cur

        for feld in FELDER:
            if not cur[feld] and rec[feld]:
                cur[feld] = rec[feld]
        cur["genre"] = genres_vereinen(cur["genre"], rec["genre"])
        if cur["lat"] is None and rec["lat"] is not None:
            cur["lat"], cur["lon"] = rec["lat"], rec["lon"]
        if len(rec["name"]) > len(cur["name"]) and rec["source"] == "festivalticker":
            cur["name"] = rec["name"]
        # Bei gleicher Schreibung gewinnt die getrennte: festivalticker führt
        # das Reload Festival als "Reloadfestival", und so stand es dann auch
        # auf der Seite.
        if (fold(rec["name"]).replace(" ", "") == fold(cur["name"]).replace(" ", "")
                and rec["name"].count(" ") > cur["name"].count(" ")):
            cur["name"] = rec["name"]
        cur["cancelled"] = cur["cancelled"] or rec["cancelled"]
        cur["sources"][rec["source"]] = rec["source_url"]
        for b in rec["lineup"]:
            k = band_key(b)
            if k:
                cur["_bands"][k] = registry.get(k, clean(b))
    return merged


def stufe2_quellenpaare(merged: dict) -> None:
    """Eindeutige Quellenpaare über abweichende Ortsschreibweisen hinweg.

    Gibt es zu Name + Jahr in jeder Quelle genau einen Kandidaten, gehören sie
    zusammen — sonst wären es echte Parallelveranstaltungen.
    """
    nach_name: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in merged.items():
        nach_name.setdefault((key[0], key[1]), []).append((key, rec))

    for gruppe in nach_name.values():
        if len(gruppe) < 2 or any(len(rec["sources"]) != 1 for _, rec in gruppe):
            continue
        quellen = [next(iter(rec["sources"])) for _, rec in gruppe]
        if len(set(quellen)) != len(quellen):
            continue
        gruppe = sorted(gruppe, key=lambda kr: kr[1]["_rang"])
        _, keep = gruppe[0]
        for drop_key, drop in gruppe[1:]:
            verschmelzen(keep, drop)
            merged.pop(drop_key, None)


def stufe3_gleicher_start(merged: dict) -> None:
    """Dieselbe Veranstaltung, unterschiedlich benannt.

    "Kosmos Festival" (festivalticker) und "Kosmos Festival Chemnitz"
    (festivalsunited) sind dasselbe. Verlangt werden gleicher Starttermin,
    gleiche Stadt und ein gemeinsamer Namensbestandteil. Der Starttermin ist
    der entscheidende Schutz: "Winter Wutzrock" im Februar und "Wutzrock" im
    August teilen Stadt und Namen, sind aber zwei Feste.
    """
    gruppen: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in merged.items():
        if rec["date_from"] and rec["city"]:
            gruppen.setdefault((rec["year"], rec["date_from"]), []).append((key, rec))

    def passt(ka, a, kb, b):
        if not (set(ka[0].split()) & set(kb[0].split())):
            return False
        # Bei identischem Namensschlüssel genügt der gleiche Tag; sonst muss
        # auch der Ort zusammenpassen (Gemeinde statt Ortsteil).
        return ka[0] == kb[0] or ort_deckt_sich(ka[2], kb[2])

    _paarweise(merged, gruppen, passt)


def stufe4_ueberlappung(merged: dict) -> None:
    """Dieselbe Veranstaltung, von den Quellen einen Tag versetzt datiert.

    Statt des Termins schützt hier der strengere Namensvergleich. Einsortiert
    wird auch unter der Spielstätte: Beim "Kein Bock auf Nazis Festival" nennt
    festivalhopper die Burg Lichtenberg als Ort, die anderen Quellen die
    Gemeinde Thallichtenberg — ohne diesen zweiten Schlüssel treffen sich die
    Einträge nie.
    """
    gruppen: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in merged.items():
        if not (rec["date_from"] and rec["city"]):
            continue
        for ort in {city_key(rec["city"]), city_key(rec["venue"])}:
            if ort:
                gruppen.setdefault((rec["year"], ort), []).append((key, rec))

    _paarweise(merged, gruppen,
               lambda ka, a, kb, b: zeitraum_ueberlappt(a, b) and name_deckt_sich(ka[0], kb[0]),
               spanne=True)


def stufe5_schreibweise(merged: dict) -> None:
    """Derselbe Name, andere Schreibweise.

    "Sonne Mond Sterne" gegen "SonneMondSterne", "Sziget" gegen "Szigit" — mit
    acht Quellen treffen solche Varianten regelmäßig aufeinander. Der
    Ortsvergleich hält gleichnamige Feste in anderen Städten auseinander.
    """
    gruppen: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in merged.items():
        teile = key[2].split()
        if teile and rec["date_from"]:
            gruppen.setdefault((rec["year"], teile[0]), []).append((key, rec))

    _paarweise(merged, gruppen,
               lambda ka, a, kb, b: (ort_deckt_sich(ka[2], kb[2])
                                     and zeitraum_ueberlappt(a, b)
                                     and schreibweise_gleich(a["name"], b["name"])),
               spanne=True)


def stufe6_ohne_termin(merged: dict) -> None:
    """Eine Quelle kennt noch keinen Termin.

    Terminlose Einträge haben kein Jahr, können also nicht nach Jahrgang mit
    ihrem datierten Zwilling gruppiert werden. Gesucht wird deshalb über den
    zusammengezogenen Namen; kommen mehrere Jahrgänge in Frage, gewinnt der
    früheste Termin. Die Quellen dürfen sich hier überschneiden: Eine
    terminlose Seite ist die Übersichtsseite des Festivals, kein zweites Fest
    am selben Ort.
    """
    def ort_passt(mit: dict, ohne: dict) -> bool:
        sa, sb = city_key(mit["city"]), city_key(ohne["city"])
        if not sb:
            return False
        if sa and (sa == sb or sa in sb or sb in sa):
            return True
        # Die terminlose Seite trägt oft die Spielstätte im Ortsfeld
        # ("Festung Rosenberg" statt Kronach).
        v = city_key(mit["venue"])
        return bool(v and (v == sb or v in sb or sb in v))

    datiert: dict[str, list[tuple]] = {}
    for key, rec in merged.items():
        if rec["date_from"]:
            datiert.setdefault(eng(key[0])[:5], []).append((key, rec))

    for ohne_key in [k for k, r in merged.items() if not r["date_from"]]:
        ohne = merged.get(ohne_key)
        if ohne is None:
            continue
        schluessel = eng(ohne_key[0])
        treffer = [(k, r) for k, r in datiert.get(schluessel[:5], [])
                   if k in merged
                   and (eng(k[0]) == schluessel or schreibweise_gleich(r["name"], ohne["name"]))
                   and ort_passt(r, ohne)]
        if not treffer:
            continue
        _, mit = min(treffer, key=lambda kr: tag_zahl(kr[1]["date_from"]))
        verschmelzen(mit, ohne)
        merged.pop(ohne_key, None)

    # Bleiben mehrere terminlose Einträge desselben Festivals übrig - etwa
    # weil noch kein Jahrgang datiert ist - werden auch sie zusammengelegt.
    offen: dict[str, list[tuple]] = {}
    for key, rec in merged.items():
        if not rec["date_from"]:
            offen.setdefault(eng(key[0]), []).append((key, rec))

    for gruppe in offen.values():
        if len(gruppe) < 2:
            continue
        gruppe = sorted(gruppe, key=lambda kr: kr[1]["_rang"])
        _, keep = gruppe[0]
        for drop_key, drop in gruppe[1:]:
            if city_key(keep["city"]) == city_key(drop["city"]):
                verschmelzen(keep, drop)
                merged.pop(drop_key, None)


def stufe7_gleiche_quelle(merged: dict) -> None:
    """Dieselbe Quelle führt dasselbe Festival zweimal.

    Sonst gilt: Zwei Einträge derselben Quelle bleiben getrennt, weil eine
    Quelle kein Festival doppelt führt — wohl aber zwei gleichnamige an
    verschiedenen Orten. wannafest tut es doch, mit unterschiedlicher
    Schreibweise ("Nacht Wacht XL" und "Nachtwacht XL", Arnheim, derselbe Tag).
    Deshalb zum Schluss diese eine, eng gefasste Ausnahme: identischer
    Namensschlüssel ohne Leerzeichen, gleicher Ort, überlappender Zeitraum.
    """
    gruppen: dict[tuple[str, str, str], list[tuple]] = {}
    for key, rec in merged.items():
        if rec["date_from"] and rec["city"]:
            gruppen.setdefault((eng(key[0]), key[1], key[2]), []).append((key, rec))

    for gruppe in gruppen.values():
        if len(gruppe) < 2:
            continue
        gruppe = sorted(gruppe, key=lambda kr: kr[1]["_rang"])
        _, keep = gruppe[0]
        for drop_key, drop in gruppe[1:]:
            if drop_key in merged and zeitraum_ueberlappt(keep, drop):
                verschmelzen(keep, drop, spanne=True)
                merged.pop(drop_key, None)


def zusammenfuehren(records: list[dict], registry: dict[str, str]) -> list[dict]:
    """Alle Funde zu Festivals bündeln, chronologisch sortiert."""
    merged = stufe1_exakt(records, registry)
    stufe2_quellenpaare(merged)
    stufe3_gleicher_start(merged)
    stufe4_ueberlappung(merged)
    stufe5_schreibweise(merged)
    stufe6_ohne_termin(merged)
    stufe7_gleiche_quelle(merged)

    festivals = []
    for rec in merged.values():
        rec.pop("_rang", None)
        rec["country"] = land_code(rec["country"])
        rec["location"] = ", ".join(x for x in (rec["city"], rec["country"]) if x)
        lineup = sorted(set(rec.pop("_bands").values()), key=str.casefold)
        rec["lineup"] = lineup
        rec["lineup_count"] = len(lineup)
        festivals.append(rec)

    festivals.sort(key=lambda r: (r["year"] or r["date_from"][-4:] or "9999",
                                  r["date_from"][3:5] if r["date_from"] else "99",
                                  r["date_from"][:2] if r["date_from"] else "99",
                                  r["name"].casefold()))
    return festivals
