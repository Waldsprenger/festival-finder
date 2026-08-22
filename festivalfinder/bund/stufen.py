"""Acht Stufen, die aus Funden Festivals machen.

Zwölf Quellen beschreiben dieselbe Veranstaltung verschieden: anderer Ort
(„Kronach" gegen „Burg Lichtenberg"), anderer Anreisetag, andere Schreibweise
(„Reloadfestival"), andere Sprache („Posen" gegen „Poznań"). Jede Stufe hat
eine eigene Sicherung gegen falsche Treffer — Tour-Formate wie das Irish Spring
Festival laufen unter einem Namen an 30 Orten und müssen getrennt bleiben, und
zwei Festivals gleichen Namens in verschiedenen Städten erst recht.

Der Schlüssel einer Gruppe ist überall derselbe: (Namensschlüssel, Jahr,
Ortsschlüssel).
"""

from ..kern import zeit
from ..kern.festival import Festival
from ..kern.fund import Fund
from ..kern.text import city_key, clean, eng, festival_key, fold, genres_vereinen
from .regeln import (adresse, name_deckt_sich, namen_verwandt, ort_deckt_sich,
                     schreibweise_gleich)

#: Schlüssel einer Gruppe: Namensschlüssel, Jahr, Ortsschlüssel
Schluessel = tuple[str, str, str]
Bestand = dict[Schluessel, Festival]

#: Felder, bei denen der gefüllte Wert den leeren ersetzt
FELDER = ("von", "bis", "stadt", "land", "ort", "plz",
          "preis", "webseite", "besucher", "hinweis")

#: So weit dürfen zwei Termine auseinanderliegen und noch dasselbe Fest sein.
#: Die Quellen zählen Anreise- und Aufbautage verschieden und datieren
#: mehrtägige Feste mal auf den ersten, mal auf den Haupttag.
NAHER_TERMIN = 14


def ueberlappt(a: Festival, b: Festival) -> bool:
    return zeit.ueberlappt(a.von, a.bis, b.von, b.bis)


def verschmelzen(keep: Festival, drop: Festival, spanne: bool = False) -> None:
    """Zwei Einträge zu einem: fehlende Angaben, Genres, Quellen, Lineups.

    Mit `spanne=True` gelten der früheste Beginn und das späteste Ende — die
    Quellen zählen Anreise- und Aufbautage verschieden.
    """
    for feld in FELDER:
        if not getattr(keep, feld) and getattr(drop, feld):
            setattr(keep, feld, getattr(drop, feld))
    if spanne:
        if drop.von and (not keep.von or drop.von < keep.von):
            keep.von = drop.von
        if drop.bis and (not keep.bis or drop.bis > keep.bis):
            keep.bis = drop.bis
    keep.genre = genres_vereinen(keep.genre, drop.genre)
    if keep.lat is None and drop.lat is not None:
        keep.lat, keep.lon = drop.lat, drop.lon
    keep.abgesagt = keep.abgesagt or drop.abgesagt
    keep.quellen.update(drop.quellen)
    keep.bands.update(drop.bands)


def _paarweise(bestand: Bestand, gruppen: dict, passt, spanne: bool = False) -> None:
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
            if ka not in bestand:
                continue
            for j in range(i + 1, len(gruppe)):
                kb, b = gruppe[j]
                if kb not in bestand or ka not in bestand:
                    continue
                if set(a.quellen) & set(b.quellen):
                    continue
                if not passt(ka, a, kb, b):
                    continue
                keep, drop, weg = ((a, b, kb) if a.rang <= b.rang else (b, a, ka))
                verschmelzen(keep, drop, spanne)
                bestand.pop(weg, None)
                if weg == ka:
                    break


# --------------------------------------------------------------------------
# Stufe 1: der Grundstock
# --------------------------------------------------------------------------

