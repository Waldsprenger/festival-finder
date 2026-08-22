# Festival-Übersicht weltweit

Zwölf Festivalverzeichnisse, zu einem weltweiten Bestand zusammengeführt, plus
eine statische Webseite, die daraus Schritt für Schritt nach Ort, Zeitraum,
Entfernung, Preis, Bands und Genre filtert. Ein Datenlauf hält beides aktuell,
ohne dass ein Rechner dafür laufen muss.

**Stand:** 13.339 Festivals in 135 Ländern, 86.266 Acts, 3.049 Festivals aus mehr
als einer Quelle · [Änderungshistorie](https://github.com/Waldsprenger/festival-finder/commits/main)

```
   zwölf Quellen
        │  quellen/          je Quelle eine Datei: Adressen finden, Seite lesen
        ▼
   23.805 Funde              Fund: eingefrorener Datensatz mit festen Feldern
        │  bund/             acht Stufen gegen Dubletten
        ▼
   13.339 Festivals   →   data/festivals.json
        │  ausgabe/          Koordinaten, Preise, Genres, Zahlenreihen
        ▼
   site/data.js  →  die Webseite
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
| `festivalfinder/kern/orte.py` | Länder, Erdteile, Länderkästen, Koordinatenprüfung |
| `festivalfinder/kern/genres.py` | Genre-Freitext → 17 Oberbegriffe |
| `festivalfinder/kern/fund.py` | `Fund`: was eine Quelle liefert, samt Trichter |
| `festivalfinder/kern/festival.py` | `Festival`: was daraus wird, samt Ausgabeform |
| **`netz/`** | **Abruf** |
| `festivalfinder/netz/abrufer.py` | `Abrufer`: holen, zwischenspeichern, 403 achten, 429 abwarten |
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
| `festivalfinder/ausgabe/daten_js.py` | → `site/data.js` und `site/orte.js` |
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
| `site/js/i18n.js` | rund 220 Texte in zehn Sprachen |
| `site/js/daten.js` | `window.DATA`, Spaltennamen, abgeleitete Register |
| `site/js/text.js` | `fold` nach den Regeln aus `data/faltung.json`, Formatierung |
| `site/js/sprache.js` | Übersetzen und Umschalten |
| `site/js/zustand.js` | was eingestellt ist, was daraus folgt, wie sortiert wird |
| `site/js/wohnort.js` | von einer Eingabe zu einem Punkt auf der Erde |
| `site/js/karte.js` | die Landkarte auf Canvas: Umrisse, Bereich, Pins, Zoom |
| `site/js/kette.js` | die sechs Schritte: aufklappen, zusammenklappen, weiterreichen |
| `site/js/auswahl.js` | Bandsuche und Genreauswahl |
| `site/js/liste.js` | Treffer: Satz, Sortierung, Karten |
| `site/js/oberflaeche.js` | Hilfetexte, Installation, Zählung, Rückmeldung, Rechtstexte |
| `site/js/start.js` | die Verdrahtung |
| `site/data.js` | die Daten, von `ausgabe/daten_js.py` erzeugt |
| `site/orte.js` | das große Ortsverzeichnis, nur bei Bedarf nachgeladen |

## Selbst bauen

```bash
pip install requests beautifulsoup4 pillow
python -m festivalfinder alles
```

Der erste Lauf dauert rund 40 Minuten (24.000 Detailseiten, vier parallele
Verbindungen); jede Seite landet gepackt unter `cache/`, ein zweiter Lauf am
selben Tag ist damit in gut acht Minuten durch. Einzelne Schritte lassen sich
auch getrennt starten:

```bash
python -m festivalfinder sammeln --limit 20   # Testlauf mit wenigen Seiten
python -m festivalfinder sammeln --frisch     # jede Seite neu abrufen
python -m festivalfinder sammeln --since 2006 # das komplette Archiv
python -m festivalfinder bauen                # nur die Webseite
python -m festivalfinder verzeichnis          # Ortsverzeichnis erneuern
python -m festivalfinder karte                # Kartengrenzen erneuern
```

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
| festivalnetworks.com | **eine** JSON-Datei hinter ihrer Karte | 1 | 616 |
| festivalflyer.com | die Startseite, mehr ist nicht erreichbar | 12 | 1 |

Die zweiten Wege sind nachgemessen, nicht geraten: Über die Länderseiten von
festivalsunited sind 30 Detailseiten erreichbar, die in der Sitemap fehlen —
darunter das Exit Festival in Novi Sad. Und festivalnetworks liefert alles in
einer einzigen Datei; die zu lesen ist genauer und rücksichtsvoller, als 624
Seiten einzeln abzurufen. Dafür hat `Quelle` ein zweites Standbein bekommen:
`feed` gibt alle Datensätze auf einmal zurück.

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
gedient. Gespeicherte Seiten kommen weiter aus dem Cache.

### Weltweit statt nur Europa

Bis zuletzt hat der Lauf alles verworfen, was außerhalb Europas lag — an neun
Stellen: in sechs Lesern, beim Zusammenführen, in der Selbstprüfung und im
Geokodierer. An ihre Stelle ist die Frage getreten, die immer die eigentliche
war: **Ist das überhaupt ein Land?** Sie hält „Bayern" und „Region Hannover"
draußen, ohne einen Erdteil auszuschließen.

Dafür kennt `gemeinsam.py` jetzt alle 252 Staaten samt Erdteil — die Liste
entsteht in `build_gazetteer.py` aus der Länderdatei von GeoNames und liegt als
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

Zwei Regeln halten das ehrlich, beide durch Tests festgehalten:

* **Geschrieben** wird nur, was auch gefunden wurde. Ein Lauf mit null Funden
  lässt die Datei unangetastet — sonst löschte ausgerechnet der Server, was
  der eigene Rechner mitgebracht hat. Teilläufe (`--limit`) schreiben nie.
* **Gelesen** wird nur, wenn die Quelle im Lauf selbst nichts hergibt. Solange
  sie antwortet, gilt ihre Antwort.

Der Wächter meldet für eine mitgebrachte Quelle nicht mehr ihr Schweigen,
sondern das Alter ihres Standes: ab drei Wochen steht es als Warnung im
Bericht und in der Zusammenfassung des Laufs.

#### Seit dem 22. August 2026: eingefroren

Bis dahin frischte eine Aufgabe der Windows-Aufgabenplanung den Stand jeden
Abend vom eigenen Rechner auf und veröffentlichte ihn, wenn er sich geändert
hatte. Seit dem 22. August weist festivalticker auch diesen Rechner ab — eine
einzelne Anfrage von hier beantwortet die Seite mit 403, genau wie die des
Servers. Damit gibt es nichts mehr aufzufrischen; die Aufgabe und die beiden
Skripte dahinter sind entfernt.

Die abgelegte Datei bleibt. Sie ist die letzte Abschrift dessen, was die
Quelle beantwortet hat: 1.971 Datensätze vom 22. August 2026. Ohne sie fehlen
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

**Sieben Stufen** führen die Einträge zusammen. Die ersten sechs verlangen
verschiedene Quellen — dieselbe Quelle führt kein Festival zweimal, wohl aber
zwei gleichnamige an verschiedenen Orten. Die siebte ist die eng gefasste
Ausnahme davon:

| Stufe | Kriterium | Fängt ab |
|---|---|---|
| 1 | Name + Jahr + Stadt exakt | den Normalfall |
| 2 | eindeutige Quellenpaare zu Name + Jahr, Termine höchstens 14 Tage auseinander | abweichende Ortsschreibweisen („Stemwede" / „Wehdem", „Kattowitz" / „Katowice") |
| 3 | gleicher Starttermin + Ort + gemeinsamer Namensteil | „Kosmos Festival" gegen „Kosmos Festival Chemnitz" |
| 4 | überlappender Zeitraum + Ort **oder Spielstätte**, Name steckt im anderen | um einen Tag versetzte Termine (Neuborn Open Air), Gemeinde gegen Spielstätte (Thallichtenberg / Burg Lichtenberg) |
| 5 | ähnliche Schreibweise (82 %), gleicher Ort, überlappender Zeitraum | „SonneMondSterne", „Elbriot", „Szigit" |
| 6 | gleicher Name, eine Quelle ohne Termin, gleicher Ort **oder dieselbe offizielle Adresse** | Übersichtsseiten ohne bestätigtes Datum |
| 7 | dieselbe Quelle, identischer Name, gleicher Ort, überlappender Termin | „Nacht Wacht XL" und „Nachtwacht XL", beide von wannafest |
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
Adresse zu mehreren Städten, bleibt der Eintrag lieber stehen. Stufe 7 lässt zum Schluss auch zwei Einträge derselben
Quelle zusammen, aber nur bei identischem Namensschlüssel, gleichem Ort und
überlappendem Termin — zwei Ausgaben desselben Festivals im selben Jahr
(Heartbeatz im Juni und im September) bleiben dadurch getrennt.

Beim Verbinden füllt jede Quelle die Lücken der anderen, Genres werden
gesammelt statt ersetzt, eine Absage aus einer Quelle genügt, und der Zeitraum
spannt vom frühesten Beginn bis zum spätesten Ende.

**Was kein Land ist, fliegt raus** — „Bayern" und „Region Hannover" stehen
manchmal im Länderfeld. Die Prüfung fragt nicht mehr nach dem Erdteil, sondern
ob hinter der Angabe ein Staat steht: `data/laender.json` führt alle 252 mit
ISO-Kürzel und Erdteil, dazu kommen die deutschen Namen aus `gemeinsam.py`.
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

## Koordinaten und Preise

Das Ortsverzeichnis ist zweimal fein aufgelöst, weil die beiden Zwecke
verschiedene Rücksichten kennen: Im Browser stehen DE/AT/CH vollständig, denn
dort zählt jedes Kilobyte. Beim Bauen kommen die Niederlande hinzu — wannafest
liefert über tausend niederländische Festivals, viele in Dörfern unter tausend
Einwohnern. Für Großbritannien lohnt es nicht: 3,6 MB Ortsdaten lösen 22
offene Fälle.

Verortet wird in vier Rängen:

1. **Postleitzahl** — trifft den Zustellbereich und ist damit am genauesten.
2. **Ortsname im Geo-Cache**, sofern Nominatim ihn schon einmal beantwortet hat.
3. **Ortsname im Ortsverzeichnis** (`data/verortung.json`, die Welt ab 1.000
   Einwohnern) — für alles, was der Cache noch nicht kennt.
4. **Punkt aus dem Datenblatt** der Quellseite, aber nur, wenn er im Rahmen
   seines Landes liegt (Landesgrenzen aus dem Ortsverzeichnis, ein Grad
   Toleranz) und nicht als Platzhalter auffällt — erkennbar daran, dass
   dieselbe Koordinate für drei oder mehr verschiedene Orte herhalten muss. Bei
   37 Einträgen sitzt er im falschen Land: Lugano in Buenos Aires, Basel in
   Berlin, Andorra in Mexiko.

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
Alle Daten stehen in `site/data.js` als Zahlenreihen: Bands und Genres nur als
Index, das drückt 5.524 Festivals mit 40.547 Acts auf 6,1 MB (2,1 MB über die
Leitung, weil GitHub Pages komprimiert).

Der Code liegt in elf Teilen: `karte.js` zeichnet die Landkarte und kennt vom
Rest nur vier Handgriffe (`start`, `zeichnen`, `setzePins`, `zentrieren`);
`app.js` kümmert sich um alles andere. Deutsche Texte stehen ausschließlich in
`i18n.js` — auch die Hilfetexte hinter den Fragezeichen, die früher zusätzlich
im HTML standen und dort auseinanderliefen. Zahlen in diesen Texten kommen aus
den Daten (`Für {ohnePreis} Festivals nennt die Quelle keinen Preis`), damit
sie nicht in zehn Sprachen veralten.

**Schritt 1 — Rahmen setzen.** Der Wohnort lässt sich überall auf der Welt
angeben, per Postleitzahl oder Ortsname; daraus rechnet die Seite jede
Entfernung. Vier
Stufen, von der billigsten zur teuersten:

1. **Mitgeliefert** (in `data.js`): die Postleitzahlen von DE/AT/CH und alle
   Orte der Welt ab 15.000 Einwohnern, DE/AT/CH vollständig — 116.653 Stück.
   Damit ist der Normalfall ohne einen einzigen Netzabruf beantwortet.
2. **Nachgeladen** (`site/orte.js`, 1,9 MB übertragen): 155.344 Orte bis
   hinunter zu kleinen Gemeinden und 24.893 Postleitzahlen der Länder, deren
   Codes höchstens vierstellig sind. Die Datei kommt erst, wenn die kleine
   Tabelle nichts hergibt — wer „97209" eingibt, lädt sie nie.
3. **Nominatim**, strukturiert gefragt (`postalcode` plus `countrycodes`), für
   fünfstellige Codes wie „75001 FR".
4. Bleibt auch das ohne Treffer, sagt die Seite das — statt still den falschen
   Ort zu nehmen.

Warum die Aufteilung: „1012" gibt es in Lausanne **und** in Amsterdam. Wer
„1012 NL" eingibt, bekam früher die Schweiz, weil nur DACH-Codes vorlagen und
das genannte Land ignoriert wurde. Und Nominatim hilft dort nicht: „75001 FR"
findet der Dienst, „1012 NL" nicht — niederländische Codes sind dort nur mit
ihrem Buchstabenteil erfasst („1012 AB"). Genau diese Länder liegen jetzt in
der nachladbaren Tabelle. Dazu Umkreis, Höchstpreis
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

`build_site.py` prüft seine eigene Ausgabe, bevor sie in die Datei geht: 15
Spalten je Zeile, jede Bandnummer und jeder Genreindex innerhalb der Liste,
Koordinaten immer paarweise, Preise im plausiblen Bereich. Stimmt etwas nicht,
bricht der Lauf ab — dann bleibt die veröffentlichte Seite beim letzten guten
Stand, statt still leer zu bleiben.

**Schnell laden, auch bei schlechtem Netz.** Die Daten stehen als
`window.DATA = JSON.parse('…')` in der Datei statt als JS-Objekt: Der Browser
liest JSON etwa doppelt so schnell wie gleichwertigen Quelltext (gemessen 64
statt 137 ms für 6 MB — auf dem Telefon entsprechend mehr). Der Service Worker
gibt dem Netz 2,5 Sekunden; danach zeigt er den gespeicherten Stand und lädt im
Hintergrund weiter, statt am leeren Bildschirm zu warten. Ortsverzeichnis und
Postleitzahlen werden auf drei Nachkommastellen gekürzt — 110 Meter genügen für
einen Wohnort, den ein Umkreisfilter in Kilometern auswertet.

Dazu: zehn Sprachen ([js/i18n.js](site/js/i18n.js), 190 Schlüssel), Hilfetexte an
jedem Regler, Installation als App mit Offline-Betrieb, Rückmeldung per
`mailto` und eine Zugriffszählung, die nur startet, wenn in
[js/config.js](site/js/config.js) eine GoatCounter-Kennung steht **und** die Seite
eigenständig über HTTPS läuft. Der Stand bleibt im GoatCounter-Konto; die Seite
zeigt ihn nirgends.

## Veröffentlichen

[GitHub Pages + Actions](.github/workflows/update.yml): Actions führt den
Datenlauf auf GitHub-Servern aus, Pages liefert das Ergebnis aus. Einmalig
unter **Settings → Pages → Source** *GitHub Actions* wählen.

| Wann | Was |
|---|---|
| Mo–Sa 03:17 UTC | nur Seiten neu holen, deren Zwischenspeicher älter als 24 Stunden ist |
| So 02:17 UTC | `--frisch`: **jede** Seite neu abrufen, danach verwaisten Cache löschen |

Der wöchentliche Komplettabruf ist nötig, weil die Quellen still korrigieren:
Ein verschobener Termin käme sonst erst an, wenn die Seite ohnehin wieder
abgerufen wird. Anschließend fallen Cachedateien weg, die seit einer Woche
niemand angefasst hat — sie gehören zu Festivals, die es in den Quellen nicht
mehr gibt. Die Wochenfrist ist Absicht: Eine Seite, die an diesem Tag nicht
antwortet, behält ihren Stand und fällt nicht gleich heraus.

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
das andere wäre unsere eigene Ungeduld.

## Tests

```bash
pip install pytest && python -m pytest tests -q
```

711 Tests in gut acht Sekunden, ohne Netz und ohne Datenbestand. Sie halten
fest, warum die Regeln so aussehen, wie sie aussehen — fast jeder Fall stand
einmal falsch in den Daten:

| Datei | prüft |
|---|---|
| `tests/kern/test_zeit.py` | jede Schreibweise der Quellen, und was kein Datum ist |
| `tests/kern/test_text.py` | Namen, Schlüssel, Bandnamen, Entschlüsseln |
| `tests/kern/test_geld.py` | Preise aus Freitext, Spannen, freier Eintritt, Währungen |
| `tests/kern/test_orte.py` | Länderschreibweisen, Koordinate gegen Land |
| `tests/kern/test_genres.py` | Freitext zu Oberbegriffen, samt Irreführern |
| `tests/kern/test_fund.py` | der Trichter — und was ein eingefrorener Datensatz zusagt |
| `tests/netz/test_abrufer.py` | 403, 429 und Netzfehler: was der Lauf daraus macht |
| `tests/quellen/test_korpus.py` | alle Leser an 21 echten, eingefrorenen Seiten |
| `tests/quellen/test_eigenheiten.py` | was einzelne Quellen anders machen als alle anderen |
| `tests/bund/test_stufen.py` | die acht Stufen, jede mit ihrer Sicherung |
| `tests/bund/test_bandnamen.py` | Kürzel abschalten, ohne dass es abfärbt |
| `tests/bund/test_verluste.py` | beim Zusammenführen geht keine Quelladresse verloren |
| `tests/ausgabe/test_daten_js.py` | die Prüfung der Zahlenreihen vor dem Ausliefern |
| `tests/ausgabe/test_verorten.py` | vier Ränge auf dem Weg zur Koordinate |
| `tests/seite/test_sprachdatei.py` | Anführungszeichen, zehn Sprachen, Platzhalter, Schlüssel |
| `tests/seite/test_aufbau.py` | Kette, Felder, Sortierung, Karte, Module, Faltung |
| `tests/seite/test_rechtstexte.py` | Datenschutz und Fußnote gegen die Daten, die es wirklich gibt |
| `tests/test_pruefung.py` | Selbstprüfung und Einbruchsmeldung |
| `tests/test_werkzeug.py` | Preisgeschichte und mitgebrachter Stand |
| `tests/test_werkzeug_netz.py` | Ausfall des Kartendienstes ist kein „Ort unbekannt" |
| `tests/test_dateien.py` | JSON schreiben und lesen, auch bei Abbruch mittendrin |
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

Vier Klassen, die sich weder im Protokoll noch beim Lesen zeigen — nur im
Vergleich, unter Zeitdruck oder an Eingaben, die es so noch nicht gab.

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
vergessen. Und ein Ort, den der Kartendienst gerade nicht beantwortet, gilt
nicht als „unbekannt": Nur eine echte Fehlanzeige kommt in den Cache, ein
Ausfall wird morgen erneut gefragt.

## Bekannte Grenzen

- **Die Seite wiegt 3,4 MB** (gepackt; 9,1 MB roh). Das ist der Preis dafür,
  dass alles in einer Datei steht und ohne Server läuft: 13.435 Festivals,
  81.004 Acts, 116.653 Orte. Nach dem ersten Besuch liegt sie im
  Anwendungsspeicher; unterwegs beim ersten Mal ist es viel.
- **5.621 Festivals haben keinen Termin.** Sie kommen aus festivism und aus
  den festivalabroad-Seiten, deren nächste Ausgabe noch nicht feststeht.
  Voreingestellt sind sie ausgeblendet; der Schalter „Festivals ohne Termin
  mitzeigen" holt sie herein.
- **Lineups gibt es für 4.611 Festivals**, überwiegend aus festivalsunited,
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
