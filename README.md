# Festival-Übersicht weltweit

Zwölf Festivalverzeichnisse, zu einem weltweiten Bestand zusammengeführt, plus
eine statische Webseite, die daraus Schritt für Schritt nach Ort, Zeitraum,
Entfernung, Preis, Bands und Genre filtert. Ein Datenlauf hält beides aktuell,
ohne dass ein Rechner dafür laufen muss.

**Stand:** 13.563 Festivals in 136 Ländern, 92.187 Acts, 3.422 Festivals aus mehr
als einer Quelle · [Änderungshistorie](https://github.com/Waldsprenger/festival-finder/commits/main)

```
   zwölf Quellen
        │  quellen/          je Quelle eine Datei: Adressen finden, Seite lesen
        ▼
   24.231 Funde              Fund: eingefrorener Datensatz mit festen Feldern
        │  bund/             acht Stufen gegen Dubletten
        ▼
   13.563 Festivals   →   data/festivals.json
        │  ausgabe/          Koordinaten, Preise, Genres, Zahlenreihen
        ▼
   site/data.js + geo.js  →  die Webseite
```

## Der Aufbau

Ein Paket mit einer Tür. Die Kernschicht kennt keine Dateien und kein Netz, die
Quellen kennen kein Zusammenführen, die Ausgabe kennt keine Quellen — was
zusammengehört, liegt beieinander, und was nichts miteinander zu tun hat, weiß
nichts voneinander.

| Modul | Aufgabe |
|---|---|
| `festivalfinder/pfade.py` | Pfade; JSON, Text und Bytes atomar schreiben |
| **`kern/`** | **die Regeln — ohne Ein- und Ausgabe** |
| `festivalfinder/kern/zeit.py` | jede Schreibweise der Quellen → ein `date` |
| `festivalfinder/kern/text.py` | Namen vereinheitlichen: Schlüssel, Bandnamen, Kürzel |
| `festivalfinder/kern/geld.py` | Preise lesen, prüfen, in Euro umrechnen |
| `festivalfinder/kern/orte.py` | Länder, Überseegebiete, Länderkästen, Koordinatenprüfung |
| `festivalfinder/kern/genres.py` | Genre-Freitext → 17 Oberbegriffe |
| `festivalfinder/kern/fund.py` | `Fund`: was eine Quelle liefert, samt Trichter |
| `festivalfinder/kern/festival.py` | `Festival`: was daraus wird, samt Ausgabeform |
| **`netz/`** | **Abruf** |
| `festivalfinder/netz/abrufer.py` | `Abrufer`: holen, zwischenspeichern, Abstand halten, 403 achten, 429 abwarten |
| `festivalfinder/netz/lesen.py` | Elementbaum, Sitemap, Datenblatt (schema.org) |
| **`quellen/`** | **eine Datei je Verzeichnis** |
| `festivalfinder/quellen/basis.py` | was alle zwölf gemeinsam haben |
| `festivalfinder/quellen/festivalticker.py` | dichteste Abdeckung für Deutschland |
| `festivalfinder/quellen/festivalsunited.py` | Lineups, Preise, Datenblatt je Seite |
| `festivalfinder/quellen/festivalalarm.py` | Spielstätte, Besucherzahl, Preise |
| `festivalfinder/quellen/festivalhopper.py` | deutschsprachig, Lineups als Verweise |
| `festivalfinder/quellen/festapp.py` | Frankreich, Italien, Spanien |
| `festivalfinder/quellen/wannafest.py` | Elektronisches, Benelux |
| `festivalfinder/quellen/festivalflyer.py` | Großbritannien und Irland |
| `festivalfinder/quellen/festivalfinder_eu.py` | Klassik, Theater, Osteuropa |
| `festivalfinder/quellen/festivalabroad.py` | weltweit, mit Koordinaten und Genres |
| `festivalfinder/quellen/jambase.py` | Nordamerika, mit vollen Lineups |
| `festivalfinder/quellen/festivalnetworks.py` | 624 Festivals in einer Datei |
| `festivalfinder/quellen/festivism.py` | Nachschlagewerk ohne Termine |
| **`bund/`** | **zusammenführen** |
| `festivalfinder/bund/bandnamen.py` | verbindliche Schreibweisen, Kürzelkollisionen |
| `festivalfinder/bund/regeln.py` | wann zwei Einträge dasselbe Fest meinen |
| `festivalfinder/bund/stufen.py` | die acht Stufen |
| `festivalfinder/bund/lauf.py` | Reihenfolge festlegen, Stufen ausführen |
| **`ausgabe/`** | **was der Lauf hinterlässt** |
| `festivalfinder/ausgabe/dateien.py` | `data/festivals.json` und drei CSV-Tabellen |
| `festivalfinder/ausgabe/verorten.py` | vier Ränge auf dem Weg zur Koordinate |
| `festivalfinder/ausgabe/daten_js.py` | → `site/data.js`, `site/geo.js`, `site/orte.js` und `site/plz.js` |
| `festivalfinder/ausgabe/seitenteile.py` | welche Dateien die Seite lädt — aus ihr selbst gelesen |
| `festivalfinder/ausgabe/uebersicht.py` | → `data/uebersicht.html`, Kontrolltabelle |
| `festivalfinder/ausgabe/pwa.py` | Manifest, App-Symbole, Service Worker |
| `festivalfinder/ausgabe/artefakt.py` | → `site/artifact.html`, alles in einer Datei |
| **`werkzeug/`** | **was seltener läuft** |
| `festivalfinder/werkzeug/gazetteer.py` | Ortsverzeichnisse aus GeoNames |
| `festivalfinder/werkzeug/weltkarte.py` | Kartenumrisse aus Natural Earth |
| `festivalfinder/werkzeug/geokodieren.py` | Ortskoordinaten von Nominatim → `data/geo.json` |
| `festivalfinder/werkzeug/schriften.py` | Display-Schrift als data-URI |
| `festivalfinder/werkzeug/preisverlauf.py` | was ein Ticket zuerst und was es heute kostet |
| `festivalfinder/werkzeug/neuheiten.py` | seit wann wir welches Festival und welche Band kennen |
| `festivalfinder/werkzeug/chronik.py` | ein Strich je Monat: Bestand und Quellenausbeute |
| `festivalfinder/werkzeug/schnappschuss.py` | der Stand einer Quelle, die nicht jeder Lauf erreicht |
| **oben** | |
| `festivalfinder/sammeln.py` | der Sammellauf über alle Quellen |
| `festivalfinder/pruefung.py` | Stimmigkeit des Ergebnisses, Einbruch gegenüber gestern |
| `festivalfinder/cli.py` | ein Einstiegspunkt für alles |
| `festivalfinder/__main__.py` | macht `python -m festivalfinder` möglich |

Und in `site/` die Seite selbst — reines HTML, CSS und JavaScript, kein
Bauschritt, keine Bibliothek. Die Reihenfolge in `index.html` ist verbindlich:
Der Service Worker und die gebündelte Einzelseite lesen genau diese Liste.

| Datei | Aufgabe |
|---|---|
| `site/index.html` | das Gerüst: sechs Schritte, Ergebnis, Rückmeldung, Fuß |
| `site/style.css` | Aussehen, inklusive der Regeln fürs Telefon |
| `site/js/config.js` | einzige Einstellung: Kennung für die Zugriffszählung |
| `site/js/i18n.js` | rund 250 Texte in dreizehn Sprachen |
| `site/js/daten.js` | `window.DATA`, Spaltennamen, abgeleitete Register, Geodaten nachladen |
| `site/js/text.js` | `fold` nach den Regeln aus `data/faltung.json`, Formatierung |
| `site/js/sprache.js` | Übersetzen und Umschalten |
| `site/js/zustand.js` | was eingestellt ist, was daraus folgt, wie sortiert wird |
| `site/js/wohnort.js` | von einer Eingabe aus jedem Land — Postleitzahl, Ort, Adresse — zu einem Punkt auf der Erde |
| `site/js/karte.js` | die Landkarte auf Canvas: Umrisse, Bereich, Pins, Zoom |
| `site/js/kette.js` | die sechs Schritte: aufklappen, zusammenklappen, weiterreichen |
| `site/js/auswahl.js` | Bandsuche und Genreauswahl |
| `site/js/liste.js` | Treffer: Satz, Sortierung, Karten |
| `site/js/wunsch.js` | gemerkte Suchen und was seit dem letzten Besuch dazukam |
| `site/js/oberflaeche.js` | Hilfetexte, Installation, Zählung, Rückmeldung, Rechtstexte |
| `site/js/start.js` | die Verdrahtung |
| `site/data.js` | die Festivals, von `ausgabe/daten_js.py` täglich erzeugt |
| `site/geo.js` | Orte, Postleitzahlen, Kartenumrisse — ändern sich selten, bleiben im Speicher |
| `site/orte.js` | das große Ortsverzeichnis samt Zweitnamen und Bundesstaaten, nur bei Bedarf nachgeladen |
| `site/plz.js` | Postleitzahlen aus 117 Ländern, nur bei Bedarf nachgeladen |

## Selbst bauen

```bash
pip install requests beautifulsoup4 pillow
python -m festivalfinder alles
```

Ein vollständiger Lauf holt rund 26.000 Detailseiten. Alle Quellen sammeln
zugleich, jede in dem Abstand, den ihr Rechner verträgt (siehe „Am 22. August
2026: zu schnell gefragt"). Die Dauer bestimmt damit festivalticker mit gut
100 Minuten; nacheinander, wie bis zum 4. Oktober 2026, waren es acht Stunden.
Jede Seite landet gepackt unter `cache/`, ein zweiter Lauf am selben Tag kommt
ohne einen einzigen Abruf aus. Einzelne Schritte lassen sich auch getrennt
starten:

```bash
python -m festivalfinder sammeln --limit 20   # Testlauf mit wenigen Seiten
python -m festivalfinder sammeln --frisch     # jede Seite neu abrufen
python -m festivalfinder sammeln --since 2006 # das komplette Archiv
python -m festivalfinder alles --offline      # nur aus dem Zwischenspeicher, kein Abruf
python -m festivalfinder bauen                # nur die Webseite
python -m festivalfinder verzeichnis          # Ortsverzeichnis erneuern
python -m festivalfinder karte                # Kartengrenzen erneuern
python -m festivalfinder symbole              # App-Symbole neu zeichnen
```

`--offline` nimmt jede Seite aus `cache/`, gleich wie alt, und fragt keinen
Rechner — weder die Quellen noch Nominatim. Damit lässt sich eine Änderung am
Code gegen genau dieselben Seiten prüfen, ohne die Quellen ein zweites Mal zu
belasten. Ortsverzeichnis und Kartengrenzen überspringt `alles` von selbst,
solange ihre Dateien vollständig da sind; die Schrift gehört nicht mehr zum
täglichen Lauf, sie liegt fertig im Projekt.

Die Webseite braucht keinen Server; `site/index.html` lässt sich per
Doppelklick öffnen.

## Die zwölf Quellen

| Quelle | Weg zu den Adressen | Seiten | Einträge |
|---|---|---:|---:|
| festivism.com | Sitemap; ein Nachschlagewerk ohne Termine | 5.206 | 4.847 |
| festivalsunited.com | Sitemap je Jahrgang **und** alle Länderseiten | 3.235 | 2.755 |
| festivalabroad.com | Sitemap; Titel, wo das Datenblatt fehlt | 3.261 | 3.223 |
| festapp.io | Sitemaps der Festivals und der einzelnen Ausgaben | 2.977 | 1.104 |
| jambase.com | 131 Monatssitemaps, Jahrgang steht in der Adresse | 2.348 | 1.396 |
| wannafest.com | `sitemaps/festivals-1.xml` | 2.113 | 1.072 |
| festivalfinder.eu | Trefferliste der European Festivals Association, geblättert | 2.072 | 413 |
| festivalticker.de | alle Listenseiten: Jahres-, Monats-, Länder- und Statusarchive | 1.971 | 1.966 |
| festival-alarm.com | Jahresseiten **und** die Regionsseiten je Land | 935 | 930 |
| festivalhopper.de | `sitemap-festivals.xml`, Jahrgang steht in der Adresse | 746 | 705 |
| festivalnetworks.com | **eine** JSON-Datei hinter ihrer Karte; ruht seit Oktober 2026 | 1 | 616 |
| festivalflyer.com | die Startseite, mehr ist nicht erreichbar; ruht seit Oktober 2026 | 12 | 1 |

Die zweiten Wege sind nachgemessen, nicht geraten: Über die Länderseiten von
festivalsunited sind 30 Detailseiten erreichbar, die in der Sitemap fehlen —
darunter das Exit Festival in Novi Sad. Und festivalnetworks liefert alles in
einer einzigen Datei; die zu lesen ist genauer und rücksichtsvoller, als 624
Seiten einzeln abzurufen. Dafür hat `Quelle` ein zweites Standbein bekommen:
`sammeldatei` gibt alle Datensätze auf einmal zurück.

Seit dem 9. September 2026 gibt festivalnetworks diese Datei nur noch gegen
ein kurzlebiges Zugangszeichen heraus, das sich ihre Karte vorher holt; ohne
antwortet sie mit 403. Das Zeichen nachzuahmen hieße, die Schranke zu umgehen,
die der Betreiber gerade eingebaut hat. Die Quelle **ruht** deshalb: `ruht`
in ihrer Datei nennt den Grund, der Lauf fragt sie nicht mehr, zählt ihre Null
nicht als Einbruch und vermerkt sie in Bericht und Chronik unter `ruhend`.

Einmal im Monat fragt er doch: Der erste Lauf eines Monats, der also die
Chronikzeile anlegt, ruft die Datei ab wie früher, ohne Zeichen
(`wieder_offen`). Das Ergebnis steht unter `ruhend_geprueft` in Bericht und
Chronik. Kommt die Datei wieder, steht zusätzlich eine Warnung dabei. In den
Bestand fließt sie trotzdem nicht, sonst hätte er an einem Tag im Monat ein
paar hundert Festivals mehr und am nächsten wieder nicht. Ob die Quelle wieder
mitläuft, entscheidet ein Mensch: Dafür genügt es, `ruht` zu leeren.

Seit Oktober 2026 ruht auch **festivalflyer**, aus einem anderen Grund: Die
Startseite nennt nur noch zwei Festivals, ihr Datenblatt trägt kein Land mehr
und bei einem nicht einmal einen Ort; die Detailseiten stehen sogar noch auf
2023. Seit September stand deshalb in jedem Lauf „kein einziger Fund". Die
monatliche Prüfung sieht auf der Startseite nach, ob sie wieder ein kommendes
Festival mit Land nennt — eine Anfrage.

Was jede Quelle beiträgt und wo ihre Fallen liegen, steht im Kopf ihres
Abschnitts in [quellen/](festivalfinder/quellen/). Drei Beispiele:

- **festivalsunited** legt jeder Seite ein Datenblatt nach schema.org bei. Der
  Fließtext hat Vorrang — er beschreibt die dargestellte Ausgabe —, das
  Datenblatt füllt Lücken: Spielstätte, Postleitzahl, Koordinaten,
  Einstiegspreis, Absagestatus. Das brachte die fehlenden Spielstätten von
  2.438 auf 683 und verdoppelte fast die über Postleitzahl verorteten Festivals.
- **wannafest** führt weit überwiegend Clubabende: In einer Stichprobe von 400
  Einträgen waren 359 „Indoor". Übernommen wird nur, was sich als Festival zu
  erkennen gibt — am Namen oder daran, dass es draußen stattfindet.
- **festivalhopper** nennt die Bands als einzelne Verweise. Die echten
  Bandkarten liegen unter `/bands/karten/`; die kürzeren `/bands/`-Adressen
  sind Menüpunkte, die sonst als Acts in 683 Lineups standen.
- **jambase** bringt Nordamerika mit vollständigen Lineups — und nennt Acts
  zweimal, die an zwei Tagen spielen. Entdoppelt wird zentral, in `datensatz()`.
- **festivalabroad** hat für 2.334 seiner 3.261 Feste kein Datenblatt: nämlich
  für die, deren nächster Termin noch aussteht („TBA — last edition: 8 Jul
  2026"). Name, Ort und Land stehen dort im Seitentitel; sie kommen terminlos
  mit. Schneidet der Titel das Land ab („United State…"), bleibt das Feld leer
  statt falsch.
- **festivism** ist ein Nachschlagewerk: Es führt das Fest, nicht seine nächste
  Ausgabe, und nennt deshalb nie ein Datum. Seine 17 Veranstaltungen im Land
  „XW" sind Konzerte in Minecraft und Roblox — die gibt es wirklich, hinfahren
  kann man nicht.

**Nicht erfasst** — geprüft wurden neunzehn weitere Adressen, jede mit
robots.txt und einem Blick auf ihren Aufbau:

| Quelle | Grund |
|---|---|
| bandsintown.com | **403**, robots.txt nennt ClaudeBot ausdrücklich |
| festicket.com | **403**, ClaudeBot in der robots.txt |
| musicfestivalwizard.com | **403**, selbst auf die robots.txt |
| songkick.com | **406**, weist die Anfrage ab |
| dice.fm | 22.209 Einzelveranstaltungen, überwiegend Clubabende und Musikquiz |
| festivalplaner.com, timeout.com, viberate.com | redaktionelle Beiträge, keine Datenbank |
| findyourfest.com, musicworldwidedirectory.com | im Browser zusammengesetzt bzw. reine Linksammlung |
| tools4music.com | 79 Einträge, alle schon vorhanden |
| bachtrack.com, de.concerty.com | Liste wird im Browser zusammengesetzt |
| musicfestadvisor.com, festivalcalendars.com | Listenartikel statt Datenbank |
Die Sperren werden nicht umgangen: Ein Cloudflare-Schutz ist eine Entscheidung
des Betreibers. Dasselbe gilt für **festivalticker** — mit einer Besonderheit,
die lange niemand sah: Vom eigenen Rechner antwortet die Seite normal (200),
dem täglichen Lauf auf GitHub-Servern dagegen mit **403 auf jede einzelne
Listenseite**. Nach fünf Absagen fragt der Lauf dort für den Rest des
Durchgangs nicht weiter — 213 abgewiesene Anfragen je Lauf sind niemandem
gedient. Gespeicherte Seiten kommen weiter aus dem Cache. Dass ein 403 von
festivalticker auch heißen kann „ihr wart zu schnell", zeigte sich erst im
August am eigenen Rechner (siehe unten).

### Weltweit statt nur Europa

Bis zuletzt hat der Lauf alles verworfen, was außerhalb Europas lag — an neun
Stellen: in sechs Lesern, beim Zusammenführen, in der Selbstprüfung und im
Geokodierer. An ihre Stelle ist die Frage getreten, die immer die eigentliche
war: **Ist das überhaupt ein Land?** Sie hält „Bayern" und „Region Hannover"
draußen, ohne einen Erdteil auszuschließen.

Dafür kennt `festivalfinder/kern/orte.py` jetzt alle 252 Staaten — die Liste
entsteht in `festivalfinder/werkzeug/gazetteer.py` aus der Länderdatei von GeoNames und liegt als
`data/laender.json` bei. Deutsche Namen stehen weiter von Hand darin, weil die
Quellen deutsch schreiben; die englischen kommen aus der Datei.

Allein diese Öffnung brachte **538 Festivals in 30 zusätzlichen Ländern**, die
die alten Quellen die ganze Zeit geliefert hatten und die weggeworfen wurden.

### Ein Stand, den der Lauf mitbringt

Damit der veröffentlichten Fassung deswegen nicht rund 800 Festivals fehlen,
legt der Lauf zu Hause ab, was er von festivalticker geholt hat:
`data/schnappschuss/festivalticker.json.gz`, rund 0,6 MB, mitversioniert. Der
Serverlauf liest die Datei, wenn seine eigene Anfrage nichts einbringt. Keine
Sperre wird dabei umgangen — die Daten stammen aus einem Abruf, den die Seite
selbst beantwortet hat.

Drei Regeln halten das ehrlich, alle durch Tests festgehalten:

* **Geschrieben** wird nur, was auch gefunden wurde. Ein Lauf mit null Funden
  lässt die Datei unangetastet — sonst löschte ausgerechnet der Server, was
  der eigene Rechner mitgebracht hat. Teilläufe (`--limit`) schreiben nie.
* **Gelesen** wird nur, wenn die Quelle im Lauf selbst nichts hergibt. Solange
  sie antwortet, gilt ihre Antwort.
* **Datiert** wird nur, was die Quelle wirklich beantwortet hat. Ein Lauf, der
  jede Seite aus dem Zwischenspeicher nimmt, sieht von außen aus wie ein
  frischer und trug den Stand deshalb auf heute — zweimal geschehen, am 22.
  und 23. August. Damit hätte die Alterswarnung unten nie angeschlagen. Jetzt
  zählt, ob in diesem Lauf überhaupt eine Seite von diesem Rechner kam; sonst
  bleibt das alte Datum stehen. Es steht auf dem 21. August 2026, dem Tag, an
  dem die 1.971 Seiten tatsächlich ankamen.

Der Wächter meldet für eine mitgebrachte Quelle nicht mehr ihr Schweigen,
sondern das Alter ihres Standes: ab drei Wochen steht es als Warnung im
Bericht und in der Zusammenfassung des Laufs. Als Einbruch zählt sie dabei
nicht — den Stand frischt nur ein Lauf von zu Hause auf, die Warnung steht also
oft wochenlang in jedem Lauf, und der Maßstab für „ein Fünftel weniger als gestern" fröre sonst
für immer auf dem höchsten je erreichten Wert ein.

#### Am 22. August 2026: zu schnell gefragt

Bis dahin frischte eine Aufgabe der Windows-Aufgabenplanung den Stand jeden
Abend vom eigenen Rechner auf und veröffentlichte ihn, wenn er sich geändert
hatte. Am 22. August beantwortete festivalticker auch von hier jede Anfrage
mit 403, genau wie die des Servers. Das sah aus wie eine Entscheidung gegen
diesen Lauf; die Aufgabe und die beiden Skripte dahinter wurden entfernt.

Es war eine Sperre der Adresse, und der Grund waren wir: zu viele Anfragen in
zu kurzer Zeit. Bis zu vier Arbeitsfäden fragten gleichzeitig, jeder nur 0,3
Sekunden nach seiner vorigen Antwort, rund 2.000 Seiten am Stück. Ein 429 als
Vorwarnung kam nie — festivalticker sperrt gleich. Auf eine Bitte um Ruhe zu
warten, wie es bei jambase hilft, konnte hier also nichts ausrichten.

Seither hält der Abrufer zu jedem Rechner einen **Mindestabstand** ein,
gezählt von Beginn zu Beginn und gleich, wie viele Fäden gerade fragen:
höchstens vier Anfragen je Sekunde im Allgemeinen, bei festivalticker eine
alle drei Sekunden (`ABSTAND_JE_HAUS` in `netz/abrufer.py`). Die Abfragen der
Weiterleitungen zu den Festivalseiten zählen mit, denn sie stehen ebenfalls
bei festivalticker. Ein voller Durchgang dort dauert damit gut 100 Minuten
statt einiger Minuten — das ist der Preis dafür, nicht wieder gesperrt zu
werden.

Am 3. Oktober 2026 antwortete festivalticker dem eigenen Rechner wieder, und
der vollständige Lauf vom 4. Oktober holte alle 2.185 Seiten im neuen Abstand,
ohne eine einzige Absage. Auffrischen kann die abgelegte Datei weiterhin nur
ein Lauf von zu Hause; der Serverlauf bekommt weiter 403 und liest sie.

Die abgelegte Datei bleibt. Sie ist die letzte Abschrift dessen, was die
Quelle beantwortet hat: 2.185 Datensätze vom 4. Oktober 2026. Ohne sie fehlen
der Seite rund 1.900 Festivals von einem Tag auf den anderen — mit ihr altern
sie sichtbar. Vergangene Termine fallen ohnehin heraus, und ab drei Wochen
steht das Datum des Standes als Warnung im Laufbericht. Wann diese Daten zu
alt sind, um sie noch zu zeigen, bleibt damit eine Entscheidung, die jemand
trifft — und keine, die still passiert.

Vom Aufräumen des Caches ist die Datei nicht betroffen: Das löscht nur Dateien
unter `cache/`, nur beim sonntäglichen `--frisch`-Lauf und nur, was seit einer
Woche niemand angefasst hat. `data/schnappschuss/` liegt in der
Versionsverwaltung, nicht im Cache.

## Vom Fund zum Festival

Jede Quelle liefert denselben Datensatz — Name, Zeitraum, Ort, Land,
Postleitzahl, Spielstätte, Preis, Genre, Besucherzahl, Webseite, Absagestatus,
Lineup. Danach wird zusammengeführt.

**Namen** laufen durch einen gemeinsamen Schlüssel: Kleinschreibung, Akzente
aufgelöst, `&`/`and` vereinheitlicht, führendes „The", Satzzeichen und
Jahreszahlen weg. Beim Festivalnamen fallen zusätzlich „Festival", „Fest" und
„Open Air" — auch angehängt: festivalticker führt das Reload Festival als
„Reloadfestival". Der Rumpf muss vier Zeichen behalten, sonst würde aus „Festa"
ein leerer Schlüssel.

**Bandnamen** gruppiert derselbe Schlüssel; je Gruppe gewinnt die häufigste
Schreibweise. Ein Großbuchstabe am Anfang hat Vorrang, sonst gewänne bei
Akronymen `b.o.s.c.h.` gegen `B.O.S.C.H.`.

**Kürzel** stehen in [data/band_aliase.json](data/band_aliase.json) (TBS → The
Butcher Sisters, ADTR → A Day to Remember …) und wirken an zwei Stellen: Beim
Einlesen bekommt das Kürzel denselben Schlüssel wie der ausgeschriebene Name;
im Suchfeld der Seite findet es zusätzlich seine Band. Ein Kürzel kann aber
selbst ein Bandname sein. Entscheidend ist deshalb, ob beide Schreibweisen je
**auf demselben Festival** stehen: „TBS" und „The Butcher Sisters" teilen sich
drei Plakate — dieselbe Band. „LP" und Linkin Park teilen sich kein einziges —
das ist die Sängerin LP, ihre acht Einträge bleiben unangetastet. Geprüft wird
je Festival, nicht je Quellseite: Die Schreibweisen stehen oft auf den Seiten
verschiedener Quellen und treffen sich erst beim Zusammenführen.

**Zweitnamen.** Was kein Buchstabenvergleich findet, steht in
[data/festival_aliase.json](data/festival_aliase.json): „Carnival of Cultures"
ist der Berliner „Karneval der Kulturen", und „Die Schagernacht München" ist
ein Tippfehler in genau dem Wort, das den Namen ausmacht. Die Liste lässt sich
ohne Codeänderung erweitern; der Name wird schon beim Einlesen ersetzt, sodass
alle Stufen und die Anzeige dieselbe Schreibweise sehen.

**Acht Stufen** führen die Einträge zusammen. Die ersten sechs verlangen
verschiedene Quellen — dieselbe Quelle führt kein Festival zweimal, wohl aber
zwei gleichnamige an verschiedenen Orten. Die siebte ist die eng gefasste
Ausnahme davon:

| Stufe | Kriterium | Fängt ab |
|---|---|---|
| 1 | Name + Jahr + Stadt exakt — außer eine Quelle nennt selbst zwei weit entfernte Termine, oder die Länder unterscheiden sich bei weit entferntem oder fehlendem Termin | den Normalfall; getrennt bleiben Bo-Mit-Rock im März und im September, „Bergenfest" (NO) und „Bergen Live" (NL) |
| 2 | eindeutige Quellenpaare zu Name + Jahr, Termine höchstens 14 Tage auseinander | abweichende Ortsschreibweisen („Stemwede" / „Wehdem", „Kattowitz" / „Katowice") |
| 3 | gleicher Starttermin + Ort + gemeinsamer Namensteil | „Kosmos Festival" gegen „Kosmos Festival Chemnitz" |
| 4 | überlappender Zeitraum + Ort **oder Spielstätte**, Name steckt im anderen, kein Beiprogramm („Road to", „Warm-up", „Afterparty") | um einen Tag versetzte Termine (Neuborn Open Air), Gemeinde gegen Spielstätte (Thallichtenberg / Burg Lichtenberg) |
| 5 | ähnliche Schreibweise (82 %), gleicher Ort, überlappender Zeitraum | „SonneMondSterne", „Elbriot", „Szigit" |
| 6 | gleicher Name, eine Quelle ohne Termin, gleicher Ort **oder dieselbe offizielle Adresse** | Übersichtsseiten ohne bestätigtes Datum |
| 7 | derselbe Namenskern, gleicher Ort, überlappender Termin — auch aus einer Quelle | „Glücksgefühle" und „Gluecksgefuehle" in Hockenheim; „Time Warp Festival" und „Time Warp Germany" in Mannheim |
| 8 | gleiche Koordinate, gleicher Tag, verwandter Name | „Hard Summer" und „HARD Summer Music Festival"; „BitterSweet" in Poznań und in Posen |

Die Stadt gehört ab Stufe 1 zum Schlüssel, sonst verschmölze das *Irish Spring
Festival* seine 30 Auftrittsorte zu einem Eintrag. Stufe 2 verzichtet auf den
Ortsvergleich — sie lebt davon, dass die Quellen den Ort verschieden genau
angeben — und prüft dafür den Termin: Ohne diese Frist verband sie das *Campus
Festival* in Dresden mit dem in Debrecen und das *Sommer im Park* in Vellmar
mit dem in Gera; eines der beiden verschwand jeweils aus der Liste. Der Starttermin schützt
Stufe 3: „Winter Wutzrock" im Februar und „Wutzrock" im August teilen Stadt und
Namen, sind aber zwei Feste. In Stufe 4 genügt ein Überlapp, dafür muss ein
Name vollständig im anderen stecken — ein gemeinsames Wort allein reicht nicht,
sonst träfen sich „METAStadt Open Air Wien" und „Afrika Tage Wien" über die
Stadt im Namen. Stufe 6 sucht über den Namen statt über den Jahrgang, den
terminlose Einträge gar nicht haben; kommen mehrere Jahrgänge infrage, gewinnt
der früheste Termin. Vier von fünf terminlosen Einträgen nennen allerdings auch
keinen Ort — mit dem Ortsvergleich allein blieben 222 Doppeleinträge stehen,
Karten ohne Termin, ohne Stadt, ohne Preis. Sie nennen aber die offizielle
Adresse, und `kosmosfestival.fi` gehört genau einem Fest; führt dieselbe
Adresse zu mehreren Städten, bleibt der Eintrag lieber stehen. Und nennt ein
terminloser Eintrag weder Ort noch Adresse — 2.493 tun das —, zählt allein der
Name, aber nur, wenn er im ganzen Land auf eine einzige Stadt zeigt.

Stufe 7 lässt zum Schluss auch zwei Einträge derselben Quelle zusammen. Das ist
die ausdrückliche Ausnahme von der Regel, dass eine Quelle kein Fest doppelt
führt; sie sichert sich stattdessen am **Namenskern**.

**Der Namenskern** ist der Name ohne das, was zwei Quellen verschieden
handhaben: die Ausgabenummer („37. Fränkische Musiktage"), den Ort im Namen
(„Fränkische Musiktage Alzenau"), das Land („Time Warp Germany") und den
Unterschied zwischen „ü" und „ue" („Glücksgefühle" gegen „Gluecksgefuehle").
Alle vier standen doppelt in den Daten.

Er verzeiht aber nichts darüber hinaus. Ein zusätzliches Wort mit eigener
Bedeutung bleibt ein Unterschied: „Gay Pride Festival" und „Hunkering Gay Pride
Festival" stehen am selben Tag in Amsterdam und sind zwei Veranstaltungen. Eine
Ziffer ebenfalls: „ИОНОСФЕРА №15" und „№24" sind zwei Abende einer Reihe und zu
90 % dieselbe Zeichenkette — nennen beide Namen Zahlen und sind es andere,
gehören sie auseinander. Und der Ort fällt nur weg, wenn er auch der Ort des
Festivals ist, sonst verlöre „Rock am Ring" seinen Ring.

Zwei Ausgaben desselben Festivals im selben Jahr (Heartbeatz im Juni und im
September) trennt weiterhin der Termin.

**Wo der genaue Schlüssel zu viel verbindet.** Stufe 1 fragte bis Oktober 2026
nur nach Name, Jahr und Stadt. Das verband dreierlei, was nicht zusammengehört:

* **Zwei Ausgaben eines Jahres.** festivalsunited führt das Bassmania Festival
  in Münster fünfmal, festivalticker Bo-Mit-Rock im März und im September — je
  mit eigener Seite. Daraus wurde ein Eintrag mit dem frühesten Termin und der
  Adresse der zuletzt gelesenen Seite. Jetzt gilt: Nennt **eine Quelle selbst**
  zwei Termine, die mehr als 14 Tage auseinanderliegen, sind es zwei Feste.
  Nennt nur eine Quelle einen abweichenden Termin, irrt sie meist —
  festival-alarm datierte Elbjazz auf den Juni —, und es bleibt bei einem.
* **Zwei Länder.** „Bergenfest" in Norwegen und „Bergen Live" in den
  Niederlanden haben denselben Schlüssel. Und festivism führt „Edgefest" für
  Kanada, Neuseeland und die USA ohne Ort und Termin; aus allen dreien wurde
  einer, und „Africa Festival" in Würzburg verlinkte auf „Africa Live" im
  Senegal. Ein anderes Land trennt jetzt, wenn die Termine weit
  auseinanderliegen oder beide fehlen. Bei nahem Termin irrt eher eine Quelle
  beim Land: wannafest führt manches Hamburger Fest unter den Niederlanden.
* **Ein Beiprogramm** (Stufe 4). Die „Road To Bay Fest"-Reihe läuft vom 10.
  Juli bis zum 12. August und endet am ersten Tag des „Bay Fest"; ein Name
  steckt im anderen, die Zeiträume überlappen. Ein Name, der nur um „Road to",
  „Warm-up", „Pre-Party" oder „Afterparty" länger ist, gilt jetzt nicht mehr
  als derselbe. Ein späterer Beginn allein trennt dagegen nicht: Die
  Konzertreihe ICÓNICA in Sevilla beginnt bei drei Quellen am 29. Mai, am 1.
  und am 17. Juni und ist trotzdem eine.

Zusammen 24 Festivals mehr, jedes mit dem Link auf seine eigene Seite. Weil sich die getrennten Einträge Name, Jahr und Ort teilen, bekommen
sie für Preisgeschichte und Neuzugänge einen Zusatz zur Kennung — das Land oder
den Termin. Der früheste behält die bisherige, damit kein bekanntes Fest über
Nacht als neu erscheint.

Beim Verbinden füllt jede Quelle die Lücken der anderen, Genres werden
gesammelt statt ersetzt, eine Absage aus einer Quelle genügt, und der Zeitraum
spannt vom frühesten Beginn bis zum spätesten Ende.

**Was kein Land ist, fliegt raus** — „Bayern" und „Region Hannover" stehen
manchmal im Länderfeld. Die Prüfung fragt nicht mehr nach dem Erdteil, sondern
ob hinter der Angabe ein Staat steht: `data/laender.json` führt alle 252 mit
ISO-Kürzel, dazu kommen die deutschen Namen aus `festivalfinder/kern/orte.py`.
Eine unbekannte längere Angabe kostet nur das Länderfeld, nicht das Festival:
Ort und Koordinate bleiben.

### Finden alte und neue Quellen zusammen?

Vier neue Verzeichnisse in einen gewachsenen Bestand zu kippen, ist die Probe
aufs Exempel für die Stufen. Nachgezählt:

| | |
|---|---:|
| Festivals aus **alter und neuer** Quelle | 1.340 |
| nur aus neuen Quellen | 7.359 |
| nur aus alten Quellen | 4.736 |
| verdächtige Paare, die noch getrennt stehen | 13 |

Die häufigsten Begegnungen sind festivalsunited + jambase (474),
festivalsunited + festivalabroad (470) und festapp + jambase (415) — die neuen
Quellen bestätigen also massenhaft Bestehendes, statt danebenzustehen.

**Die 13 Übriggebliebenen waren ein Fund.** Von 54 Paaren mit gleichem Namen
und deckungsgleichem Ort liegen 45 über neunzig Tage auseinander: verschiedene
Jahrgänge und echte Zweitausgaben, die getrennt bleiben müssen. Neun liegen
unter 25 Tagen und meinen dasselbe Fest — „Weeze" gegen „Airport Weeze",
„Brügge" gegen „Zeebrugge", „Athen" gegen „Athens", „Hockenheim" gegen
„Hockenheimring".

Der Grund: Stufe 2 verlangte, dass **jeder** Kandidat aus genau einer Quelle
stammt. Ausgerechnet dort, wo der Beweis am stärksten ist — fünf Quellen sagen
„Weeze", eine sagt „Airport Weeze" —, griff sie nicht. Jetzt zählt stattdessen,
dass keine Quelle zwei der Kandidaten führt.

Gegengeprüft an denselben 23.458 Funden, einmal mit der alten und einmal mit
der neuen Regel: **36 Festivals gehen zusammen**, darunter „Rock in Rio Lisboa"
mit „Rock In Rio Lisbon" und „Les Eurockéennes" mit „Les Eurockéennes de
Belfort". „Krach am Bach" bleibt vierfach, weil festivalticker drei der vier
Orte selbst führt — die Regel schützt genau diesen Fall.

Drei Paare bleiben getrennt, jedes aus einem Grund, der die Regel nicht
aufweicht:

| Paar | Warum getrennt |
|---|---|
| Release Athens, 1.6. und 17.6. | 16 Tage; die Frist liegt bei 14 |
| Land Beyond Festival, 1.5. und 24.5. | 23 Tage |
| „Nig Rock Festival" / „Nigrock" | Schlüssel „nig rock" gegen „nigrock" — die Stufe für Schreibweisen verlangt denselben Ort, hier steht „Geestland - Bad Bederkesa" gegen „Bad Bederkesa" |

Drei von 13.496 sind die Grenze dessen, was ohne Raten zu holen ist. Jede
weitere Lockerung träfe auch die 45 Paare, die zwei Jahrgänge oder zwei
Ausgaben desselben Jahres sind — und die gehören auseinander.

## Genres

Die Quellen schreiben das Genre als Freitext — 1.544 verschiedene Angaben von
„Rock" bis „Psychedelic Minimal Techno". Danach sucht niemand, deshalb bildet
[kern/genres.py](festivalfinder/kern/genres.py) sie auf 17 Oberbegriffe ab, zweistufig: Erst die
Fälle, in denen ein Stichwort in die Irre führt („Hardcore Techno" ist kein
Punk, „Classic Rock" keine Klassik), dann die Stichwörter. Mehrere Treffer sind
Absicht: „Ska Punk" gehört zu Punk und zu Reggae/Ska. Bleibt nichts übrig, gilt
„Genreübergreifend" — sobald aber eine Richtung erkennbar ist, fällt die
Sammelkategorie weg.

**„Hardcore" ist zweideutig, und zwar nicht am Wort erkennbar.** In der
Bandmusik heißt es Hardcore Punk, in der Tanzmusik Gabber; die Quellen
schreiben beides gleich. Ein Stichwort reicht dafür nicht — es entscheidet
der Rest der Angabe. Nennt jemand ausdrücklich Punk, Oi! oder Metalcore, gilt
der Punk. Steht daneben harte Tanzmusik (Hardstyle, Frenchcore, Uptempo), oder
ist außer Elektronischem nichts genannt, gilt das Tempo. Ohne diese
Unterscheidung standen **60 reine Elektro-Festivals** unter „Punk & Hardcore",
darunter Defqon.1, Thunderdome, Tomorrowland Brasil und Masters of Hardcore:
Wer nach Punk suchte, bekam sie mitgeliefert.

Ein einzelnes elektronisches Wort kippt dabei nichts: Das StuStaCulum nennt
achtzehn Stile, siebzehn davon mit Band und eines „Deep House" — dort bleibt
der Hardcore der Punk.

## Koordinaten und Preise

Das Ortsverzeichnis ist zweimal fein aufgelöst, weil die beiden Zwecke
verschiedene Rücksichten kennen: Im Browser stehen DE/AT/CH vollständig, denn
dort zählt jedes Kilobyte. Beim Bauen kommen die Niederlande hinzu — wannafest
liefert über tausend niederländische Festivals, viele in Dörfern unter tausend
Einwohnern. Für Großbritannien lohnt es nicht: 3,6 MB Ortsdaten lösen 22
offene Fälle.

Verortet wird in vier Rängen:

1. **Postleitzahl** — trifft den Zustellbereich und ist damit am genauesten.
2. **Ortsname im Geo-Cache**, sofern Nominatim ihn schon einmal beantwortet
   hat — und sofern die Adresse des Treffers nicht ein anderes Land nennt als
   gesucht.
3. **Ortsname im Ortsverzeichnis** (`data/verortung.json`, die Welt ab 1.000
   Einwohnern) — für alles, was der Cache noch nicht kennt.
4. **Punkt aus dem Datenblatt** der Quellseite, aber nur, wenn er im Rahmen
   seines Landes liegt (Landesgrenzen aus dem Ortsverzeichnis, ein Grad
   Toleranz) und nicht als Platzhalter auffällt — erkennbar daran, dass
   dieselbe Koordinate für drei oder mehr verschiedene Orte herhalten muss. Bei
   37 Einträgen sitzt er im falschen Land: Lugano in Buenos Aires, Basel in
   Berlin, Andorra in Mexiko.

**Das Land ist Bedingung, nicht Wunsch.** Beim Geokodieren stand es einmal nur
im ersten von vier Versuchen; scheiterte der, suchte der zweite weltweit — und
Nominatim antwortete willig. Buenos Aires lag danach in Spanien, Mumbai in
Madrid, Jakarta in Berlin, Hongkong in Paris und Santiago de Chile in Kiew: 145
Orte, 179 Festivals. Jetzt geht das Länderkürzel bei jedem Versuch mit, jeder
Treffer wird gegen die Landesangabe seiner eigenen Adresse geprüft, und der
Cache wird beim Bauen noch einmal danach durchgesehen. Nicht am Landesrahmen —
der entsteht aus Ortsnamen und reicht nicht bis Réunion, Puerto Rico oder
Spitzbergen; und ein Gebiet, dessen Anschrift auf den Mutterstaat lautet
(Hongkong → China, Saint-Martin → Frankreich), widerspricht ihm nicht.

**Warum Postleitzahlen weltweit.** Ortsnamen sind mehrdeutig — „Bernau"
gibt es dreimal in Deutschland, und welches gemeint ist, weiß weder ein
Verzeichnis noch ein Suchdienst sicher. Eine Postleitzahl dagegen trifft genau
einen Zustellbereich. Bis vor Kurzem lagen nur die Postleitzahlen von DE/AT/CH
vor; seit die Tabelle die Welt abdeckt (1.080.715 Codes), bekommen **510
Festivals** statt eines geratenen Ortsmittelpunkts ihren Zustellbereich —
Median 1,9 km genauer, in 31 Fällen lag der Ortsname um mehr als 25 km daneben.

**Warum der Cache vor dem Verzeichnis steht.** Wo beide etwas wissen, sind sie
sich einig: Median 0,3 km Abstand, 90 % unter 2,3 km. In 4 % der Fälle wählen
sie verschiedene gleichnamige Orte, und keiner hat nachweislich recht. Deshalb
bleibt es bei der Antwort, die schon in den Daten steht, statt bestehende
Koordinaten ohne Grund zu verschieben.

**Was das spart.** Ein frischer Klon musste 4.816 Orte bei Nominatim erfragen —
bei einer erlaubten Anfrage je Sekunde rund 96 Minuten. Jetzt beantwortet das
Verzeichnis 5.058 Festivals selbst, es bleiben 323 Anfragen und sechs Minuten.
Im Alltag kommen ohnehin nur eine Handvoll neuer Orte dazu.

**Preise** sind Freitext in zehn Währungen. Als Preis zählt nur eine Zahl
unmittelbar an einer Währung, sonst würde „VVK 199 € (Stufe 2)" als 2 €
gelesen. Spannen liefern den unteren Wert, „Spende" und „Zahl was du willst"
ergeben 0 € — ein solcher Nachsatz hinter einer Preisangabe hebt den Preis
dagegen nicht auf.

Angezeigt wird der Quelltext nur dann, wenn er mehr sagt als die Zahl selbst:
„VVK 22,50 € | AK 24 €" nennt zwei Preise, „ab 12,90 Eur" nur den einen —
daraus wurde früher „ab 12,90 € (ab 12,90 Eur)", zweimal dasselbe. Umgerechnet
wird, was in fremder Währung dasteht („ab 168,38 € (VVK 158,85 CHF)"); der
umgerechnete Wert dient ohnehin vor allem dem Preisregler und der Sortierung.

**Tagesaktuelle Preise gibt es nicht — aber die Veränderung.** Die Quellen
nennen fast immer den Preis zum Verkaufsstart und schreiben ihn selten fort.
Von den Veranstalterseiten ist er nicht zu holen: Eine Stichprobe über 60
Festivals ergab, dass 23 % der Seiten das Auslesen in ihrer `robots.txt`
untersagen, und von 22 erreichbaren Ticket-Unterseiten enthielt **keine
einzige** einen lesbaren Preis — die Shops laden per JavaScript nach oder
liegen bei Ticketanbietern.

Was bleibt, ist die eigene Beobachtung: Der Lauf holt die Quellseiten täglich.
[werkzeug/preisverlauf.py](festivalfinder/werkzeug/preisverlauf.py) hält je Festival fest, was zuerst
dastand und was heute dasteht (`data/preis_verlauf.json`). Ändert eine Quelle
ihren Preis, zeigt die Karte den heutigen und dahinter in Klammern den ersten:
„VVK 129 € (zum Start: VVK 89 €)". Festivals, die aus den Quellen
verschwinden, fallen aus der Datei — sonst wüchse sie mit jedem Jahrgang.

## Die Webseite (`site/`)

Reines HTML und JavaScript, kein Server, keine Cookies, keine fremden Dateien.
Die Festivals stehen in `site/data.js` als Zahlenreihen: Bands und Genres nur
als Index, das drückt 13.563 Festivals mit 92.187 Acts auf 4,6 MB (1,9 MB über
die Leitung, weil GitHub Pages komprimiert).

**Was sich täglich ändert, und was nicht.** Bis Oktober 2026 standen auch
Ortsverzeichnis, Postleitzahlen und Kartenumrisse in `data.js` — 5,1 MB, die
sich fast nie ändern und trotzdem nach jedem nächtlichen Lauf neu geladen
wurden. Sie stehen jetzt in `site/geo.js?v=<Stand>`: Der Stand ist ein
Prüfwert über den Inhalt, und eine Datei mit Stand im Namen ändert sich nie.
Der Service Worker hält sie deshalb ohne Rückfrage vor; neu geladen wird erst,
wenn sich das Verzeichnis wirklich ändert. Die Seite zeichnet die Liste, bevor
`geo.js` da ist, und holt sie im Leerlauf nach — Karte und Wohnortsuche warten
darauf, die Liste nicht.

Der Code liegt in zwölf Teilen: `karte.js` zeichnet die Landkarte und kennt vom
Rest nur vier Handgriffe (`start`, `zeichnen`, `setzePins`, `zentrieren`), die
übrigen teilen sich `FF` als einzigen Namensraum. Deutsche Texte stehen ausschließlich in
`i18n.js` — auch die Hilfetexte hinter den Fragezeichen, die früher zusätzlich
im HTML standen und dort auseinanderliefen. Zahlen in diesen Texten kommen aus
den Daten (`Für {ohnePreis} Festivals nennt die Quelle keinen Preis`), damit
sie nicht in dreizehn Sprachen veralten.

**Schritt 1 — Rahmen setzen.** Der Wohnort lässt sich aus jedem Land angeben —
so, wie man ihn dort schreibt: „97209 Veitshöchheim", „Austin, TX", „SW1A 1AA",
„〒100-0001 東京都千代田区", „Москва" oder eine ganze Adresse wie „1600
Pennsylvania Ave NW, Washington, DC 20500". Daraus rechnet die Seite jede
Entfernung.

[site/js/wohnort.js](site/js/wohnort.js) zerlegt die Eingabe zuerst: Was ist
Postleitzahl, was Ort, was Bundesstaat oder Land, was Straße und Hausnummer?
Postleitzahlen erkennt sie an ihrer Form — „100-0001" kann nur Japan sein,
„1100-148" nur Portugal, „M5V 3L9" nur Kanada —, Länder in jeder Sprache, die
der Browser kennt („Japan", „日本", „Deutschland", „USA"), und die Staaten der
USA, Kanadas und Australiens als Kürzel oder ausgeschrieben. In einer Straße
ist eine kurze Zahl die Hausnummer: „Avenida Paulista 1578" liegt nicht in
Sydney, obwohl es dort die Postleitzahl 1578 gibt. Dann sucht sie, von der
billigsten Stufe zur teuersten:

1. **Mitgeliefert** (`geo.js`): die Postleitzahlen von DE/AT/CH und alle Orte
   der Welt ab 15.000 Einwohnern, DE/AT/CH vollständig — 116.653 Stück. Wer
   „97209" eingibt, lädt nichts nach.
2. **Orte nachgeladen** (`orte.js`, 4,8 MB übertragen): 260.592 Orte ab 1.000
   Einwohnern, 114.338 Zweitnamen der Städte ab 100.000 („Warszawa", „Åbo",
   „Москва", „東京", „القاهرة") und 24.207 Orte der USA, Kanadas und
   Australiens mit ihrem Bundesstaat — es gibt 33 Springfields in den USA, und
   „Springfield, IL" meint keines in Missouri.

Jeder Ort trägt seine Einwohnerzahl, und bei gleichem Namen gewinnt erst die
genaue Schreibweise, dann die Größe. Ohne das fand „München" ein Dorf in
Brandenburg und „Mailand" einen Weiler im Allgäu: Die mitgelieferte Liste
führt Deutschland vollständig, und GeoNames nennt die Städte „Munich" und
„Milan" — die deutschen Namen sind dort nur Zweitnamen. Die 2.376 Zweitnamen,
die wie ein Ort der kleinen Liste lauten, liegen deshalb gleich in `geo.js`.
Und „Åbo" ist Turku, nicht das „Abo" in Osttimor: Wer den Kringel schreibt,
meint ihn auch.
3. **Postleitzahlen nachgeladen** (`plz.js`, 2,2 MB übertragen): 117 Länder.
   GeoNames führt 1,08 Millionen Codes, Portugal jede Straße, Singapur jedes
   Haus; für einen Umkreis in Kilometern genügt das Viertel. Jedes Land wird
   deshalb als Präfixbaum verdichtet: Ein Präfix steht für alle Codes darunter,
   sobald sie höchstens fünf Kilometer von ihrem Mittel entfernt liegen —
   319.000 Einträge bleiben. Höchstens zwei Stellen dürfen dabei wegfallen;
   sonst läge Monaco ganz auf dem leeren Präfix, und jede fünfstellige Zahl
   der Welt wäre eine Postleitzahl in Monaco.
4. **Nominatim** — erst wenn nichts davon passt, mit der ganzen Eingabe.
5. Bleibt auch das ohne Treffer, sagt die Seite das — statt still den falschen
   Ort zu nehmen.

Welches Land gemeint ist, wenn es einen Code mehrfach gibt („2000" ist
Unterzögersdorf, Sydney, Antwerpen, Kopenhagen-Frederiksberg …): ein genannter
Ort in der Nähe, ein genanntes Land oder Bundesstaat, sonst die Sprache und
Region des Browsers — wer mit „en-AU" surft, landet in Sydney —, zuletzt
DE/AT/CH. Die übrigen Länder nennt die Seite dazu. Bis Oktober 2026 kannte sie
außerhalb Europas fast nur Ortsnamen ab 15.000 Einwohnern: Von 49 Eingaben aus
aller Welt löste sie 11 selbst auf, und drei landeten falsch — „1600
Pennsylvania Ave …, Washington" in Wien, „1012 AB Amsterdam" in Lausanne,
„2000" für Sydney in Niederösterreich. Jetzt sind es 48 ohne Nominatim; die
übrige, „C1002" in Buenos Aires, führt GeoNames nicht. Dazu Umkreis, Höchstpreis
und Zeitraum, jeweils mit Schalter „auch ohne Angabe zeigen", und einer für
abgesagte Festivals. Die Karte ist ein Canvas aus mitgelieferten Vektorgrenzen
— keine Kartenkacheln, also erfährt kein fremder Server, wo jemand sucht.

**Schritt 2 — Bands oder Genre.** Bandsuche mit Kürzelauflösung und Gewichtung
(×1/×2) oder Genrefilter über die 17 Oberbegriffe.

**Schritt 3 — Treffer.** Übereinstimmung in Prozent, Sortierung je Filterart
verschieden voreingestellt (Bands: Treffer zuerst, Genre: Datum zuerst),
fehlende Angaben immer am Ende. Gezeichnet wird in Stapeln — 25 Karten am
Telefon, 50 am Rechner; alle 300 auf einmal ergaben eine Seite von 109.000
Pixeln Höhe.

`festivalfinder/ausgabe/daten_js.py` prüft seine eigene Ausgabe, bevor sie in die Datei geht: 16
Spalten je Zeile, jede Bandnummer und jeder Genreindex innerhalb der Liste,
Koordinaten immer paarweise, Preise im plausiblen Bereich. Stimmt etwas nicht,
bricht der Lauf ab — dann bleibt die veröffentlichte Seite beim letzten guten
Stand, statt still leer zu bleiben.

**Schnell laden, auch bei schlechtem Netz.** Die Daten stehen als
`window.DATA = JSON.parse('…')` in der Datei statt als JS-Objekt: Der Browser
liest JSON etwa doppelt so schnell wie gleichwertigen Quelltext (gemessen 64
statt 137 ms für 6 MB — auf dem Telefon entsprechend mehr). Der Service Worker
gibt dem Netz 2,5 Sekunden; danach zeigt er den gespeicherten Stand und lädt im
Hintergrund weiter, statt am leeren Bildschirm zu warten. Dateien mit Stand im
Namen (`geo.js?v=…`, `orte.js?v=…`) fragt er gar nicht erst nach, und beim
Wechsel auf einen neuen Stand räumt er den alten weg. Ortsverzeichnis und
Postleitzahlen werden auf drei Nachkommastellen gekürzt — 110 Meter genügen für
einen Wohnort, den ein Umkreisfilter in Kilometern auswertet.

Dazu: dreizehn Sprachen ([js/i18n.js](site/js/i18n.js), 248 Schlüssel), Hilfetexte an
jedem Regler, Installation als App mit Offline-Betrieb, Rückmeldung per
`mailto` und eine Zugriffszählung, die nur startet, wenn in
[js/config.js](site/js/config.js) eine GoatCounter-Kennung steht **und** die Seite
eigenständig über HTTPS läuft. Der Stand bleibt im GoatCounter-Konto; die Seite
zeigt ihn nirgends.

**Welche Sprachen.** Genau die Landessprachen der zwanzig Länder mit den
meisten Festivals (Oktober 2026: DE, US, GB, NL, FR, ES, AU, CH, CA, BE, IT,
AT, PL, CZ, FI, NO, SE, PT, BR, HR): Deutsch, Englisch, Französisch, Spanisch,
Italienisch, Niederländisch, Polnisch, Portugiesisch, Tschechisch, Finnisch,
Schwedisch, Norwegisch (Bokmål) und Kroatisch. Russisch und Türkisch sind
dafür entfallen — Russland steht mit 112 Festivals auf Platz 21, die Türkei
weiter hinten. Nicht dabei ist Rätoromanisch: Es ist Landessprache der
Schweiz, aber gesprochen von einem halben Prozent, das durchweg auch Deutsch
kann. Die Seite wählt beim ersten Besuch die Sprache des Browsers, sofern sie
sie kennt, sonst Deutsch; Norwegisch erkennt sie als „nb", „no" und „nn".
Wer früher Russisch oder Türkisch gewählt hatte, bekommt ebenfalls die
Browsersprache. Die Adresssuche versteht Ländernamen weiter auch auf Russisch
und Türkisch.

**Gemerkte Suchen.** Ein Filter lässt sich unter einem Namen ablegen; beim
nächsten Besuch steht darüber, was seither dazugekommen ist. Zwei Arten von
Neuigkeit zählen, und die zweite ist die interessantere: ein Festival, das es
gestern nicht gab — und eine Band, die bei einem längst bekannten Festival neu
bestätigt wurde. Wacken kennt jeder; interessant wird es, wenn dort Powerwolf
dazukommt. Sind mehrere Bands ausgewählt, genügt eine davon.

Alles bleibt auf dem Gerät. Gespeichert wird im lokalen Speicher des Browsers,
verglichen wird im Browser; es gibt kein Konto, keinen Server und keine
Anmeldung. Wer eine Suche auf ein zweites Gerät bringen will, nimmt den Link:
Der Filter steht darin, base64-verpackt hinter `#l=`.

**Ohne Rückblickgrenze.** Die Seite wird über den Winter oft aufgerufen, weil
dann die Lineups kommen, und im Frühling kaum. Wer nach vierzig Tagen
wiederkommt, bekommt die Änderungen aus vierzig Tagen; wer nach einem halben
Jahr wiederkommt, die aus einem halben Jahr. Möglich ist das, weil nicht
festgehalten wird, *was an welchem Tag passiert ist*, sondern *seit wann wir
etwas kennen*: je Festival ein Datum, je Band im Lineup ein Datum. Dieselbe
Auskunft, aber einmal je Sache statt einmal je Ereignis — und damit ohne
Zeitfenster, das irgendwann abläuft und Änderungen still verschluckt.

Begrenzt wird trotzdem, nur an der richtigen Stelle: Ein Festival, das aus
allen Quellen verschwunden ist, fällt nach 60 Tagen heraus. Die Aufzeichnung
wächst deshalb nicht mit den Jahrgängen, sondern bleibt so groß wie der
Bestand.

Vier Entscheidungen, die dahinterstehen:

* **Bands als Namen, nicht als Nummern.** `band_nr()` vergibt die Indizes bei
  jedem Bau neu, in der Reihenfolge des Auftretens — eine gemerkte 4711 meinte
  morgen eine andere Band. Namen, die aus allen Quellen verschwinden, fallen
  beim Auspacken weg, statt als `undefined` stehen zu bleiben und die Suche
  stumm zu machen.
* **Nur eine Prüfregel.** `FF.PRUEFUNG` bekommt den Filter als Argument, statt
  ihn sich aus `state` zu holen. Eine gemerkte Suche ist derselbe Filter, nur
  nicht der gerade eingestellte, und wird mit denselben Regeln geprüft — nicht
  mit einer zweiten Fassung, die irgendwann davonläuft.
* **Die Neuigkeiten reisen in `data.js` mit, nicht in einer eigenen Datei.**
  Sie zeigen mit Zeilen- und Bandnummern in `data.js` hinein, und die werden
  bei jedem Bau neu vergeben; zwei getrennte Dateien können aus zwei
  verschiedenen Läufen stammen. Genau das wäre der Normalfall gewesen, nicht
  die Ausnahme: Der Service Worker gibt dem Netz 2,5 Sekunden, und die
  Megabytes von `data.js` verlieren dieses Rennen auf dem Telefon fast immer, während
  eine kleine Nebendatei es gewinnt. In der installierten App hätte die
  Meldung damit meistens geschwiegen — ohne ein Wort dazu. In einer Datei kann
  das nicht passieren, und die gebündelte Einzelseite bekommt sie gratis mit.
* **Ein Lauf nach langer Pause urteilt nicht.** Die 60 Tage Geduld fragen „wie
  lange hat keine Quelle das mehr geliefert" — wurde zwei Monate lang gar
  nicht gesammelt, hat niemand gefragt. Ohne diese Ausnahme wäre nach einer
  Laufpause der ganze Bestand „neu". GitHub schaltet zeitgesteuerte Läufe nach
  60 Tagen ohne Aktivität im Projekt ab; die Pause ist keine Erfindung.

Was dazugekommen ist, rechnet der Lauf aus, nicht der Browser:
[werkzeug/neuheiten.py](festivalfinder/werkzeug/neuheiten.py) hält in
`data/bestand_verlauf.json` fest, seit wann es welches Festival gibt und seit
wann welche Band in seinem Lineup steht. Beim Bauen wird daraus `D.neu` —
Tagesnummern ab dem Beginn der Aufzeichnung, nicht Datumsangaben: Aus
„2027-03-14" wird eine dreistellige Zahl.

Zwei Regeln halten die Aufzeichnung ruhig: Der erste Lauf meldet nichts — ohne
Vergleichsstand wären alle 13.338 Festivals neu; der Tag, an dem sie begann,
steht als `beginn` in der Datei, und was dieses Datum trägt, gilt dauerhaft als
„schon immer da". Und ein Festival, das einen Lauf lang fehlt, ist nicht
verschwunden: An dem Tag, an dem festivalticker den Serverlauf abwies, fehlten
1.900 auf einmal; ohne Geduld wären sie am Tag darauf allesamt „neu" gewesen.

**Die App bekommt dasselbe.** „App installieren" ist der übliche
PWA-Weg — dieselbe Seite, derselbe Anwendungsspeicher, derselbe Service
Worker. Gemerkte Suchen und Neuigkeiten funktionieren dort genauso, auch
offline: `data.js` liegt mitsamt `D.neu` im Vorrat des Service Workers.

**Was es (noch) nicht gibt: Push und E-Mail.** Beides ginge, kostet aber sehr
Verschiedenes. Eine Push-Meldung darf inhaltsleer sein — der Service Worker
holt sich die Änderungen und gleicht sie hier ab, der Absender erfährt nie,
wonach jemand sucht. Dafür fehlt nur eine Stelle, die Abo-Endpunkte
entgegennimmt; GitHub kann das nicht, ein kleiner Worker anderswo schon. Eine
E-Mail dagegen muss fertig getextet verschickt werden: Der Abgleich müsste auf
einem Server passieren, und damit lägen Adresse und Bandauswahl dort. Das ist
kein technisches, sondern ein datenschutzrechtliches Vorhaben.

## Veröffentlichen

[GitHub Pages + Actions](.github/workflows/update.yml): Actions führt den
Datenlauf auf GitHub-Servern aus, Pages liefert das Ergebnis aus. Einmalig
unter **Settings → Pages → Source** *GitHub Actions* wählen.

| Wann | Was |
|---|---|
| Mo–Sa 03:17 UTC | `alles`: nur Seiten neu holen, deren Zwischenspeicher älter als 24 Stunden ist |
| So 02:17 UTC | `alles --frisch`: **jede** Seite neu abrufen, danach verwaisten Cache löschen |
| bei jedem Push auf `main` | `bauen`: aus dem Bestand der letzten Nacht neu erzeugen und veröffentlichen |

Ein Push ändert Code, keine Termine — deshalb wird dabei nicht gesammelt. Das
erspart den zwölf Quellen einen Abruf je Commit und dem Lauf zehn Minuten; die
Seite ist trotzdem gleich nach dem Push auf dem neuen Stand. Möglich ist das,
weil ein Sammellauf genau ein Ergebnis hinterlässt — `data/festivals.json` —
und alles Weitere daraus abgeleitet wird: die drei CSV-Tabellen, die
Kontrolltabelle, `data.js`, `geo.js`, `orte.js`, `plz.js`, die Einzelseite. Fehlt der Bestand, weil
der Zwischenspeicher abgelaufen ist, läuft stattdessen der volle Lauf; ohne ihn
gäbe es nichts zu bauen.

Der wöchentliche Komplettabruf ist nötig, weil die Quellen still korrigieren:
Ein verschobener Termin käme sonst erst an, wenn die Seite ohnehin wieder
abgerufen wird. Anschließend fallen Cachedateien weg, die seit einer Woche
niemand angefasst hat — sie gehören zu Festivals, die es in den Quellen nicht
mehr gibt. Die Wochenfrist ist Absicht: Eine Seite, die an diesem Tag nicht
antwortet, behält ihren Stand und fällt nicht gleich heraus.

### Was den Zeitplan am Leben hält

GitHub schaltet zeitgesteuerte Läufe in öffentlichen Projekten ab, sobald 60
Tage lang **niemand ins Projekt geschrieben hat**. Die Läufe selbst zählen
dabei nicht: Ein Projekt kann täglich bauen und trotzdem als verlassen gelten.
Für diese Seite ist das keine graue Theorie — an ihr wird über den Herbst
gearbeitet, wenn die Lineups kommen, und im Frühjahr oft monatelang nicht.

Dagegen steht die **Chronik**: Der Lauf trägt einmal im Monat eine Zeile in
[data/chronik.jsonl](data/chronik.jsonl) nach und schiebt sie ins Projekt.
Bestand, Acts, Funde je Quelle, die Warnungen des Tages. Sie ist für sich
nützlich — `lauf.json` beschreibt nur den letzten Lauf und wird jedes Mal
überschrieben, die Chronik ist die einzige Stelle zum Zurückschauen: Wie ist
der Bestand über die Jahre gewachsen, kam festivalticker je wieder? Dass ihr
Commit nebenbei den Zeitplan am Leben hält, ist die Folge davon und kein
Kunstgriff. Ein leerer Commit täte es technisch auch und wäre genau das: leer.

Zwei Dinge, die dabei zu beachten sind:

* **Keine Schleife.** Der Workflow hört auch auf `push`. Ein Push mit dem
  `GITHUB_TOKEN` löst aber keinen Workflow aus — das verhindert GitHub, um
  genau diese Rekursion zu unterbinden. Wer das später auf einen persönlichen
  Token umstellt, baut sich eine.
* **Der Lauf prüft sich selbst.** Ob ein Commit der Actions-Kennung wirklich
  als „Aktivität" zählt, sagt GitHub nirgends verbindlich zu. Deshalb rechnet
  jeder Lauf aus, wie lange der letzte Schreibvorgang her ist, und meldet es in
  der Zusammenfassung; über 40 Tagen wird daraus eine Warnung. GitHub kündigt
  die Abschaltung zwar auch per E-Mail an, aber die liest man leicht weg.

Was daran hängt, ist mehr als der tägliche Bestand: Der Actions-Cache verfällt,
wenn sieben Tage lang niemand darauf zugreift. Steht der Zeitplan, verschwinden
mit ihm `geo.json`, `preis_verlauf.json`, `quellen_stand.json` und
`bestand_verlauf.json` — und damit die Aufzeichnung, seit wann wir welches
Festival kennen. Sie beginnt danach von vorn: `beginn` steht auf dem Tag der
Wiederaufnahme, es wird also nichts fälschlich als neu gemeldet, aber die Zeit
davor ist als Vergleichsmaßstab verloren.

Von Hand startbar ist beides unter *Actions*; das Feld *Alles neu abrufen*
schaltet den frischen Lauf ein. Mitveröffentlicht werden die Ausgaben unter
`/daten/`: `festivals.json`, `festivals.csv`, `lineups.csv`, `bands.csv`, die
Kontrolltabelle `uebersicht.html` und `lauf.json`.

`lauf.json` ist der Zustandsbericht des letzten Laufs: Funde je Quelle,
Festivals gesamt, Einbruchsmeldungen, nicht ladbare Seiten je Rechnername und
die Hinweise der Leser. Er steht dort, weil das Protokoll eines fremden Servers
niemandem zugänglich ist — und genau dort blieb eine Störung monatelang
verborgen: **festivalticker liefert beim Lauf auf GitHub-Servern nichts**, vom
eigenen Rechner aus dagegen 1.966 Festivals. Der Verdacht fällt auf die
Rechenzentrums-Adressen; die veröffentlichte Fassung hat deshalb rund 800
Festivals weniger als ein Lauf zu Hause.

Der Wächter schwieg dabei, weil eine Null als Maßstab unbrauchbar ist:
`0 < 0 * 0.8` ist falsch, also verglich er nichts mehr. Jetzt meldet er jede
Quelle, die gar nichts liefert — unabhängig davon, was sie früher lieferte. Der
Bericht nennt dazu die Fehlerart samt Statuscode (`www.festivalticker.de
HTTPError 403`), denn 403 ist etwas anderes als 429: das eine ist zu achten,
das andere wäre unsere eigene Ungeduld. Ganz sauber trennt das nicht —
festivalticker antwortet auch auf Ungeduld mit 403. Dagegen hilft nur der
Mindestabstand, bevor es so weit kommt.

## Tests

```bash
pip install pytest pyflakes && python -m pytest tests -q
```

782 Tests in knapp acht Sekunden, ohne Netz und ohne Datenbestand. Sie halten
fest, warum die Regeln so aussehen, wie sie aussehen — fast jeder Fall stand
einmal falsch in den Daten:

| Datei | prüft |
|---|---|
| `tests/kern/test_zeit.py` | jede Schreibweise der Quellen, und was kein Datum ist |
| `tests/kern/test_text.py` | Namen, Schlüssel, Bandnamen, Entschlüsseln, Zeichensalat |
| `tests/kern/test_geld.py` | Preise aus Freitext, Spannen, freier Eintritt, Währungen |
| `tests/kern/test_orte.py` | Länderschreibweisen, Koordinate gegen Land |
| `tests/kern/test_genres.py` | Freitext zu Oberbegriffen, samt Irreführern |
| `tests/kern/test_fund.py` | der Trichter — und was ein eingefrorener Datensatz zusagt |
| `tests/netz/test_abrufer.py` | Abstand je Rechner; 403, 429 und Netzfehler: was der Lauf daraus macht |
| `tests/quellen/test_korpus.py` | alle Leser an 21 echten, eingefrorenen Seiten |
| `tests/quellen/test_eigenheiten.py` | was einzelne Quellen anders machen als alle anderen |
| `tests/bund/test_stufen.py` | die acht Stufen, jede mit ihrer Sicherung |
| `tests/bund/test_bandnamen.py` | Kürzel abschalten, ohne dass es abfärbt |
| `tests/bund/test_verluste.py` | beim Zusammenführen geht keine Quelladresse verloren |
| `tests/ausgabe/test_daten_js.py` | die Prüfung der Zahlenreihen vor dem Ausliefern |
| `tests/ausgabe/test_verorten.py` | vier Ränge auf dem Weg zur Koordinate |
| `tests/seite/test_sprachdatei.py` | Anführungszeichen, dreizehn Sprachen, Platzhalter, Schlüssel |
| `tests/seite/test_aufbau.py` | Kette, Felder, Sortierung, Karte, Module, Faltung |
| `tests/seite/test_rechtstexte.py` | Datenschutz und Fußnote gegen die Daten, die es wirklich gibt |
| `tests/test_sammeln.py` | der Ablauf des Laufs: alle Quellen zugleich, Parsefehler, Schweigen, Zwischenspeicher |
| `tests/test_pruefung.py` | Selbstprüfung und Einbruchsmeldung |
| `tests/test_werkzeug.py` | Preisgeschichte und mitgebrachter Stand |
| `tests/test_neuheiten.py` | seit wann wir was kennen — und wann das schweigt |
| `tests/test_chronik.py` | genau eine Zeile je Monat, auch nach einer Pause |
| `tests/test_werkzeug_netz.py` | Ausfall des Kartendienstes ist kein „Ort unbekannt"; Postleitzahlen der Welt verdichten |
| `tests/test_dateien.py` | JSON schreiben und lesen, auch bei Abbruch mittendrin |
| `tests/test_statisch.py` | pyflakes über den Quelltext — Namen, die erst zur Laufzeit auffielen |
| `tests/test_dokumentation.py` | das README gegen das Projekt, das es wirklich gibt |

Der Workflow führt sie vor jedem Datenlauf aus: Ein Fehler in der Logik soll
auffallen, bevor er sich in die veröffentlichten Daten schreibt.

**An echten Seiten statt an Schnipseln.** Handgeschriebene Testschnipsel halten
fest, was gemeint war — nicht, was die Quellen schicken. Genau dort sassen die
letzten Fehler. In `tests/seiten/` liegen deshalb je Quelle zwei echte Seiten,
eingefroren und gepackt (zusammen 0,5 MB). Jede wird gelesen und das Ergebnis
gegen dieselben Regeln geprüft, die auch der Lauf anlegt; dazu kommt jede Seite
noch einmal leer, abgeschnitten, ohne Auszeichnung und als bloßer Satz. Ein
Leser darf dann nichts finden — abstürzen oder etwas erfinden darf er nicht.

## Wenn eine Quelle sich ändert

Ändert eine Seite ihren Aufbau, liefert ihr Leser stillschweigend weniger — in
der Gesamtliste fällt das kaum auf, weil sieben andere weiter füllen. Der Lauf
vergleicht deshalb jede Quelle mit dem letzten Mal (`data/quellen_stand.json`)
und meldet, wenn eine um mehr als ein Fünftel einbricht. Ebenso gemeldet wird,
wie viele Detailseiten ein Leser gar nicht verarbeiten konnte: Ein einzelner
unerwarteter Wert kostet dieses Festival, nicht den Lauf — aber er soll
auffallen. Ein Preis wie „8.900.00" im Datenblatt hat auf diese Weise 26
Einträge gekostet, bis er auffiel.

**Und der Lauf prüft sein eigenes Ergebnis.** Nicht „wie beim letzten Mal",
sondern „in sich stimmig": Passt das Jahr zum Termin, liegt das Ende nicht vor
dem Anfang, liegt jede Koordinate auf der Erde, zählt das Lineup richtig, ist die
Besucherzahl plausibel, steht im Preisfeld ein Preis, blieb eine Dublette
übrig? Jeder dieser Punkte war schon einmal falsch — zehn Koordinaten in Mexiko
und Buenos Aires, ein Jahrgang 2027 mit Termin im August 2026, eine
Besucherzahl mit 66 Stellen, „Pop Punk" als Preis, eine doppelte Nachtwacht.
Was die Prüfung findet, steht am Ende des Laufs im Protokoll.

### Die Prüfstelle für alle zwölf

Jeder Fund geht durch `datensatz()` — und damit durch dieselbe Plausibilitäts-
prüfung. Das ist Absicht: Was zwölf Leser einzeln beachten müssten, beachtet
keiner zuverlässig.

| Feld | Regel | Anlass |
|---|---|---|
| Land | als Kürzel, und es muss ein Staat sein | sechs Leser lieferten `DE`, zwei „Deutschland" |
| Besucherzahl | genau eine Zahl, 10 bis 5 Mio. | ein Muster griff ins Leere und klebte Datumsziffern zu 66 Stellen zusammen |
| Preis | eine Zahl oder freier Eintritt | auf einer Seite stand „Preis: Pop Punk" |
| Ort | Postleitzahl gehört ins eigene Feld | „104 45 Athen" fand keine Karte |
| Spielstätte | keine Knopfbeschriftung | „Tickets Ticket" stand auf acht Karten |
| Koordinate | auf der Erde, nicht bei null Grad null | Buenos Aires für Lugano; 0/0 heißt „Feld leer" |

**Was die Prüfung ans Licht brachte:** `Besucher:[^0-9]*([\d.]+)` sprang über
ganze Absätze hinweg und holte die nächste Ziffer irgendwo auf der Seite. Auf
Seiten mit dem Wort „Besucherinformationen" ergab das Zahlen mit bis zu 66
Stellen. Das Muster fragt jetzt nur noch dicht am Wort.

## Was fehlt und warum

Feld für Feld gegen die zwischengespeicherten Quellseiten geprüft — bei jedem
fehlenden Wert wurde die Seite nach einem Beleg durchsucht:

| Feld | fehlt | steht doch auf der Seite |
|---|---:|---|
| Besucherzahl | 2.924 | 0 |
| Lineup | 2.750 | — die Quelle führt keins |
| Postleitzahl | 1.924 | 0 |
| Preis | 1.882 | 2 |
| Genre | 1.830 | 0 |
| Spielstätte | 940 | 129-mal nur der Festivalname selbst |
| Webseite | 363 | 0 — verlinkt sind nur Bildnachweise und Werbung |
| Termin | 292 | nur Termine *vergangener* Ausgaben |
| Ort | 247 | 16 |
| Land | 0 | — |

Die Quellen sind damit ausgeschöpft. Zwei Punkte sind erklärungsbedürftig: Die
Einträge ohne Termin nennen auf ihrer Seite sehr wohl ein Datum — das der
**letzten** Ausgabe. Der Scraper übernimmt es bewusst nicht, sondern vermerkt
es als Hinweis, sonst stünden vergangene Termine als kommende in der Liste. Und
die 129 unterdrückten Spielstätten tragen im Datenblatt nur den Festivalnamen,
sagen als Ortsangabe also nichts.

**Auch festivalabroads Ticketangaben helfen nicht.** Das Datenblatt führt ein
Feld `offers`, und der Leser holte es sich jahrelang ab, ohne es je zu
verwenden. Nachgezählt über alle 3.261 Seiten: 853 Angebote, und **kein
einziges** mit einem Preis — dort stehen nur Ticketshop, Verfügbarkeit und
Währung. Die tote Zeile ist raus.

Im Fließtext derselben Seiten stehen dagegen Preise, bei 228 von 3.261 Seiten.
Sie kommen aber zu 97 % von **Vivid Seats**, einem Wiederverkaufsmarkt: „Buy
General Admission Vivid Seats · from US$267" ist ein Angebot auf dem Zweitmarkt,
nicht die Kasse des Veranstalters. Das Preisfeld meint überall sonst den
günstigsten Einstiegspreis; eine Zweitmarktzahl darin würde den Preisfilter
ausschließen lassen, was an der Kasse viel weniger kostet, die Sortierung
verschieben und die Preisbeobachtung mit Marktschwankungen füllen. 159
Festivals bekämen dafür überhaupt erst einen Preis — gut ein Prozent. Der Preis
dafür ist zu hoch, also bleibt es bei „kein Preis".

**Die offiziellen Festivalseiten helfen nicht weiter.** Eine Stichprobe über
180 Festivals: Neun von zehn Veranstalterseiten bieten nichts Maschinenlesbares
an, und wo ein Datenblatt steht, widersprach es kein einziges Mal. Die
Datumsangaben im Fließtext meinen oft gar nicht das Festival, sondern
Vorverkaufsstarts, Nebenveranstaltungen oder Nachrichten. **Bei einer
Abweichung gilt deshalb der Bestand, nicht die Veranstalterseite.**

### Was der Weltmaßstab an Fehlern mitbrachte

Nach dem Umbau noch einmal alles durchgesehen — die acht bekannten Datenklassen
standen auf null, vier neue kamen zum Vorschein.

**Die Koordinate muss zum Land passen.** Solange nur Europa gesammelt wurde,
hielt der europäische Rahmen die groben Verwechslungen ab. Ohne ihn stand
Budapest Park in Berlin, das Kolibri Festival in Delaware und das LongLake
Festival Lugano wieder in Buenos Aires — 41 Fälle. An die Stelle des Rahmens
tritt die richtige Frage: Liegt der Punkt in dem Land, das die Quelle nennt?
Die Kästen dafür entstehen aus dem Ortsverzeichnis (`data/laender_rahmen.json`,
244 Länder) und sind bewusst weit: Las Palmas gehört zu Spanien, Funchal zu
Portugal.

Geprüft wird zweimal — bei jedem Fund und noch einmal nach dem Verschmelzen.
Denn Land und Koordinate können aus verschiedenen Quellen stammen: Eine nannte
Berlin ohne Land, eine andere Deutschland ohne Koordinate, und zusammen ergab
das Lollapalooza Berlin in Chicago.

**Nachschlagewerke führen auch, was gewesen ist.** 185 Einträge von festivism
tragen ein vergangenes Jahr im Namen — „Big Day Out 2000 Auckland", „Anders
Zorns Fiedelwettbewerb 1906". Ohne Termin sahen sie auf der Seite aus wie
offene Ankündigungen. Terminlos plus vergangenes Jahr im Namen heißt: gewesen.

**Gleicher Punkt, gleicher Tag.** Elf Paare standen nebeneinander, die
zusammengehören: „Hard Summer" und „HARD Summer Music Festival", „BitterSweet"
in Poznań und in Posen. Dafür gibt es jetzt Stufe 8 — die Koordinate ist dort
das stärkere Zeichen als der Name. Der Name muss trotzdem passen: In Attard auf
Malta liegen am 11. September zwei verschiedene Veranstaltungen auf demselben
Punkt. Sechs Paare fanden so zusammen, drei Abkürzungen stehen in der
Aliasliste (`ESNS`, `M3F`, `Das Fest`).

**Ersatzschreibweisen aus dem Datenblatt.** „Shaq&#8217;s Fun House",
„Larry &amp; Joe", „Moon Palace Golf &#038; Spa" — 236 Felder trugen
HTML-Ersatzschreibweisen. Im Fließtext nimmt der Parser sie einem ab, im
JSON-Datenblatt nicht. `clean()` löst sie jetzt auf, und `fold()` beginnt mit
`clean()`: Sonst wäre „Larry &amp; Joe" ein anderer Act als „Larry & Joe".

**Die Karte kannte die Datumsgrenze nicht.** Bei 180 Grad springt die Länge auf
-180; wer in Suva sitzt (178 Ost), hätte Honolulu 336 Grad entfernt gesehen
statt 24 — der Pin lag außerhalb des Bildes, während die Liste korrekt 5.090 km
anzeigte. Kein Randfall: Von 832 Festivals im Umkreis von 9.000 km um Suva
liegen 175 jenseits der Grenze. Die Entfernungen selbst stimmten immer, nur die
Projektion nicht.

**Und der schwerste Fund war ein Verhaltensfehler:** Das Zusammenführen hing
von der Reihenfolge der Funde ab. Zwei Läufe über dieselben 23.781 Funde
ergaben 15.483 und 15.512 Festivals — die Seiten kommen aus vier Fäden in
wechselnder Folge zurück, also hätte sich der Bestand täglich verändert, ohne
dass sich an den Quellen etwas ändert. Gegen die alte Fassung gemessen war der
Fehler schon vorher da (21 und 29 Abweichungen); mit acht Quellen fiel er nicht
auf, mit zwölf schon. Seitdem legt `zusammenfuehren()` die Reihenfolge selbst
fest, nach Rang und Adresse. Gemischte Eingabe, gleiches Ergebnis.

## Fehler, die besondere Umstände brauchen

Sechs Klassen, die sich weder im Protokoll noch beim Lesen zeigen — nur im
Vergleich, unter Zeitdruck, an Eingaben, die es so noch nicht gab, oder erst an
einem Tag, der noch nicht gekommen ist.

**„None" stand als Ortsname auf 2.490 Karten.** `str(blatt.get("city", ""))`
sieht sicher aus und ist es nicht: Steht der Schlüssel im Datenblatt und trägt
den Wert `null`, greift der Standardwert nicht — `str(None)` ergibt die
Zeichenkette „None". Sie stand als Ort in der Liste, in der Suche und auf der
Karte, in 123 Fällen als Postleitzahl und in 8 als anklickbare Webseite; der
Geokodierer fragte Nominatim in 111 Ländern nach einem Ort dieses Namens und
bekam Antworten — ein Hotel in Texas, ein Verkehrslandeplatz in Sachsen, eine
Adresse in Bangladesch für ein dänisches Festival. Es gibt jetzt `text.feld()`,
das `null` als leer liest, den Trichter, der eine Webseite ohne `http` verwirft,
und eine Selbstprüfung, die ein Nullwort in einem Textfeld meldet.

**Ein Datum, das nach UTC gerechnet wird, ist östlich davon das von gestern.**
`new Date().toISOString().slice(0,10)` liefert in Neuseeland zwölf Stunden lang
und in Deutschland zwischen Mitternacht und zwei Uhr den Vortag. Die
Voreinstellung „ab heute" zeigte dann Festivals, die gestern zu Ende gegangen
sind. `FF.heute()` liest jetzt Jahr, Monat und Tag nach der Uhr des Betrachters;
ein Test hält fest, dass in den Skripten der Seite kein `toISOString` mehr steht.

**Ein Festival, das gerade läuft, verschwand.** Der Datumsfilter verglich nur
den Beginn; die Vorgabe lautet „ab heute". An einem beliebigen Tag fielen damit
rund hundert laufende Veranstaltungen aus der Liste — sie hatten gestern
angefangen. Jetzt zählt der Zeitraum: Ein Fest ist dabei, solange es noch nicht
vorbei ist. Dieselbe Regel beim Jahrgangsschnitt, sonst hätte der Neujahrstag
jedes Fest verworfen, das über Silvester läuft.

**Ein Ablaufplan als Bandliste legte den Lauf lahm.** Das Muster
`([^()]+?)\s*\(…\)` sucht in einem Text ohne Klammern von jeder Stelle aus bis
zum Ende: 1.000 Uhrzeiten kosteten 3 Sekunden, 4.000 schon 64, 10.000 über
sechs Minuten. Der Namensteil ist jetzt begrenzt, und ohne Klammer im Text
sucht das Muster gar nicht erst — aus 387 Sekunden werden 0,09.

**Kyrillische und griechische Namen gab es nicht.** `fold()` behielt nur
`[a-z0-9]`; von „Мумий Тролль" blieb nichts übrig, der Act galt als namenlos
und fiel aus jedem Lineup. Schlimmer noch: „Ελλάδα Band" schrumpfte auf „band"
und wäre mit jeder anderen so verkürzten Band zusammengefallen. Jetzt bleiben
Buchstaben aller Schriften stehen. Für lateinische Namen ändert sich nichts —
geprüft an allen 40.538 Bandnamen, 17 änderten ihren Schlüssel, jeder davon zum
Besseren.

**Zwei Faltungen, die auseinandergelaufen sind.** Dieselbe Aufgabe, zweimal
umgesetzt: `fold()` im Sammler bildete die Schlüssel, `fold()` im Browser
normalisierte die Suche. Bei jedem achten Bandnamen kamen sie zu
verschiedenen Ergebnissen — wer „2 Engel and Charlie" tippte, fand „2 Engel &
Charlie" nicht, obwohl die Daten beide für dieselbe Band halten. Die Regeln
stehen jetzt auf beiden Seiten gleich; nachgemessen im Browser: 0 Abweichungen
bei 40.538 Bandnamen und 2.781 Orten.

Dazu eine Stelle, die niemandem geschadet hat und trotzdem falsch war:
`alias_kollisionen()` schaltete Kürzel ab, indem es eine Tabelle im Modul
veränderte. Dieselbe Funktion `band_key` antwortete davor und danach
verschieden. Der Vorgang heisst jetzt `alias_abschalten()`, und vor jedem Test
wird die Tabelle zurückgesetzt — sonst hinge ein Testergebnis davon ab, welcher
Test vorher lief.

### Was der erste Serverlauf noch fand

**429 heisst „zu schnell" — und das ist unsere Schuld.** Der erste weltweite
Lauf auf GitHub-Servern verlangte jambase 2.348 Seiten in kurzer Folge ab und
bekam dafür **1.575-mal ein 429**; nur 766 Seiten kamen an. Kein fremdes
Verbot, sondern eigene Ungeduld — und die richtige Antwort darauf ist warten,
nicht lauter fragen.

Der Lauf merkt sich jetzt je Rechner eine Wartezeit. Sie beginnt bei null,
wächst mit jeder Bitte um Ruhe (oder auf den Wert, den ein `Retry-After`
nennt), gilt für alle weiteren Anfragen an denselben Rechner und ist bei acht
Sekunden gedeckelt. Eine Bitte um Ruhe zählt dabei **nicht** als Fehlversuch:
Sonst wären nach drei Bitten die drei regulären Versuche aufgebraucht und die
Seite fiele still heraus.

Nebenbei bestätigte derselbe Lauf, dass festivalticker den Serverlauf wieder
bedient — 1.971 Funde, kein mitgebrachter Stand nötig. Die Sperre von gestern
war keine dauerhafte Entscheidung, sondern vermutlich dieselbe Ungeduld von
unserer Seite.

### Was der Lauf vom 4. Oktober 2026 fand

Der erste vollständige Lauf mit Mindestabstand dauerte **acht Stunden**. 110
Minuten davon gingen bewusst an festivalticker, 3,6 Stunden aber an einen
Fehler in der Bremse: jambase bat nach hundert Seiten einmal um Ruhe, und der
Abrufer nahm die genannte Wartezeit als Takt für den Rest des Laufs — die
übrigen 2.160 Seiten kamen im Abstand von genau sechs Sekunden. Eine
Einzelanfrage beantwortete jambase danach in 0,6 Sekunden. Seither ist ein
`Retry-After` eine Pause für den ganzen Rechner, einmal; der Abstand wächst je
Bitte um eine Sekunde, und vier zugleich abgewiesene Fäden zählen als eine
Bitte. jambase bekommt von vornherein eine Sekunde Abstand.

Und die Quellen warten nicht mehr aufeinander. Nacheinander hatten die übrigen
zehn Rechner während der 110 Minuten bei festivalticker nichts zu tun; jetzt
sammeln alle zugleich, jede in ihrem eigenen Abstand. Rücksicht kostet das
keine, der Abstand gilt je Rechner.

Dazu vier Fehler in den Daten:

* **festivalabroad** hat das Titelformat geändert: „4 Peaks Music Festival –
  Dates to Be Announced | Bend, Unit…". Bei allen 145 Festivals ohne Termin
  stand „Dates to Be Announced | Bend" als Ort in den Daten, fast immer ohne
  Land. Über den Ort findet ein terminloser Eintrag zu seinem datierten — 29
  fanden deshalb nicht zusammen, und 121 dieser Orte gingen als Anfrage an
  Nominatim. Der volle Ort steht im Verweis auf die Länderseite.
* **Zeichensalat** bei 76 Festivals, meist im Lineup: „Nata\x9aa" statt
  „Nataša". Seiten in Windows-1252, gelesen als ISO-8859-1 — Browser behandeln
  beides gleich, `clean()` jetzt auch.
* **Ende vor Anfang**: festivalabroad datierte das NorthSide Festival auf den
  12. bis 6. Juni. Welche Hälfte falsch ist, verrät der Eintrag nicht; ohne
  Termin findet er über Ort und Namen zu dem, den fünf andere Quellen auf den
  4. bis 6. Juni datieren. Vier weitere Funde hatten denselben Widerspruch,
  nur fiel er unter dem Termin anderer Quellen nicht auf.
* **festivalflyer** liefert nichts mehr und ruht (siehe „Die zwölf Quellen").

Beim Messen fiel noch Rechenzeit ab: Das Zusammenführen dauerte 15 Sekunden,
davon zwei Drittel für `fold` — 1,2 Millionen Aufrufe für 126.000 verschiedene
Namen. Mit gemerkten Ergebnissen sind es 5 Sekunden, Festival für Festival
dasselbe Ergebnis. Und jambase baut für den einen Verweis, den es von der
Seite braucht, nur noch die Verweise als Baum auf: 40 statt 61 Millisekunden
je Seite.

### Der Neuaufbau im Oktober 2026

Jedes Modul wurde neu geschrieben und gegen den alten Code geprüft, auf genau
denselben Seiten: Beide lasen offline dieselben 24.231 Funde aus dem
Zwischenspeicher, und jeder Unterschied im Ergebnis musste sich als behobener
Fehler erklären lassen. Gefunden hat das:

* **Postleitzahlen im Ort** in jeder Schreibweise, die nicht deutsch ist:
  „BN2 Brighton", „80-873 Gdańsk", „6060-133 Idanha-a-Nova", „1012 AB
  Amsterdam". Der Ort taugte so weder fürs Zusammenführen noch für die Karte.
* **„und weitere"** als Act in 302 Lineups, **Prosa als Künstlerliste** bei
  festival-alarm, eine Jahreszahl oder Wikidata-Kennung als Ort, 85
  festivalabroad-Einträge, deren „offizielle Seite" die eigene war, 1.054
  Adressen mit Zählparametern (`utm_…`), die Spielstätte als Wiederholung des
  Orts, festapp-Regionen („QC H2X") statt Städten, „- 2026" im Namen.
* **Die Zusammenführung** — siehe „Wo der genaue Schlüssel zu viel verbindet".

Und schneller wurde, was nicht jeden Tag neu sein muss:

* **`data.js` von 9,8 auf 4,6 MB**, weil Orte und Karte in `geo.js` gezogen
  sind und dort im Speicher bleiben. Dazu fielen Felder weg, die die Seite
  nicht mehr las: die Erdteile und die Höchstwerte der Schieberegler, die es
  seit der Umstellung auf ein Eingabefeld nicht mehr gibt.
* **Unveränderte Schritte laufen nicht.** Ortsverzeichnis und Kartengrenzen
  werden nur gebaut, wenn ihre Dateien fehlen; Dateien werden nur geschrieben,
  wenn sich ihr Inhalt geändert hat, und App-Symbole nur gezeichnet, wenn es
  sie nicht gibt.
* **Die Seite rechnet einmal statt sechsmal**: Die Restzahl je Schritt kommt
  aus einem Durchlauf über alle Festivals, Entfernungen werden je Wohnort
  einmal gerechnet und gemerkt.

Gemessen und offen gelassen: Liest ein Lauf alles aus dem Zwischenspeicher,
dauert er gut sieben Minuten, und neun Zehntel davon gehen an den HTML-Parser
von Python (30 ms je Seite bei festivalsunited). Im täglichen Lauf fällt das
nicht ins Gewicht — festivalticker braucht mit seinem Abstand ohnehin 110
Minuten, und gelesen wird nebenher. Das Paket `lxml` würde den Parser etwa
verdreifachen, ist aber eine zusätzliche Abhängigkeit und müsste gegen alle
24.231 Funde geprüft werden; es ist deshalb nicht eingebaut.

### Was nachweislich in Ordnung ist

Nicht jede Prüfung findet etwas, und das ist auch ein Ergebnis. Nachgemessen
und ohne Befund:

| Frage | Messung |
|---|---|
| Verlieren vier Fäden Meldungen? | 4 × 500 Einträge → genau 2.000 |
| Merkt der Wächter einen Einbruch? | halbe Ausbeute → alle zwölf Quellen gemeldet |
| Übersteht der Lauf eine kaputte Sammeldatei? | keine Antwort und ungültiges JSON → 0 Datensätze, kein Absturz |
| Verschieben Zeitzonen den Tag? | festapp schreibt UTC-Abendzeiten, der Leser nimmt das Hauptdatenblatt — „ArtikFest 19.–21. Feb" stimmt |
| Stimmen Entfernungen über die Datumsgrenze? | Suva–Honolulu 5.090 km, Auckland–Santiago 9.670 km |
| Hält die Seite 13.500 Festivals aus? | 568 ms Laden, 646 ms für 8.375 Treffer, 63 MB Speicher |
| Passt die Preisvorgabe von 150 € noch? | Median 62,50 €, 82 % der Festivals mit Preis bleiben sichtbar |

## Wenn etwas mittendrin abbricht

Ein Lauf kann jederzeit enden: Stromausfall, geschlossener Deckel, ein
abgebrochener Prozess. Drei Stellen sind darauf vorbereitet, weil an ihnen
etwas hängt, das sich nicht wiederbeschaffen lässt.

* **JSON wird erst daneben geschrieben und dann an seinen Platz gerückt.**
  Ohne das bliebe eine halbe Datei zurück — bei `preis_verlauf.json` wäre die
  ganze beobachtete Preisgeschichte weg, bei `geo.json` rund 2.000 einzeln
  erfragte Koordinaten.
* **Eine unlesbare Datei hält den Lauf nicht auf.** Sie wird als `.kaputt`
  beiseitegelegt, gemeldet und neu aufgebaut, statt jeden weiteren Lauf
  scheitern zu lassen, bis jemand sie von Hand löscht.
* **Jeder Schritt der Kette hat eine Stunde Zeit.** Das Ortsverzeichnis lief
  einmal vierzehn Stunden, weil eine Prüfung in einer Schleife stand; ein
  hängender Schritt fällt niemandem auf, ein abgebrochener steht im Protokoll.

Dazu zwei Fälle, in denen ein Ausfall sonst dauerhaft würde: Ein Festival, das
in einem Lauf fehlt, behält seine Preisgeschichte noch zwei Monate — sonst
hätte der Tag, an dem eine Quelle schwieg, den Startpreis von 800 Festivals
vergessen. Diese zwei Monate zählen ab dem letzten Sehen, nicht ab der letzten
Preisänderung: Ein Preis, der ein halbes Jahr gleich bleibt, ist der Normalfall
— gälte sein Alter, fielen genau die Einträge zuerst heraus, die die Frist
schützen soll. Und ein Ort, den der Kartendienst gerade nicht beantwortet, gilt
nicht als „unbekannt": Nur eine echte Fehlanzeige kommt in den Cache, ein
Ausfall wird morgen erneut gefragt.

## Bekannte Grenzen

- **Die Seite wiegt beim ersten Besuch 3,8 MB** (gepackt; 10,3 MB roh): 1,9 MB
  Festivals, die täglich neu kommen, und 1,9 MB Orte und Karte, die bleiben.
  Das ist der Preis dafür, dass alles ohne Server läuft: 13.563 Festivals,
  92.187 Acts, 116.653 Orte. Danach lädt ein Besuch nur noch die
  Festivaldatei; unterwegs beim ersten Mal ist es trotzdem viel.
- **Postleitzahlen kennt die Seite aus 120 Ländern**, so viele führt GeoNames.
  Für China, Nigeria, Ägypten, Saudi-Arabien und die übrigen gilt der
  Ortsname, für Brasilien und Argentinien nur der grobe Bereich: GeoNames
  führt dort je Stadt einen Code, nicht die Straßenzüge. Mehrdeutige reine
  Zahlen („06000" gibt es in acht Ländern) entscheidet die Sprache des
  Browsers, sonst das Alphabet — mit Hinweis auf die anderen. Die Einzelseite
  für claude.ai kennt nur DE/AT/CH und Orte ab 15.000 Einwohnern; die großen
  Verzeichnisse lägen dort nur unnötig im Gewicht.
- **3.991 Festivals haben keinen Termin.** Sie kommen aus festivism und aus
  den festivalabroad-Seiten, deren nächste Ausgabe noch nicht feststeht.
  Voreingestellt sind sie ausgeblendet; der Schalter „Festivals ohne Termin
  mitzeigen" holt sie herein.
- **Lineups gibt es für 5.332 Festivals**, überwiegend aus festivalsunited,
  festivalhopper und jambase. festivalabroad hat 10.000 Künstlerseiten, die
  Auftritte nennen könnten — in einer Stichprobe von acht hatte genau eine
  einen Eintrag. 10.000 Abrufe für schätzungsweise 1.500 Zeilen wären der
  Quelle gegenüber unverhältnismäßig.

- festivalticker zeigt für vergangene Jahrgänge nur je 40 Einträge; mehr gibt
  die Seite nicht her.
- 292 Einträge haben kein Datum: Die Quellen führen sie ohne bestätigte
  Neuauflage. Das Feld `Hinweis` nennt dann die letzte gefundene Ausgabe.
- Zwei festivalticker-Seiten reihen Bandnamen ohne jeden Trenner aneinander
  (`Quincy Goldie 333 I Fire Schnuppe …`). Sie bleiben ohne Lineup: Eine
  Aufteilung nach Leerzeichen würde raten und aus „Nebula Allstars" die Band
  „Nebula" machen. Erfundene Bandnamen wären schlimmer als fehlende.
- Bei reinen Akronymen kann die Mehrheitsregel danebengreifen (`GANS` → `Gans`).
- Die Geokodierung fragt zuerst mit dem Land aus der Quelle. Fehlt es, sucht
  sie weltweit — und dann kann „Newark" in New Jersey statt in England landen.
  Das Ortsverzeichnis fängt den Normalfall vorher ab; offen bleiben rund 850
  Orte je Lauf.
- Ein kompletter Archivlauf (`--since 2006`) erzeugt über 23.000 Abrufe und
  eine Datei, die für die Veröffentlichung zu groß wird. Vergangene Jahrgänge
  filtert die Webseite ohnehin heraus.

## Quellen und Lizenzen der Fremddaten

Ortskoordinaten von [OpenStreetMap](https://www.openstreetmap.org/copyright)
(ODbL), Orts- und Postleitzahlenverzeichnis von
[GeoNames](https://www.geonames.org) (CC BY 4.0), Landesgrenzen von
[Natural Earth](https://www.naturalearthdata.com) (gemeinfrei), Schrift Anton
(SIL Open Font License 1.1). Festival- und Lineup-Daten stammen von den acht
oben genannten Verzeichnissen.