def stufe1_exakt(funde: list[Fund], namen: dict[str, str],
                 band_key, rang: dict[str, int]) -> Bestand:
    """Gleicher Name, gleiches Jahr, gleiche Stadt.

    Die Stadt gehört bewusst zum Schlüssel: Tour-Formate laufen unter einem
    Namen an vielen Orten und sind eigenständige Termine.
    """
    bestand: Bestand = {}
    for f in funde:
        key = (festival_key(f.name), f.jahr, city_key(f.stadt))
        cur = bestand.get(key)
        if cur is None:
            cur = Festival.aus_fund(f, rang.get(f.quelle, len(rang)))
            bestand[key] = cur

        for feld in FELDER:
            if not getattr(cur, feld) and getattr(f, feld):
                setattr(cur, feld, getattr(f, feld))
        # Auch beim ersten Datensatz, obwohl das nach einem Selbstgespraech
        # aussieht: Einzelne Quellseiten wiederholen sich in ihrer eigenen
        # Aufzaehlung ("Ska, NDH, Elektro, Ska, NDH, Elektro"), und der
        # Abgleich ohne Gross-/Kleinschreibung raeumt das weg.
        cur.genre = genres_vereinen(cur.genre, f.genre)
        if cur.lat is None and f.lat is not None:
            cur.lat, cur.lon = f.lat, f.lon

        if len(f.name) > len(cur.name) and f.quelle == "festivalticker":
            cur.name = f.name
        # Bei gleicher Schreibung gewinnt die getrennte: festivalticker führt
        # das Reload Festival als „Reloadfestival", und so stand es dann auch
        # auf der Seite.
        if (fold(f.name).replace(" ", "") == fold(cur.name).replace(" ", "")
                and f.name.count(" ") > cur.name.count(" ")):
            cur.name = f.name
        cur.abgesagt = cur.abgesagt or f.abgesagt
        cur.quellen[f.quelle] = f.url
        for b in f.lineup:
            if (k := band_key(b)):
                cur.bands[k] = namen.get(k, clean(b))
    return bestand


# --------------------------------------------------------------------------
# Stufen 2 bis 8: was Stufe 1 nicht zusammenbrachte
# --------------------------------------------------------------------------

def termine_passen(gruppe: list[tuple]) -> bool:
    """Liegen alle Termine der Gruppe nah beieinander?

    Ohne diese Frage verband Stufe 2 das „Campus Festival" in Dresden mit dem
    in Debrecen und das „Sommer im Park" in Vellmar mit dem in Gera — gleicher
    Name, gleiches Jahr, verschiedene Quellen, aber Monate auseinander. Eines
    der beiden verschwand dabei aus der Liste.
    """
    termine = [rec.von for _, rec in gruppe if rec.von]
    return all((zeit.abstand_tage(a, b) or 0) <= NAHER_TERMIN
               for a in termine for b in termine)


def stufe2_quellenpaare(bestand: Bestand) -> None:
    """Eindeutige Quellenpaare über abweichende Ortsschreibweisen hinweg.

    Gibt es zu Name + Jahr in jeder Quelle genau einen Kandidaten und liegen
    die Termine nah beieinander, gehören sie zusammen — auch wenn die eine
    Quelle die Gemeinde nennt und die andere den Ortsteil („Stemwede" und
    „Wehdem") oder den deutschen statt des polnischen Namens („Kattowitz" und
    „Katowice").
    """
    nach_name: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in bestand.items():
        nach_name.setdefault((key[0], key[1]), []).append((key, rec))

    for gruppe in nach_name.values():
        if len(gruppe) < 2:
            continue
        # Keine Quelle darf zwei der Kandidaten führen: Wer dasselbe Fest
        # zweimal listet, meint zwei verschiedene („Krach am Bach" steht bei
        # festivalticker für drei Feste in drei Orten).
        #
        # Früher musste dafür jeder Kandidat aus genau einer Quelle stammen.
        # Das schloss die Fälle aus, in denen der Beweis am stärksten ist: Beim
        # San Hejmo Festival standen fünf Quellen für „Weeze" gegen eine für
        # „Airport Weeze" — und blieben getrennt.
        quellen = [q for _, rec in gruppe for q in rec.quellen]
        if len(set(quellen)) != len(quellen):
            continue
        if not termine_passen(gruppe):
            continue
        gruppe = sorted(gruppe, key=lambda kr: kr[1].rang)
        _, keep = gruppe[0]
        for weg, drop in gruppe[1:]:
            verschmelzen(keep, drop)
            bestand.pop(weg, None)


def stufe3_gleicher_start(bestand: Bestand) -> None:
    """Dieselbe Veranstaltung, unterschiedlich benannt.

    „Kosmos Festival" (festivalticker) und „Kosmos Festival Chemnitz"
    (festivalsunited) sind dasselbe. Verlangt werden gleicher Starttermin,
    gleiche Stadt und ein gemeinsamer Namensbestandteil. Der Starttermin ist
    der entscheidende Schutz: „Winter Wutzrock" im Februar und „Wutzrock" im
    August teilen Stadt und Namen, sind aber zwei Feste.
    """
    gruppen: dict[tuple, list[tuple]] = {}
    for key, rec in bestand.items():
        if rec.von and rec.stadt:
            gruppen.setdefault((rec.jahr, rec.von), []).append((key, rec))

    def passt(ka, a, kb, b):
        if not (set(ka[0].split()) & set(kb[0].split())):
            return False
        # Bei identischem Namensschlüssel genügt der gleiche Tag; sonst muss
        # auch der Ort zusammenpassen (Gemeinde statt Ortsteil).
        return ka[0] == kb[0] or ort_deckt_sich(ka[2], kb[2])

    _paarweise(bestand, gruppen, passt)


