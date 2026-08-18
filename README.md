# Festival-Übersicht Europa

Zusammengeführte Festival- und Lineup-Daten aus festivalticker.de,
festivalsunited.com und festival-alarm.com.

## Aufbau

`scraper/gemeinsam.py` hält Pfade, Browserkennung und das Länderwissen — das lag
vorher in drei Modulen nebeneinander. Die übrigen Skripte sind eigenständig
ausführbar und bauen aufeinander auf:

```
festival_scraper.py  →  data/festivals.json + CSV-Ausgaben
genres.py            →  Genre-Oberbegriffe (Modul, von build_site.py genutzt)
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

| Quelle | Weg | Umfang |
|---|---|---|
| festivalticker.de | alle Listenseiten: Jahres-, Monats-, Länder- und Statusarchive | 2.720 Detailseiten insgesamt |
| festivalsunited.com | `sitemap.xml` mit Unterkarten je Jahrgang | 16.044 Detailseiten insgesamt |
| festival-alarm.com | Jahresseiten `/Festivals-JAHR` | 4.750 Detailseiten insgesamt |

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
Termine, Preise und Orte. Außereuropäische Einträge werden verworfen.

## Neu erzeugen

```bash
python scraper/festival_scraper.py && python scraper/build_overview.py
```

Alle Seiten liegen unter `cache/` — ein erneuter Lauf ist dadurch in ~90 s durch,
ohne die Quellseiten nochmals abzurufen. Für frische Daten `cache/` löschen
(Erstlauf ca. 7–8 Minuten, 4 parallele Verbindungen).

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
python scraper/daily_update.py
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
sind 29 Festivals betroffen; sie bleiben in der Webseite ausgeblendet, lassen sich per
Haken einblenden und erscheinen dann durchgestrichen mit rotem Vermerk.

**Ablauf:** Wohnort → Umkreis → Ticketobergrenze → frühester Starttermin; danach
entweder Bands oder Genre. Bei Bands: suchen, auswählen, optional pro Band auf `×2`
stellen — die Trefferquote ist die gewichtete Summe der gefundenen Bands geteilt durch
die Summe aller gewählten Gewichte. Bei Genre: Oberbegriffe anklicken — die Trefferquote
ist die Zahl der abgedeckten geteilt durch die Zahl der gewählten Oberbegriffe.
Sortiert wird nach Übereinstimmung absteigend, bei Gleichstand nach Entfernung
aufsteigend, dann nach Preis aufsteigend.

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
Zugeordnet sind 3.526 der 4.367 Festivals; für 804 nennt keine Quelle eine Richtung, sie
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
Italienisch, Niederländisch, Polnisch und Portugiesisch. Alle Texte stehen in
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
läuft anschließend täglich um 03:17 UTC, lässt sich unter *Actions* aber auch
jederzeit von Hand starten. Er hält Seiten- und Geo-Cache über Läufe hinweg,
sodass pro Tag nur wirklich Geändertes neu abgerufen wird.

Warum nicht Streamlit: Streamlit Community Cloud ist für Python-Apps mit
Serverprozess gedacht. Diese Seite ist reines HTML/JS, bräuchte also einen
kompletten Umbau, liefe danach langsamer (Server-Roundtrip pro Klick) und
schläft auf dem kostenlosen Tarif nach Inaktivität ein. Pages hat keine
Schlafphase, keine Laufzeitkosten und die Aktualisierung ist ohnehin ein
Cron-Job, kein Serverdienst.

## Abgleich

**Festivals** werden in vier Stufen zusammengeführt: exakt über Name + Jahr + Stadt,
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

Die erste Stufe im Detail: Der Name wird dafür
normalisiert (Umlaute, Artikel, Jahreszahl und die Wörter „Festival/Open Air" fallen weg).
Die Stadt gehört bewusst zum Schlüssel: Tour-Formate wie das *Irish Spring Festival*
laufen unter einem Namen an 30 Orten und sind eigenständige Termine. In einem zweiten
Schritt werden Einträge quellenübergreifend verbunden, wenn es zu Name + Jahr in jeder
Quelle genau einen Kandidaten gibt — so greift der Abgleich auch bei abweichender
Ortsschreibweise, ohne Tourtermine zu verschmelzen.

**Bandnamen** laufen durch denselben Normalisierer (Groß-/Kleinschreibung, Akzente,
`&`/`and`, führendes „The", Satzzeichen). Je Gruppe gewinnt die häufigste Schreibweise
und ersetzt alle übrigen.

## Bekannte Grenzen

- festivalticker listet unter *alle-festivals* nur 2026 plus die separate 2027-Seite;
  die Archivjahrgänge (2006–2025) haben eigene URLs und sind nicht enthalten.
- 311 Einträge haben kein Datum: festivalsunited führt sie ohne bestätigte Neuauflage.
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
