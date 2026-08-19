# Festival-Übersicht Europa

Acht Festivalverzeichnisse, zu einem Bestand zusammengeführt: **5.737 Festivals**
in **42 Ländern** mit **40.511 Acts**, davon 1.568 Festivals aus mehr als einer
Quelle. Dazu eine statische Webseite, die nach Band oder Genre filtert, und ein
Datenlauf, der sich täglich selbst aktualisiert.

Was sich wann geändert hat, steht in der
[Änderungshistorie](https://github.com/Waldsprenger/festival-finder/commits/main);
die Fußzeile der Webseite verlinkt sie ebenfalls.

**Wegweiser**

| Wenn du wissen willst … | Abschnitt |
|---|---|
| woraus die Daten kommen | [Quellenerfassung](#quellenerfassung), [Die acht Quellen im Vergleich](#die-acht-quellen-im-vergleich) |
| wie doppelte Einträge verschwinden | [Zusammenführen](#zusammenführen) |
| was in den Quellen fehlt und warum | [Was in den Quellen wirklich fehlt](#was-in-den-quellen-wirklich-fehlt), [Bekannte Grenzen](#bekannte-grenzen) |
| wie die Seite gebaut und veröffentlicht wird | [Neu erzeugen](#neu-erzeugen), [Webseite](#webseite-site), [Veröffentlichen und täglich aktualisieren](#veröffentlichen-und-täglich-aktualisieren) |

## Aufbau

`scraper/gemeinsam.py` hält Pfade, Browserkennung und das Länderwissen — das lag
vorher in drei Modulen nebeneinander. Die übrigen Skripte sind eigenständig
ausführbar und bauen aufeinander auf:

```
festival_scraper.py  →  data/festivals.json + CSV-Ausgaben
genres.py            →  Genre-Oberbegriffe (Modul, von build_site.py genutzt)
pruefe_offiziell.py  →  Stichprobe gegen die offiziellen Festivalseiten
geocode.py           →  data/geo.json          (Ortskoordinaten)
build_gazetteer.py   →  data/gazetteer.json + plz.json
build_map.py         →  data/welt_grob.json + welt_fein.json
fetch_fonts.py       →  site/fonts.css
build_site.py        →  site/data.js
build_pwa.py         →  site/manifest.webmanifest + sw.js + icons/
build_overview.py    →  data/uebersicht.html
build_artifact.py    →  site/artifact.html      (alles in einer Datei)
daily_update.py      →  führt die Kette aus
```

## Quellenerfassung

Der Scraper enumeriert die Seiten vollständig statt einzelne Listen abzuklappern:

| Quelle | Weg | Seiten |
|---|---|---|
| festivalsunited.com | `sitemap.xml` je Jahrgang **und** die 35 europäischen Länderseiten | 3.226 |
| festapp.io | Sitemaps der Festivals und der einzelnen Ausgaben | 2.973 |
| festivalfinder.eu | Trefferliste der European Festivals Association, geblättert über `/p2`, `/p3` … | 2.071 |
| wannafest.com | `sitemaps/festivals-1.xml` | 2.093 |
| festivalticker.de | alle Listenseiten: Jahres-, Monats-, Länder- und Statusarchive plus „Umsonst und draußen" | 1.971 |
| festival-alarm.com | Jahresseiten `/Festivals-JAHR` **und** die Regionsseiten je Land und Jahr | 935 |
| festivalhopper.de | `sitemap-festivals.xml`, Jahrgang steht in der Adresse | 728 |
| festivalflyer.com | die Startseite, mehr ist nicht erreichbar | 12 |

Die fünf zuletzt genannten kamen später dazu. Was sie beitragen, steht weiter
unten unter „Die acht Quellen im Vergleich".

Die zweiten Wege sind nicht geraten, sondern nachgemessen: Über die
Länderseiten von festivalsunited sind 30 Detailseiten erreichbar, die in der
Sitemap fehlen — darunter das Exit Festival in Novi Sad. Die Regionsseiten von
festival-alarm bringen vier weitere, die Umsonst-Liste von festivalticker eine.
Nicht erfasst werden die 5.000 Konzertseiten unter `sitemap-events`: Das sind
Einzelkonzerte, keine Festivals. Eine Sitemap haben festivalsunited, festapp,
wannafest und festivalhopper; bei festivalticker und festival-alarm antwortet
`/sitemap.xml` mit 404, dort führen nur die Listenseiten zum Ziel.

Die Jahresliste wächst automatisch mit: Die Obergrenze ist das laufende Jahr
plus fünf, künftige Jahrgänge wie 2028 werden also ohne Codeänderung erfasst.
Fehlende Zukunftsjahrgänge melden die Quellen mit 404, das gilt nicht als Fehler.

`--since JAHR` steuert die Tiefe; voreingestellt ist das laufende Jahr. Ein
kompletter Durchlauf über alle Jahrgänge geht mit `--since 2006`, erzeugt aber
über 23.000 Abrufe und eine Datei, die für die Veröffentlichung zu groß wird.
Vergangene Jahrgänge werden von der Webseite ohnehin herausgefiltert.

Zwei Grenzen der Quellen: festivalticker zeigt für vergangene Jahre nur je 40
Einträge, mehr gibt die Seite nicht her. Und festival-alarm führt bei den
meisten Festivals kein Lineup („keine Daten") — es liefert vor allem zusätzliche
Termine, Preise und Orte. Außereuropäische Einträge werden verworfen — und zwar an zwei Stellen, die
beide nötig sind: Die Prüfung erkennt jedes gültige Länderkürzel, das nicht zu
Europa gehört (die frühere Namensliste kannte „usa“, aber nicht IN, CL, PY, CO,
ZA, ID, KR, KZ, CR, CN oder TH), und der festivalsunited-Leser holt das Land
notfalls aus der eingebetteten Adresse oder dem Länderlink der Seite. Ohne das
zweite stand etwa das Suwannee Hulaween aus Florida ganz ohne Land in der Datei
und blieb damit drin. Zusammen fielen 67 Einträge weg; seither trägt jedes
Festival ein Land, vorher waren 834 ohne.

## Die acht Quellen im Vergleich

Jede Quelle bringt Eigenes mit — der Wert steckt nicht in der Zahl der Seiten,
sondern darin, wie viele Festivals **nur** dort stehen:

| Quelle | Einträge | nur dort | Besonderheit |
|---|---|---|---|
| festivalsunited | 2.770 | 1.523 | Lineups, Preise, Datenblatt je Seite |
| festivalticker | 1.966 | 807 | dichteste Abdeckung für Deutschland |
| wannafest | 1.061 | 805 | Elektronisches, Niederlande und Belgien |
| festival-alarm | 921 | 211 | Spielstätte, Besucherzahl, Preise |
| festapp | 739 | 375 | Frankreich, Italien, Spanien |
| festivalhopper | 683 | 76 | Lineups als Einzelverweise, Kapazität |
| festivalfinder | 400 | 372 | Klassik, Theater, Osteuropa |
| festivalflyer | 1 | 0 | Großbritannien, nur was die Startseite zeigt |

**wannafest wird gefiltert.** Die Seite führt weit überwiegend Clubabende: In
einer Stichprobe von 400 Einträgen waren 359 als „Indoor" ausgewiesen, darunter
Sachen wie „Bootshaus DJ Contest". Ungefiltert hätten rund 1.800 Clubnächte die
Festivalliste geflutet. Übernommen wird deshalb nur, was sich als Festival zu
erkennen gibt: am Namen oder daran, dass es draußen stattfindet.

**Nicht erfasste Seiten.** Fünf der vorgeschlagenen Verzeichnisse liefern keine
Daten:

| Seite | Grund |
|---|---|
| festicket.com | die `robots.txt` untersagt ClaudeBot ausdrücklich das Sammeln; zusätzlich Cloudflare-Sperre |
| de.concerty.com | Cloudflare-Sperre, selbst die `robots.txt` antwortet mit 403 |
| musicfestivalwizard.com | dieselbe Cloudflare-Sperre |
| bachtrack.com | Festivalliste wird im Browser zusammengesetzt; die Sitemap führt Kritiken und Einzelkonzerte der Klassik |
| festivalnetworks.com, musicfestadvisor.com, festivalcalendars.com | Listenartikel statt Datenbank, keine auslesbaren Detailseiten |

Die drei gesperrten Seiten werden nicht umgangen. Ein Cloudflare-Schutz ist eine
bewusste Entscheidung des Betreibers, und festicket benennt ClaudeBot sogar
namentlich — daran hält sich der Scraper.

**Bandverweise gegen Menüpunkte.** Bei festivalhopper stehen die Bands als
einzelne Verweise auf der Seite — das Menü aber auch: „Bands", „Bands A-Z",
„Bands Genres", „Bands Länder" und „Headliner" führten als Acts in 683 Lineups.
Die Bandkarten liegen unter `/bands/karten/`, die Menüpunkte unter kürzeren
`/bands/`-Adressen; danach unterscheidet der Scraper.

## Das Datenblatt der Quellseiten

festivalsunited legt jeder Detailseite ein maschinenlesbares Datenblatt bei
(JSON-LD nach schema.org). Der Scraper liest es als **zweite** Quelle: Der
Fließtext beschreibt die dargestellte Ausgabe und hat Vorrang, das Datenblatt
füllt, was dort fehlt. Es liefert Land, Ort und Postleitzahl, die Spielstätte,
Koordinaten, den Einstiegspreis, den Absagestatus und in Einzelfällen den
Termin.

Dazu kommt der Kopfblock der Seite, der als Fließtext nichts hergibt: Er nennt
die Stile ausdrücklich („Multi-Genre: Rock, Metal, Punk UVM") und die Kapazität
(„ca. 18.000"), während der Beschreibungssatz nur „genreübergreifendes
Festival" sagt. Beim Reload Festival 2027 stand deshalb die Sammelkategorie, wo
die Seite Rock, Metal und Punk aufführt.

Der Gewinn war beträchtlich: Bei den damals 4.269 Festivals fehlte die
Spielstätte zuvor 2.438-mal, danach nur noch 683-mal; ohne Genreangabe waren
797 Einträge, danach 322; ohne Besucherzahl 2.988, danach 1.585.
Postleitzahlen kamen so oft dazu, dass die Zahl der über die
Postleitzahl verorteten Festivals von 1.894 auf 2.923 stieg — das ist der
genauere Weg, weil eine Postleitzahl den Zustellbereich trifft, während ein
Ortsname erst gefunden werden muss und in den Quellen auch mal „Madgeburg"
heißt.

**Koordinaten nur nach Prüfung.** Für 2.476 Festivals nennt das Datenblatt
einen Punkt, und meist sitzt er genau — der Abstand zur bisher errechneten
Koordinate liegt im Mittel bei 2,1 km. Bei 37 Einträgen liegt er dagegen im
falschen Land: Lugano landete in Buenos Aires, Basel und Budapest in Berlin,
Andorra in Mexiko. Dreizehnmal steht 51,5/10,5 — der Mittelpunkt Deutschlands
als Platzhalter, verteilt über Deutschland und die Schweiz. `build_site.py`
übernimmt einen Punkt deshalb nur, wenn er im Rahmen des Landes liegt
(Landesgrenzen aus dem Ortsverzeichnis, ein Grad Toleranz) und nicht als
Platzhalter auffällt — erkennbar daran, dass dieselbe Koordinate für drei
oder mehr verschiedene Orte herhalten muss. Und er greift erst, wenn
Postleitzahl und Ortsname nichts hergeben.

## Abgleich mit den offiziellen Seiten

```bash
python scraper/pruefe_offiziell.py 40          # Zufallsstichprobe
python scraper/pruefe_offiziell.py --name Wacken
```

Das Werkzeug holt die Festivalseite selbst und vergleicht den Starttermin.
Belastbar ist dabei nur deren eigenes Datenblatt; bloße Datumsangaben im
Fließtext gehören genauso oft zu Nachrichten oder Nebenveranstaltungen.
Verglichen wird außerdem nur derselbe Jahrgang — die offizielle Seite zeigt
die nächste Ausgabe, unser Bestand führt jede einzeln.

Was eine Stichprobe von 60 Festivals ergab: **34 Seiten nennen überhaupt kein
Datum** in lesbarer Form (es steckt in Grafiken oder wird per Skript
nachgeladen), 15 nur im Fließtext, und lediglich **6 führen ein Datenblatt**.
Davon bestätigten vier unseren Termin; die zwei Abweichungen lösten sich beim
Nachsehen auf — die Seiten zeigten bereits die nächste Ausgabe, die wir als
eigenen Eintrag ebenfalls führen, mit übereinstimmendem Datum.

Ein zweiter, größerer Lauf über 120 Festivals bestätigte das Bild: 83 Seiten
nennen kein Datum des Jahrgangs, 8 waren nicht erreichbar, 7 bestätigten
unseren Termin maschinenlesbar — und **kein einziges Datenblatt widersprach**.
Die 18 Fälle, in denen nur der Fließtext abweicht, sind überwiegend
Nebenwirkungen der Suche: Auf Veranstalterseiten stehen Vorverkaufsstarts,
Nachrichten und Termine anderer Jahrgänge im selben Text. Ebenfalls geprüft:
Von 60 Festivals ohne Preis nannten nur zwei offizielle Seiten einen Preis in
maschinenlesbarer Form.

Daraus folgt: Ein automatischer Abgleich taugt **nicht** als Datenquelle, weil
neun von zehn Veranstalterseiten nichts Maschinenlesbares anbieten. Hinzu
kommt, dass die Datumsangaben dort oft gar nicht das Festival selbst meinen,
sondern Vorverkaufsstarts, Nebenveranstaltungen oder Nachrichten. **Bei einer
Abweichung gilt deshalb der Bestand, nicht die Veranstalterseite** — das Skript
liegt als Stichprobe zur Kontrolle bei, seine Meldungen sind Hinweise zum
Nachsehen und keine Korrekturen.

## Neu erzeugen

```bash
python scraper/festival_scraper.py && python scraper/build_overview.py
```

Alle Seiten liegen unter `cache/` — ein erneuter Lauf ist dadurch in gut vier
Minuten durch, ohne die Quellseiten nochmals abzurufen. Für frische Daten
`--frisch` setzen oder `cache/` löschen (Erstlauf rund 25 Minuten für 11.300
Detailseiten, 4 parallele Verbindungen).

## Dateien in `data/`

| Datei | Inhalt |
|---|---|
| `uebersicht.html` | Durchsuchbare Tabelle, Filter „nur mit Lineup" / „nur Doppeltreffer" |
| `festivals.csv` | Ein Festival je Zeile inkl. vollständigem Lineup |
| `lineups.csv` | Eine Zeile je Band-Festival-Paar (für Pivot-Auswertungen) |
| `bands.csv` | Acts nach Anzahl Festivals — zeigt Mehrfachbuchungen |
| `festivals.json` | Rohdaten inkl. Quell-URLs je Eintrag |
| `band_normalisierung.json` | Welche Schreibweisen zu welchem Namen vereinheitlicht wurden |

## Webseite (`site/`)

```bash
python scraper/geocode.py         # Festivalkoordinaten -> data/geo.json (einmalig, ~35 min)
python scraper/build_gazetteer.py # Ortsverzeichnis aus GeoNames (einmalig)
python scraper/fetch_fonts.py     # Display-Schrift als data-URI (einmalig)
python scraper/build_site.py      # erzeugt site/data.js
python scraper/build_artifact.py  # erzeugt site/artifact.html (Einzeldatei)
```

Täglicher Sammellauf für alle Schritte:

```bash
python scraper/daily_update.py            # nur Veraltetes nachladen
python scraper/daily_update.py --frisch   # jede Seite neu holen
```

Danach `site/index.html` im Browser öffnen — die Seite läuft ohne Server. Weil
Browser bei `file://` kein `fetch()` auf lokale Dateien erlauben, liegen die Daten
als `data.js` vor und nicht als JSON. Alternativ lokal ausliefern:

```bash
python -m http.server 8765 --directory site
```

**Wohnort:** Die Postleitzahl ist der verlässliche Weg — Ortsnamen sind mehrdeutig,
„Seeheim" gibt es in Südhessen und in Oberbayern. Erkannt werden `97209`,
`97209 Veitshöchheim` und `1010 AT` (zur Trennung gleicher Codes in AT und CH),
ebenso weiterhin reine Ortsnamen. Bei mehrdeutigen Namen weist die Seite darauf hin.

**Kalendergrenze:** Früher als der Monatsanfang des zeitlich ersten Festivals im
Datenbestand lässt sich nichts einstellen — startet das früheste am 24.06.2025,
ist der 01.06.2025 die Untergrenze. Getippte Daten davor werden zurückgezogen.

**Reglergrenzen** stammen aus den Daten und werden bei jedem Build neu berechnet:
der Umkreis reicht bis zum entferntesten Festival ab `REF_PLZ` in `build_site.py`
(derzeit 97209 → 3.300 km), der Preis bis zum teuersten gefundenen Ticket
(derzeit 1.600 €), jeweils aufgerundet.

**Abgesagte Ausgaben** erkennt der Scraper an der durchgestrichenen Überschrift und
dem Hinweis „wurde abgesagt" (festivalticker) beziehungsweise am Status im Kopfbereich
und dem Klartext „&lt;Name&gt; wurde abgesagt" (festivalsunited). Wichtig ist die enge
Fassung: Bei festivalsunited steht „Abgesagt" auf 416 Seiten als Hinweis auf *andere*
Jahrgänge in der Ausgabenliste — gewertet wird nur die dargestellte Ausgabe. Derzeit
sind 72 Festivals betroffen; sie bleiben in der Webseite ausgeblendet, lassen sich per
Haken einblenden und erscheinen dann durchgestrichen mit rotem Vermerk.

**Ablauf:** Wohnort → Umkreis → Ticketobergrenze → frühester Starttermin; danach
entweder Bands oder Genre. Bei Bands: suchen, auswählen, optional pro Band auf `×2`
stellen — die Trefferquote ist die gewichtete Summe der gefundenen Bands geteilt durch
die Summe aller gewählten Gewichte. Bei Genre: Oberbegriffe anklicken — die Trefferquote
ist die Zahl der abgedeckten geteilt durch die Zahl der gewählten Oberbegriffe.

**Sortierung** steht über der Trefferliste und richtet sich nach dem Filter: Mit
Bandauswahl zählt zuerst die Übereinstimmung, mit Genreauswahl der Termin — ein
Oberbegriff trifft auf Hunderte Festivals zu, da ordnet die Prozentzahl kaum noch.
Ohne beide Filter entscheidet die Entfernung. Wählbar sind daneben Entfernung,
Preis und Datum; bei Bands zusätzlich die Übereinstimmung. Jede Filterart merkt
sich ihre eigene Wahl, ein Wechsel wirft sie also nicht weg. Gleichstand löst die
jeweils nächste Größe auf, und Festivals ohne Angabe — kein Preis, kein Termin,
kein Ort — stehen immer am Ende, weil ein fehlender Preis nicht der günstigste ist.

**Am Telefon zuerst.** Die Seite wird vor allem am Handy benutzt, deshalb sind
Tippziele auf mindestens 44 Pixel gebracht (Fragezeichen behalten ihre kleine
Darstellung, bekommen die Fläche aber unsichtbar dazu), alle Eingabefelder
tragen 16 Pixel Schrift — darunter zoomt iOS beim Antippen ungefragt die ganze
Seite —, und Ränder wie Kopfbereich sind schmaler. Die Karte ist im Hochformat
fast quadratisch statt ein 16:7-Streifen und lässt sich mit zwei Fingern zoomen
und verschieben; ein Finger bleibt fürs Weiterscrollen frei, ein Tipp wählt den
nächsten Pin. Der Hinweis unter der Karte nennt je nach Gerät Mausrad oder
Finger.

**Trefferliste in Stapeln:** Alle 300 Karten auf einmal ergaben am Telefon eine
Seite von 109.000 Pixeln Höhe. Gezeichnet werden jetzt 25 (am Rechner 50), der
Rest kommt per Knopf nach — das kürzt die Aufbauzeit auf ein Viertel. Ein Klick
auf einen Kartenpin holt den zugehörigen Eintrag selbst nach vorn, auch wenn er
noch im Nachschub steckt.

**Bands oder Genre, nicht beides.** Der Umschalter über der Auswahl hat drei Stellungen
(*Nach Bands*, *Nach Genre*, *Ohne beides*); es wirkt immer nur die aktive. Beide
Auswahlen bleiben beim Umschalten erhalten, damit ein Vergleich nichts kostet.

**Genre-Oberbegriffe:** Die Quellen schreiben das Genre als Freitext — rund 17.400
Angaben in 1.584 Schreibweisen, von „Rock“ bis „Psychedelic Minimal Techno“. Danach
filtert niemand, deshalb bildet [scraper/genres.py](scraper/genres.py) sie auf 17
Oberbegriffe ab (Rock, Metal, Punk & Hardcore, Pop, Hip-Hop & Rap, Elektro/Techno & Dance,
Reggae/Ska, Jazz/Blues, Soul/Funk, Folk/Country, Weltmusik, Klassik, Schlager/Volksmusik,
Gothic/Wave, Mittelalter, Kultur & Bühne, Genreübergreifend). Eine Angabe darf mehrere
Oberbegriffe ergeben: „Ska Punk“ zählt zu Punk *und* zu Reggae/Ska, sonst fände es nur die
Hälfte der Suchenden. Vor der Stichwortsuche steht eine Liste von Sonderfällen, in denen
ein Wort in die Irre führt — „Hardcore Techno“ ist kein Punk, „Classic Rock“ keine Klassik.
Zugeordnet sind 4.060 der 5.969 Festivals; für 1.906 nennt keine Quelle eine Richtung, sie
lassen sich per Haken einblenden. Nicht zugeordnet bleiben 0,4 % der Angaben, fast nur
Tippfehler und Einzelstücke wie `Zapparesk`. Die Abdeckung prüft

```bash
python scraper/genres.py
```

**Genreübergreifend ist der Rückfall, keine Sammelkiste.** Der Oberbegriff greift nur,
solange keine Richtung erkennbar ist; sobald eine dazukommt, fällt er weg. Das hängt an
zwei Stellen zusammen: Erstens sammelt der Scraper die Genres inzwischen aus *allen*
Quellen (`genre_merge`), statt die erste gefüllte Angabe gewinnen zu lassen — bei „Rock im
Park“ stand vorher nur das festivalsunited-Wort „genreübergreifendes“, während
festival-alarm acht konkrete Richtungen nennt. Zweitens verdrängt jede konkrete Zuordnung
den Sammelbegriff. Zusammen sank die Kategorie von 719 auf 459 Festivals; bei diesen sagen
tatsächlich alle Quellen nur „genreübergreifendes“ oder „Gemischt“. Nicht als Genre zählt
außerdem der Veranstalterhinweis „Angebot von …“, den festivalsunited im selben Satzmuster
führt wie die Stilangabe.

Preise werden für Filter und Sortierung in Euro umgerechnet (Näherungskurse in
`build_site.py`), angezeigt wird zusätzlich der Originaltext der Quelle.

**Zwei Ausgabeformen.** `site/index.html` ist die lokale Fassung mit getrennten
Dateien. `site/artifact.html` bündelt Schrift, CSS, Daten, Skript und beide
Rechtstexte in einer einzigen Datei — nötig für die Veröffentlichung über
claude.ai, wo externe Dateien und fremde Server per Sicherheitsrichtlinie
blockiert sind. Deshalb löst die Wohnortsuche primär über das mitgelieferte
GeoNames-Verzeichnis auf (85.098 Orte, DE/AT/CH vollständig, übriges Europa ab
15.000 Einwohnern); Nominatim wird nur in der lokalen Fassung und nur als
Rückfall angefragt.

## Sprachen

Die Oberfläche gibt es auf Deutsch, Englisch, Französisch, Spanisch,
Italienisch, Niederländisch, Polnisch, Portugiesisch, Russisch und Türkisch.
Alle Texte stehen in
[site/i18n.js](site/i18n.js); die Seite wählt beim ersten Besuch die
Browsersprache und merkt sich eine spätere Auswahl lokal.

Eine Sprache ergänzen: Kürzel in `SPRACHEN` eintragen und in jedem Eintrag von
`TEXTE` eine Zeile hinzufügen. Fehlt eine Übersetzung, greift Deutsch — die
Seite bleibt also auch bei unvollständiger Sprachdatei benutzbar.

Impressum und Datenschutzerklärung bleiben bewusst auf Deutsch: Es sind
rechtsverbindliche Texte, bei denen eine ungenaue Übersetzung schlechter wäre
als keine. In den anderen Sprachen weist die Fußzeile darauf hin.

## Als App auf dem Startbildschirm

`scraper/build_pwa.py` erzeugt Manifest, App-Symbole und einen Service Worker.
Damit lässt sich die Seite unter Android und iOS installieren; sie startet dann
ohne Browserleiste und funktioniert offline, weil die Festivaldaten lokal liegen.

Wirksam wird das **nur bei eigener Auslieferung über HTTPS**, also in der
GitHub-Pages-Fassung — ein Service Worker verlangt eine eigene sichere Adresse.
In der eingebetteten claude.ai-Fassung bleibt die Registrierung wirkungslos;
`app.js` prüft das und tut dort nichts.

Der Service Worker holt immer zuerst aus dem Netz und fällt erst ohne
Verbindung auf den Speicher zurück. Neue Festivaldaten kommen also an, sobald
Netz da ist. Seine Version leitet sich vom Datenstand ab, damit nach jedem
Tageslauf der alte Speicher verworfen wird.

## Zugriffszählung (freiwillig)

Eine statische Seite kann sich nicht selbst zählen. `site/config.js` hält deshalb
eine Kennung für [GoatCounter](https://www.goatcounter.com) bereit — den Teil vor
`.goatcounter.com`. Leer heißt: keine Zählung, kein fremder Server, kein Hinweis
im Seitenfuß. Das ist der Auslieferungszustand.

Gezählt wird nur, wo es auch wirklich funktioniert: eigene Auslieferung über HTTPS,
nicht eingebettet, nicht auf `localhost`. In der claude.ai-Fassung sperrt die
Sicherheitsrichtlinie den Aufruf ohnehin, deshalb erscheint dort auch der
Datenschutzhinweis nicht. GoatCounter setzt keine Cookies und rührt den
Gerätespeicher nicht an.

**Der Stand bleibt privat.** Die Zahlen stehen ausschließlich im GoatCounter-Konto
hinter der Anmeldung; die Seite zeigt sie nirgends an, auch nicht über eine
besondere Adresse. Eine Anzeige auf der Seite würde verlangen, die Statistik bei
GoatCounter öffentlich zu schalten — deshalb gibt es sie nicht, und die
öffentliche Statistik bleibt aus.

## Veröffentlichen und täglich aktualisieren

Die Seite ist statisch, deshalb ist **GitHub Pages + GitHub Actions** der passende
Weg: Actions führt den Datenlauf auf GitHub-Servern aus, Pages liefert das Ergebnis
unter fester Adresse aus. Der eigene Rechner muss dafür nie laufen.

Einmalige Einrichtung:

```bash
git init -b main
git add -A
git commit -m "Festival Finder"
git remote add origin https://github.com/<dein-konto>/festival-finder.git
git push -u origin main
```

Danach im Repository unter **Settings → Pages → Source** den Eintrag
*GitHub Actions* wählen. Der Workflow [.github/workflows/update.yml](.github/workflows/update.yml)
hält Seiten- und Geo-Cache über Läufe hinweg und kennt zwei Zeitpläne:

| Wann | Was |
|---|---|
| Mo–Sa 03:17 UTC | nur Seiten neu holen, deren Zwischenspeicher älter als 24 Stunden ist |
| So 02:17 UTC | `--frisch`: **jede** Seite neu abrufen und verwaisten Cache löschen |

Der wöchentliche Komplettabruf ist nötig, weil die Quellen still korrigieren:
Ein verschobener Termin oder ein nachgetragener Act käme sonst erst an, wenn
die Seite ohnehin wieder abgerufen wird. Anschließend fallen Cachedateien weg,
die seit einer Woche niemand angefasst hat — sie gehören zu Festivals, die es
in den Quellen nicht mehr gibt. Die Wochenfrist ist Absicht: Eine Seite, die
an diesem Tag nicht antwortet, behält ihren alten Stand und fällt nicht gleich
heraus.

Von Hand startbar ist beides unter *Actions*; dort schaltet das Feld
*Alles neu abrufen* den frischen Lauf ein.

Warum nicht Streamlit: Streamlit Community Cloud ist für Python-Apps mit
Serverprozess gedacht. Diese Seite ist reines HTML/JS, bräuchte also einen
kompletten Umbau, liefe danach langsamer (Server-Roundtrip pro Klick) und
schläft auf dem kostenlosen Tarif nach Inaktivität ein. Pages hat keine
Schlafphase, keine Laufzeitkosten und die Aktualisierung ist ohnehin ein
Cron-Job, kein Serverdienst.

## Zusammenführen

**Festivals** werden in sechs Stufen zusammengeführt: exakt über Name + Jahr + Stadt,
dann über eindeutige Quellenpaare zu Name + Jahr, dann über gleiche Stadt +
gleichen Starttermin + gemeinsamen Namensbestandteil bei verschiedenen Quellen.
Die dritte Stufe fängt Fälle wie „Kosmos Festival" gegen „Kosmos Festival Chemnitz"
ab. Der Starttermin ist dabei der entscheidende Schutz: „Winter Wutzrock" im Februar
und „Wutzrock" im August teilen Stadt und Namensteil, sind aber zwei Veranstaltungen.

Die vierte Stufe greift, wenn die Quellen denselben Termin **verschieden datieren**:
Das Neuborn Open Air steht bei festivalticker ab dem 27.08., bei den beiden anderen
Quellen ab dem 28.08. — übrig blieben zwei Einträge, einer mit 17 und einer mit
4 Bands. Statt des Starttermins genügt hier ein Überlapp der Zeiträume; den Schutz
übernimmt ein strengerer Namensvergleich: Ein Name muss vollständig im anderen
stecken („Neuborn" in „NOAF Neuborn") oder beide ohne Leerzeichen gleich sein
(„R.O.I. Rock On Isens" und „ROI Rock On Isens"). Ein gemeinsames Wort allein reicht
nicht, sonst verschmölzen „METAStadt Open Air Wien" und „Afrika Tage Wien" über die
Stadt im Namen. Beim Verbinden gelten der früheste Beginn und das späteste Ende, weil
die Quellen unterschiedliche Teile derselben Veranstaltung beschreiben.

Der Ort dieser Stufe ist nicht nur die Gemeinde, sondern auch die **Spielstätte**:
Beim „Kein Bock auf Nazis Festival" nennt festivalhopper die Burg Lichtenberg als
Ort, die drei anderen Quellen die Gemeinde Thallichtenberg — zusammen mit dem um
einen Tag versetzten Termin fanden sich die Einträge sonst nie.

Die fünfte Stufe fängt **abweichende Schreibweisen** desselben Namens ab
(„Sonne Mond Sterne" gegen „SonneMondSterne", „Elb Riot" gegen „Elbriot"). Verlangt
werden derselbe Ort, ein überlappender Zeitraum, getrennte Quellen und eine
Ähnlichkeit von 82 % über den zusammengezogenen Namen; unter sechs Zeichen greift
die Regel gar nicht, sonst zöge sie Kurznamen zusammen.

Die sechste Stufe verbindet Einträge, zu denen eine Quelle **noch keinen Termin**
kennt. Solche Einträge haben kein Jahr und können deshalb nicht nach Jahrgang
gruppiert werden — gesucht wird über den zusammengezogenen Namen, und stehen
mehrere Jahrgänge zur Wahl, gewinnt der früheste Termin. Die terminlose Seite trägt
im Ortsfeld häufig die Spielstätte („Festung Rosenberg" statt Kronach), deshalb wird
auch gegen die Spielstätte des datierten Eintrags verglichen. Die Quellen dürfen sich
hier überschneiden: Eine terminlose Seite ist die Übersichtsseite des Festivals, kein
zweites Fest am selben Ort. Bleiben mehrere terminlose Einträge desselben Festivals
übrig, werden auch sie zusammengelegt.

Die erste Stufe im Detail: Der Name wird dafür
normalisiert (Umlaute, Artikel, Jahreszahl und die Wörter „Festival/Open Air" fallen weg).
Die Stadt gehört bewusst zum Schlüssel: Tour-Formate wie das *Irish Spring Festival*
laufen unter einem Namen an 30 Orten und sind eigenständige Termine. In einem zweiten
Schritt werden Einträge quellenübergreifend verbunden, wenn es zu Name + Jahr in jeder
Quelle genau einen Kandidaten gibt — so greift der Abgleich auch bei abweichender
Ortsschreibweise, ohne Tourtermine zu verschmelzen.

Der Namensschlüssel entfernt „Festival", „Fest" und „Open Air" auch dann, wenn
sie **angehängt** sind: festivalticker führt das Reload Festival als
„Reloadfestival", festivalsunited getrennt — ohne diese Regel standen beide
nebeneinander, einer davon ohne Koordinaten. Der Rumpf muss dabei vier Zeichen
behalten, sonst würde aus „Festa" ein leerer Schlüssel. Bei sonst gleicher
Schreibung gewinnt für die Anzeige die getrennte Variante.

**Bandnamen** laufen durch denselben Normalisierer (Groß-/Kleinschreibung, Akzente,
`&`/`and`, führendes „The", Satzzeichen). Je Gruppe gewinnt die häufigste Schreibweise
und ersetzt alle übrigen.

**Kürzel** stehen in `data/band_aliase.json` (TBS → The Butcher Sisters, ADTR → A Day
to Remember, SOAD → System of a Down …). Sie wirken an zwei Stellen: Beim Einlesen
bekommt das Kürzel denselben Schlüssel wie der ausgeschriebene Name, sodass beide
Schreibweisen zu einem Act verschmelzen; im Suchfeld der Seite findet zusätzlich jedes
Kürzel seine Band, und der Treffer weist das Kürzel aus („auch TBS").

Ein Kürzel kann aber selbst ein Bandname sein. Entscheidend ist deshalb nicht, ob es
im Programm vorkommt, sondern ob Kürzel und ausgeschriebener Name je **auf demselben
Festival** stehen: „TBS" und „The Butcher Sisters" teilen sich drei Plakate, das ist
dieselbe Band. „LP" und Linkin Park teilen sich kein einziges — das ist die Sängerin
LP, und für sie bleibt das Kürzel in den Daten unangetastet; die Suche zeigt dann
beide. Geprüft wird je Festival, nicht je Quellseite: Die beiden Schreibweisen stehen
oft auf den Seiten verschiedener Quellen und treffen sich erst beim Zusammenführen.

## Was in den Quellen wirklich fehlt

Feld für Feld gegen die zwischengespeicherten Quellseiten geprüft: Bei jedem
fehlenden Wert wurde die Seite nach einem Beleg durchsucht. Die Spalte „fehlt"
nennt den heutigen Bestand von 5.737 Festivals, die Spalte daneben das Ergebnis
der Nachsuche.

| Feld | fehlt | steht doch auf der Seite |
|---|---|---|
| Besucherzahl | 2.921 | 0 |
| Lineup | 2.748 | — die Quelle führt keins |
| Postleitzahl | 1.920 | 0 |
| Preis | 1.880 | 2 |
| Genre | 1.824 | 0 |
| Spielstätte | 944 | 129-mal nur der Festivalname selbst |
| Webseite | 360 | 0 — die Seiten verlinken nur Bildnachweise und Werbung |
| Termin | 291 | nur Termine *vergangener* Ausgaben |
| Ort | 247 | 16 |
| Land | 0 | — |

Die Nachsuche selbst lief auf dem damaligen Stand mit drei Quellen (4.269
Festivals); an ihrem Ergebnis ändert der Zuwachs nichts, denn sie fragt, ob ein
Wert auf der Quellseite steht und nur nicht gelesen wurde. Die fünf neuen
Verzeichnisse sind schlanker als die ersten drei: festivalfinder nennt weder
Preis noch Lineup, wannafest keine Postleitzahl.

Zwei Zahlen sind gegenüber der ersten Prüfung gefallen, weil zwei Auslesefehler
gefunden wurden: Das Preismuster bei festivalsunited kannte `EUR` und `CHF`,
aber nicht das Eurozeichen — dabei schreibt die Seite überwiegend „ab € 85,00".
Und das Feld „Örtlichkeit" bei festival-alarm wurde nie gelesen, obwohl es die
Spielstätte nennt (Arena Wien, Waschhaus Potsdam).

Die Quellen sind damit ausgeschöpft. Zwei Punkte sind erklärungsbedürftig:
Die Einträge ohne Termin nennen auf ihrer Seite sehr wohl ein Datum — das
der **letzten** Ausgabe. Der Scraper übernimmt es bewusst nicht, sondern
vermerkt es als Hinweis, sonst stünden vergangene Termine als kommende in der
Liste. Und die 129 unterdrückten Spielstätten tragen im Datenblatt nur den
Festivalnamen, sagen als Ortsangabe also nichts.

## Vergangene Ausgaben

Manche Quellseiten zeigen die **letzte** Ausgabe, wenn die nächste nicht
bestätigt ist — die Seite des Exit Festivals etwa den Jahrgang 2025. Solche
Einträge fallen nach dem Zusammenführen heraus, sobald ihr Termin älter ist als
`--since`. Einträge ganz ohne Termin bleiben dagegen drin: Das sind
angekündigte Festivals ohne bestätigtes Datum, erkennbar am Hinweis auf die
letzte gefundene Ausgabe.

## Bekannte Grenzen

- festivalticker listet unter *alle-festivals* nur 2026 plus die separate 2027-Seite;
  die Archivjahrgänge (2006–2025) haben eigene URLs und sind nicht enthalten.
- 291 Einträge haben kein Datum: die Quellen führen sie ohne bestätigte Neuauflage.
  Das Feld `Hinweis` nennt dann die letzte gefundene Ausgabe.
- Bei reinen Akronymen kann die Mehrheitsregel die falsche Variante wählen
  (`GANS` → `Gans`), da sie gemischte Schreibweise bevorzugt. Ein Großbuchstabe
  am Anfang hat Vorrang, damit nicht `b.o.s.c.h.` statt `B.O.S.C.H.` gewinnt.
- Zwei festivalticker-Seiten reihen Bandnamen ohne jeden Trenner aneinander
  (`Quincy Goldie 333 I Fire Schnuppe …`). Sie bleiben ohne Lineup: Eine
  Aufteilung nach Leerzeichen würde raten und aus „Nebula Allstars" die Band
  „Nebula" machen. Erfundene Bandnamen wären schlimmer als fehlende.
- Preise sind Freitext in zehn Währungen. Als Preis zählt nur eine Zahl direkt an
  einer Währung, sonst würde „VVK 199 € (Stufe 2)" als 2 € gelesen. „Spende" und
  „Zahl was du willst" ergeben 0 €; ein solcher Hinweis nach einer Preisangabe
  („VVK 45-172 € (Pay what you can)") hebt den Preis dagegen nicht auf.
  Zwei Angaben bleiben undeutbar, weil die Quelle dort Unsinn liefert (`Pop Punk`).
- Die Geokodierung ist auf europäische Länder begrenzt. Ohne diese Grenze liefert
  Nominatim bei mehrdeutigen Namen den weltweit bekanntesten Ort — „Newark" wurde
  New Jersey statt England.