def stufe4_ueberlappung(bestand: Bestand) -> None:
    """Dieselbe Veranstaltung, von den Quellen einen Tag versetzt datiert.

    Statt des Termins schützt hier der strengere Namensvergleich. Einsortiert
    wird auch unter der Spielstätte: Beim „Kein Bock auf Nazis Festival" nennt
    festivalhopper die Burg Lichtenberg als Ort, die anderen Quellen die
    Gemeinde Thallichtenberg — ohne diesen zweiten Schlüssel treffen sich die
    Einträge nie.
    """
    gruppen: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in bestand.items():
        if not (rec.von and rec.stadt):
            continue
        for ort in {city_key(rec.stadt), city_key(rec.ort)}:
            if ort:
                gruppen.setdefault((rec.jahr, ort), []).append((key, rec))

    _paarweise(bestand, gruppen,
               lambda ka, a, kb, b: ueberlappt(a, b) and name_deckt_sich(ka[0], kb[0]),
               spanne=True)


def stufe5_schreibweise(bestand: Bestand) -> None:
    """Derselbe Name, andere Schreibweise.

    „Sonne Mond Sterne" gegen „SonneMondSterne", „Sziget" gegen „Szigit" — mit
    zwölf Quellen treffen solche Varianten regelmäßig aufeinander. Der
    Ortsvergleich hält gleichnamige Feste in anderen Städten auseinander.
    """
    gruppen: dict[tuple[str, str], list[tuple]] = {}
    for key, rec in bestand.items():
        teile = key[2].split()
        if teile and rec.von:
            gruppen.setdefault((rec.jahr, teile[0]), []).append((key, rec))

    _paarweise(bestand, gruppen,
               lambda ka, a, kb, b: (ort_deckt_sich(ka[2], kb[2])
                                     and ueberlappt(a, b)
                                     and schreibweise_gleich(a.name, b.name)),
               spanne=True)


def stufe6_ohne_termin(bestand: Bestand) -> None:
    """Eine Quelle kennt noch keinen Termin.

    Terminlose Einträge haben kein Jahr, können also nicht nach Jahrgang mit
    ihrem datierten Zwilling gruppiert werden. Gesucht wird deshalb über den
    zusammengezogenen Namen; kommen mehrere Jahrgänge in Frage, gewinnt der
    früheste Termin. Die Quellen dürfen sich hier überschneiden: Eine
    terminlose Seite ist die Übersichtsseite des Festivals, kein zweites Fest
    am selben Ort.
    """
    def ort_passt(mit: Festival, ohne: Festival) -> bool:
        sa, sb = city_key(mit.stadt), city_key(ohne.stadt)
        if not sb:
            return False
        if sa and (sa == sb or sa in sb or sb in sa):
            return True
        # Die terminlose Seite trägt oft die Spielstätte im Ortsfeld
        # („Festung Rosenberg" statt Kronach).
        v = city_key(mit.ort)
        return bool(v and (v == sb or v in sb or sb in v))

    def webseite_passt(mit: Festival, ohne: Festival) -> bool:
        """Dieselbe offizielle Adresse — dann ist es dasselbe Fest."""
        a, b = adresse(mit.webseite), adresse(ohne.webseite)
        return bool(a and a == b)

    datiert: dict[str, list[tuple]] = {}
    for key, rec in bestand.items():
        if rec.von:
            datiert.setdefault(eng(key[0])[:5], []).append((key, rec))

    for ohne_key in [k for k, r in bestand.items() if not r.von]:
        ohne = bestand.get(ohne_key)
        if ohne is None:
            continue
        schluessel = eng(ohne_key[0])
        gleichnamig = [(k, r) for k, r in datiert.get(schluessel[:5], [])
                       if k in bestand
                       and (eng(k[0]) == schluessel
                            or schreibweise_gleich(r.name, ohne.name))]
        treffer = [(k, r) for k, r in gleichnamig if ort_passt(r, ohne)]
        if not treffer:
            # Vier von fünf terminlosen Einträgen nennen gar keinen Ort — wohl
            # aber die offizielle Adresse. Sie gehört genau einem Fest und ist
            # damit der bessere Anker. Nur wenn alle Kandidaten in derselben
            # Stadt liegen: sonst wäre offen, welches Fest gemeint ist.
            treffer = [(k, r) for k, r in gleichnamig if webseite_passt(r, ohne)]
            if len({city_key(r.stadt) for _, r in treffer}) > 1:
                treffer = []
        if not treffer:
            continue
        _, mit = min(treffer, key=lambda kr: kr[1].von)
        verschmelzen(mit, ohne)
        bestand.pop(ohne_key, None)

    # Bleiben mehrere terminlose Einträge desselben Festivals übrig — etwa weil
    # noch kein Jahrgang datiert ist — werden auch sie zusammengelegt.
    offen: dict[str, list[tuple]] = {}
    for key, rec in bestand.items():
        if not rec.von:
            offen.setdefault(eng(key[0]), []).append((key, rec))

    for gruppe in offen.values():
        if len(gruppe) < 2:
            continue
        gruppe = sorted(gruppe, key=lambda kr: kr[1].rang)
        _, keep = gruppe[0]
        for weg, drop in gruppe[1:]:
            if city_key(keep.stadt) == city_key(drop.stadt):
                verschmelzen(keep, drop)
                bestand.pop(weg, None)


