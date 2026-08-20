# Festival-Übersicht Europa

Acht Festivalverzeichnisse, zu einem Bestand zusammengeführt, plus eine
statische Webseite, die daraus nach Band oder Genre filtert. Ein Datenlauf
hält beides aktuell, ohne dass ein Rechner dafür laufen muss.

**Stand:** 5.742 Festivals in 42 Ländern, 40.547 Acts, 1.570 Festivals aus mehr
als einer Quelle · [Änderungshistorie](https://github.com/Waldsprenger/festival-finder/commits/main)

```
   acht Quellen
        │  quellen.py         Adressen sammeln, Detailseiten auslesen
        ▼
   11.362 Funde
        │  zusammenfuehren.py sechs Stufen gegen Dubletten
        ▼
   data/festivals.json
        │  build_site.py      Koordinaten, Preise, Genres, Zahlenreihen
        ▼
   site/data.js  →  die Webseite
```

## Die Dateien

| Datei | Aufgabe |
|---|---|
| `scraper/gemeinsam.py` | Pfade, Länderwissen, JSON lesen und schreiben |
| `scraper/netz.py` | Seiten abrufen und zwischenspeichern, HTML und Datenblätter lesen |
| `scraper/text.py` | Namen vereinheitlichen: Schlüssel, Bandnamen, Kürzel, Datum |
| `scraper/quellen.py` | die acht Verzeichnisse — je Quelle: Adressen finden, Seite auslesen |
| `scraper/zusammenfuehren.py` | aus vielen Funden ein Festival: sechs Stufen |
| `scraper/festival_scraper.py` | Ablauf und Ausgaben → `data/festivals.json` + CSV |
| `scraper/genres.py` | Genre-Freitext → 17 Oberbegriffe |
| `scraper/geocode.py` | Ortskoordinaten von Nominatim → `data/geo.json` |
| `scraper/build_gazetteer.py` | Ortsverzeichnisse aus GeoNames: klein für den Browser, groß fürs Verorten |
| `scraper/build_map.py` | Kartenumrisse aus Natural Earth |
| `scraper/fetch_fonts.py` | Display-Schrift als data-URI |
| `scraper/build_site.py` | → `site/data.js` |
| `scraper/build_overview.py` | → `data/uebersicht.html`, Kontrolltabelle |
| `scraper/build_pwa.py` | Manifest, App-Symbole, Service Worker |
| `scraper/build_artifact.py` | → `site/artifact.html`, alles in einer Datei |
| `scraper/daily_update.py` | führt die Kette aus, protokolliert nach `data/update.log` |

Und in `site/` die Seite selbst — reines HTML, CSS und JavaScript, kein
Bauschritt, keine Bibliothek:

| Datei | Aufgabe |
|---|---|
| `site/index.html` | das Gerüst: drei Schritte, Rückmeldung, Fuß |
| `site/style.css` | Aussehen, inklusive der Regeln fürs Telefon |
| `site/karte.js` | die Landkarte auf Canvas: Umrisse, Umkreis, Pins, Zoom |
| `site/app.js` | Sprache, Filter, Auswahl, Trefferliste, Rahmen |
| `site/i18n.js` | 189 Texte in zehn Sprachen |
| `site/config.js` | einzige Einstellung: Kennung für die Zugriffszählung |
| `site/data.js` | die Daten, von `build_site.py` erzeugt |

## Selbst bauen

```bash
pip install requests beautifulsoup4 pillow
python scraper/daily_update.py
```

Der erste Lauf dauert rund 35 Minuten (11.300 Detailseiten, vier parallele
Verbindungen); jede Seite landet unter `cache/`, ein zweiter Lauf am selben Tag
ist damit in gut vier Minuten durch. Einzelne Schritte lassen sich auch
getrennt starten — jedes Skript ist für sich lauffähig.

```bash
python scraper/festival_scraper.py --limit 20   # Testlauf mit wenigen Seiten
python scraper/festival_scraper.py --frisch     # jede Seite neu abrufen
python scraper/festival_scraper.py --since 2006 # das komplette Archiv
```

Die Webseite braucht keinen Server; `site/index.html` lässt sich per
Doppelklick öffnen.

## Die acht Quellen

| Quelle | Weg zu den Adressen | Seiten | Einträge | nur dort |
|---|---|---:|---:|---:|
| festivalsunited.com | Sitemap je Jahrgang **und** die europäischen Länderseiten | 3.226 | 2.776 | 1.527 |
| festapp.io | Sitemaps der Festivals und der einzelnen Ausgaben | 2.977 | 740 | 375 |
| wannafest.com | `sitemaps/festivals-1.xml` | 2.105 | 1.066 | 810 |
| festivalfinder.eu | Trefferliste der European Festivals Association, geblättert | 2.069 | 396 | 367 |
| festivalticker.de | alle Listenseiten: Jahres-, Monats-, Länder- und Statusarchive | 1.971 | 1.966 | 806 |
| festival-alarm.com | Jahresseiten **und** die Regionsseiten je Land | 935 | 921 | 211 |
| festivalhopper.de | `sitemap-festivals.xml`, Jahrgang steht in der Adresse | 728 | 683 | 76 |
| festivalflyer.com | die Startseite, mehr ist nicht erreichbar | 12 | 1 | 0 |

Der Wert einer Quelle steckt nicht in der Zahl ihrer Seiten, sondern in der
Spalte „nur dort". Die zweiten Wege sind nachgemessen, nicht geraten: Über die
Länderseiten von festivalsunited sind 30 Detailseiten erreichbar, die in der
Sitemap fehlen — darunter das Exit Festival in Novi Sad.

Was jede Quelle beiträgt und wo ihre Fallen liegen, steht im Kopf ihres
Abschnitts in [quellen.py](scraper/quellen.py). Drei Beispiele:

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

**Nicht erfasst** werden festicket.com, de.concerty.com und
musicfestivalwizard.com (Cloudflare-Sperre, festicket nennt ClaudeBot
ausdrücklich in seiner `robots.txt`), bachtrack.com (Liste wird im Browser
zusammengesetzt, die Sitemap führt Kritiken) sowie festivalnetworks.com,
musicfestadvisor.com und festivalcalendars.com (Listenartikel statt Datenbank).
Die Sperren werden nicht umgangen: Ein Cloudflare-Schutz ist eine Entscheidung
des Betreibers.

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

**Sieben Stufen** führen die Einträge zusammen. Die ersten sechs verlangen
verschiedene Quellen — dieselbe Quelle führt kein Festival zweimal, wohl aber
zwei gleichnamige an verschiedenen Orten. Die siebte ist die eng gefasste
Ausnahme davon:

| Stufe | Kriterium | Fängt ab |
|---|---|---|
| 1 | Name + Jahr + Stadt exakt | den Normalfall |
| 2 | eindeutige Quellenpaare zu Name + Jahr | abweichende Ortsschreibweisen |
| 3 | gleicher Starttermin + Ort + gemeinsamer Namensteil | „Kosmos Festival" gegen „Kosmos Festival Chemnitz" |
| 4 | überlappender Zeitraum + Ort **oder Spielstätte**, Name steckt im anderen | um einen Tag versetzte Termine (Neuborn Open Air), Gemeinde gegen Spielstätte (Thallichtenberg / Burg Lichtenberg) |
| 5 | ähnliche Schreibweise (82 %), gleicher Ort, überlappender Zeitraum | „SonneMondSterne", „Elbriot", „Szigit" |
| 6 | gleicher Name, eine Quelle ohne Termin | Übersichtsseiten ohne bestätigtes Datum |
| 7 | dieselbe Quelle, identischer Name, gleicher Ort, überlappender Termin | „Nacht Wacht XL" und „Nachtwacht XL", beide von wannafest |

Die Stadt gehört ab Stufe 1 zum Schlüssel, sonst verschmölze das *Irish Spring
Festival* seine 30 Auftrittsorte zu einem Eintrag. Der Starttermin schützt
Stufe 3: „Winter Wutzrock" im Februar und „Wutzrock" im August teilen Stadt und
Namen, sind aber zwei Feste. In Stufe 4 genügt ein Überlapp, dafür muss ein
Name vollständig im anderen stecken — ein gemeinsames Wort allein reicht nicht,
sonst träfen sich „METAStadt Open Air Wien" und „Afrika Tage Wien" über die
Stadt im Namen. Stufe 6 sucht über den Namen statt über den Jahrgang, den
terminlose Einträge gar nicht haben; kommen mehrere Jahrgänge infrage, gewinnt
der früheste Termin. Stufe 7 lässt zum Schluss auch zwei Einträge derselben
Quelle zusammen, aber nur bei identischem Namensschlüssel, gleichem Ort und
überlappendem Termin — zwei Ausgaben desselben Festivals im selben Jahr
(Heartbeatz im Juni und im September) bleiben dadurch getrennt.

Beim Verbinden füllt jede Quelle die Lücken der anderen, Genres werden
gesammelt statt ersetzt, eine Absage aus einer Quelle genügt, und der Zeitraum
spannt vom frühesten Beginn bis zum spätesten Ende.

**Außerhalb Europas** wird verworfen — über den Ländernamen *und* über den
Code: Die Namensliste kannte „usa", nicht aber IN, CL, PY, CO, ZA, ID, KR, KZ,
CR, CN oder TH. Unbekannte längere Angaben („Bayern", „Region Hannover")
bleiben drin; ein Rauswurf auf Verdacht kostet echte Festivals.

## Genres

Die Quellen schreiben das Genre als Freitext — 1.544 verschiedene Angaben von
„Rock" bis „Psychedelic Minimal Techno". Danach sucht niemand, deshalb bildet
[genres.py](scraper/genres.py) sie auf 17 Oberbegriffe ab, zweistufig: Erst die
Fälle, in denen ein Stichwort in die Irre führt („Hardcore Techno" ist kein
Punk, „Classic Rock" keine Klassik), dann die Stichwörter. Mehrere Treffer sind
Absicht: „Ska Punk" gehört zu Punk und zu Reggae/Ska. Bleibt nichts übrig, gilt
„Genreübergreifend" — sobald aber eine Richtung erkennbar ist, fällt die
Sammelkategorie weg.

## Koordinaten und Preise

Verortet wird in vier Rängen:

1. **Postleitzahl** — trifft den Zustellbereich und ist damit am genauesten.
2. **Ortsname im Geo-Cache**, sofern Nominatim ihn schon einmal beantwortet hat.
3. **Ortsname im Ortsverzeichnis** (`data/verortung.json`, ganz Europa ab 1.000
   Einwohnern) — für alles, was der Cache noch nicht kennt.
4. **Punkt aus dem Datenblatt** der Quellseite, aber nur, wenn er im Rahmen
   seines Landes liegt (Landesgrenzen aus dem Ortsverzeichnis, ein Grad
   Toleranz) und nicht als Platzhalter auffällt — erkennbar daran, dass
   dieselbe Koordinate für drei oder mehr verschiedene Orte herhalten muss. Bei
   37 Einträgen sitzt er im falschen Land: Lugano in Buenos Aires, Basel in
   Berlin, Andorra in Mexiko.

**Warum Postleitzahlen für ganz Europa.** Ortsnamen sind mehrdeutig — „Bernau"
gibt es dreimal in Deutschland, und welches gemeint ist, weiß weder ein
Verzeichnis noch ein Suchdienst sicher. Eine Postleitzahl dagegen trifft genau
einen Zustellbereich. Bis vor Kurzem lagen nur die Postleitzahlen von DE/AT/CH
vor; seit die Tabelle ganz Europa abdeckt (410.185 Codes), bekommen **510
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

## Die Webseite (`site/`)

Reines HTML und JavaScript, kein Server, keine Cookies, keine fremden Dateien.
Alle Daten stehen in `site/data.js` als Zahlenreihen: Bands und Genres nur als
Index, das drückt 5.742 Festivals mit 40.547 Acts auf 6,1 MB (2,1 MB über die
Leitung, weil GitHub Pages komprimiert).

Der Code liegt in zwei Teilen: `karte.js` zeichnet die Landkarte und kennt vom
Rest nur vier Handgriffe (`start`, `zeichnen`, `setzePins`, `zentrieren`);
`app.js` kümmert sich um alles andere. Deutsche Texte stehen ausschließlich in
`i18n.js` — auch die Hilfetexte hinter den Fragezeichen, die früher zusätzlich
im HTML standen und dort auseinanderliefen. Zahlen in diesen Texten kommen aus
den Daten (`Für {ohnePreis} Festivals nennt die Quelle keinen Preis`), damit
sie nicht in zehn Sprachen veralten.

**Schritt 1 — Rahmen setzen.** Wohnort per Postleitzahl (auch „1010 AT" zur
Trennung von Österreich und Schweiz) oder Ortsname, gesucht im mitgelieferten
Verzeichnis; Nominatim nur, wenn lokal nichts passt. Dazu Umkreis, Höchstpreis
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

**Schnell laden, auch bei schlechtem Netz.** Die Daten stehen als
`window.DATA = JSON.parse('…')` in der Datei statt als JS-Objekt: Der Browser
liest JSON etwa doppelt so schnell wie gleichwertigen Quelltext (gemessen 64
statt 137 ms für 6 MB — auf dem Telefon entsprechend mehr). Der Service Worker
gibt dem Netz 2,5 Sekunden; danach zeigt er den gespeicherten Stand und lädt im
Hintergrund weiter, statt am leeren Bildschirm zu warten. Ortsverzeichnis und
Postleitzahlen werden auf drei Nachkommastellen gekürzt — 110 Meter genügen für
einen Wohnort, den ein Umkreisfilter in Kilometern auswertet.

Dazu: zehn Sprachen ([i18n.js](site/i18n.js), 190 Schlüssel), Hilfetexte an
jedem Regler, Installation als App mit Offline-Betrieb, Rückmeldung per
`mailto` und eine Zugriffszählung, die nur startet, wenn in
[config.js](site/config.js) eine GoatCounter-Kennung steht **und** die Seite
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
`/daten/`: `festivals.json`, `festivals.csv`, `lineups.csv`, `bands.csv` und
die Kontrolltabelle `uebersicht.html`.

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
dem Anfang, steckt jede Koordinate in Europa, zählt das Lineup richtig, ist die
Besucherzahl eine Zahl, blieb eine Dublette übrig? Jeder dieser Punkte war
schon einmal falsch — zehn Koordinaten in Mexiko und Buenos Aires, ein Jahrgang
2027 mit Termin im August 2026, eine Besucherzahl „2.000", eine doppelte
Nachtwacht. Was die Prüfung findet, steht am Ende des Laufs im Protokoll.

## Was fehlt und warum

Feld für Feld gegen die zwischengespeicherten Quellseiten geprüft — bei jedem
fehlenden Wert wurde die Seite nach einem Beleg durchsucht:

| Feld | fehlt | steht doch auf der Seite |
|---|---:|---|
| Besucherzahl | 2.925 | 0 |
| Lineup | 2.750 | — die Quelle führt keins |
| Postleitzahl | 1.922 | 0 |
| Preis | 1.880 | 2 |
| Genre | 1.827 | 0 |
| Spielstätte | 940 | 129-mal nur der Festivalname selbst |
| Webseite | 360 | 0 — verlinkt sind nur Bildnachweise und Werbung |
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

## Bekannte Grenzen

- festivalticker zeigt für vergangene Jahrgänge nur je 40 Einträge; mehr gibt
  die Seite nicht her.
- 292 Einträge haben kein Datum: Die Quellen führen sie ohne bestätigte
  Neuauflage. Das Feld `Hinweis` nennt dann die letzte gefundene Ausgabe.
- Zwei festivalticker-Seiten reihen Bandnamen ohne jeden Trenner aneinander
  (`Quincy Goldie 333 I Fire Schnuppe …`). Sie bleiben ohne Lineup: Eine
  Aufteilung nach Leerzeichen würde raten und aus „Nebula Allstars" die Band
  „Nebula" machen. Erfundene Bandnamen wären schlimmer als fehlende.
- Bei reinen Akronymen kann die Mehrheitsregel danebengreifen (`GANS` → `Gans`).
- Die Geokodierung ist auf europäische Länder begrenzt. Ohne diese Grenze
  liefert Nominatim bei mehrdeutigen Namen den weltweit bekanntesten Ort —
  „Newark" wurde New Jersey statt England.
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
