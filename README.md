# Festival-Übersicht Europa

Zusammengeführte Festival- und Lineup-Daten aus festivalticker.de und festivalsunited.com.

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

**Reglergrenzen** stammen aus den Daten und werden bei jedem Build neu berechnet:
der Umkreis reicht bis zum entferntesten Festival ab `REF_PLZ` in `build_site.py`
(derzeit 97209 → 3.300 km), der Preis bis zum teuersten gefundenen Ticket
(derzeit 1.600 €), jeweils aufgerundet.

**Ablauf:** Wohnort → Umkreis → Ticketobergrenze → frühester Starttermin; danach Bands
suchen und auswählen, optional pro Band auf `×2` stellen. Die Trefferquote ist die
gewichtete Summe der gefundenen Bands geteilt durch die Summe aller gewählten Gewichte.
Sortiert wird nach Übereinstimmung absteigend, bei Gleichstand nach Entfernung
aufsteigend, dann nach Preis aufsteigend.

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

**Festivals** werden in drei Stufen zusammengeführt: exakt über Name + Jahr + Stadt,
dann über eindeutige Quellenpaare zu Name + Jahr, zuletzt über gleiche Stadt +
gleichen Starttermin + gemeinsamen Namensbestandteil bei verschiedenen Quellen.
Die dritte Stufe fängt Fälle wie „Kosmos Festival" gegen „Kosmos Festival Chemnitz"
ab. Der Starttermin ist dabei der entscheidende Schutz: „Winter Wutzrock" im Februar
und „Wutzrock" im August teilen Stadt und Namensteil, sind aber zwei Veranstaltungen.

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
  (`GANS` → `Gans`), da sie gemischte Schreibweise bevorzugt.
- Preise sind Freitext in zehn Währungen. Als Preis zählt nur eine Zahl direkt an
  einer Währung, sonst würde „VVK 199 € (Stufe 2)" als 2 € gelesen. „Spende" und
  „Zahl was du willst" ergeben 0 €; ein solcher Hinweis nach einer Preisangabe
  („VVK 45-172 € (Pay what you can)") hebt den Preis dagegen nicht auf.
  Zwei Angaben bleiben undeutbar, weil die Quelle dort Unsinn liefert (`Pop Punk`).
- Die Geokodierung ist auf europäische Länder begrenzt. Ohne diese Grenze liefert
  Nominatim bei mehrdeutigen Namen den weltweit bekanntesten Ort — „Newark" wurde
  New Jersey statt England.