def stufe7_gleiche_quelle(bestand: Bestand) -> None:
    """Dieselbe Quelle führt dasselbe Festival zweimal.

    Sonst gilt: Zwei Einträge derselben Quelle bleiben getrennt, weil eine
    Quelle kein Festival doppelt führt — wohl aber zwei gleichnamige an
    verschiedenen Orten. wannafest tut es doch, mit unterschiedlicher
    Schreibweise („Nacht Wacht XL" und „Nachtwacht XL", Arnheim, derselbe Tag).
    Deshalb zum Schluss diese eine, eng gefasste Ausnahme: identischer
    Namensschlüssel ohne Leerzeichen, gleicher Ort, überlappender Zeitraum.
    """
    gruppen: dict[tuple[str, str, str], list[tuple]] = {}
    for key, rec in bestand.items():
        if rec.von and rec.stadt:
            gruppen.setdefault((eng(key[0]), key[1], key[2]), []).append((key, rec))

    for gruppe in gruppen.values():
        if len(gruppe) < 2:
            continue
        gruppe = sorted(gruppe, key=lambda kr: kr[1].rang)
        _, keep = gruppe[0]
        for weg, drop in gruppe[1:]:
            if weg in bestand and ueberlappt(keep, drop):
                verschmelzen(keep, drop, spanne=True)
                bestand.pop(weg, None)


def stufe8_gleicher_punkt(bestand: Bestand) -> None:
    """Dieselbe Koordinate, derselbe Tag, ein verwandter Name.

    „Das Fest" und „DAS FEST Karlsruhe" stehen auf demselben Punkt am selben
    Tag; die Namensstufen greifen nicht, weil vom Schlüssel nur „das" übrig
    bleibt. Die Koordinate ist hier das stärkere Zeichen.

    Der Name muss trotzdem passen: In Attard auf Malta liegen am 11. September
    zwei verschiedene Veranstaltungen auf demselben Punkt, und die gehören
    auseinander.
    """
    punkte: dict[tuple, list[tuple]] = {}
    for key, rec in bestand.items():
        if rec.lat is None or not rec.von:
            continue
        punkte.setdefault((round(rec.lat, 2), round(rec.lon, 2), rec.von),
                          []).append((key, rec))

    for gruppe in punkte.values():
        if len(gruppe) < 2:
            continue
        quellen = [q for _, rec in gruppe for q in rec.quellen]
        if len(set(quellen)) != len(quellen):
            continue
        gruppe = sorted(gruppe, key=lambda kr: kr[1].rang)
        _, keep = gruppe[0]
        for weg, drop in gruppe[1:]:
            if weg not in bestand or not namen_verwandt(keep.name, drop.name):
                continue
            verschmelzen(keep, drop)
            bestand.pop(weg, None)


#: Die Stufen nach Stufe 1, in der Reihenfolge, in der sie laufen
NACH_STUFE1 = (stufe2_quellenpaare, stufe3_gleicher_start, stufe4_ueberlappung,
               stufe5_schreibweise, stufe6_ohne_termin, stufe7_gleiche_quelle,
               stufe8_gleicher_punkt)
