"""Die Datenschutzerklärung muss beschreiben, was die Seite wirklich tut.

Sie hat es eine Weile nicht getan: Dort stand, aufgelöst würden Postleitzahlen
„für Deutschland, Österreich und die Schweiz". Seit der weltweiten Erweiterung
kennt die Seite 55.385 Postleitzahlen aus 36 Ländern — die übrigen 33 kommen
aus dem Verzeichnis, das erst bei Bedarf nachgeladen wird. Auch die Zahl der
Ortsnamen war um ein Drittel zu klein.

Solche Sätze veralten still: Niemand liest die Rechtstexte, wenn er den
Scraper erweitert. Also prüft der Rechner mit.
"""

import json
import re

import pytest

from festivalfinder.pfade import BASE, DATA, SITE

DATENSCHUTZ = (SITE / "datenschutz.html").read_text(encoding="utf-8")


def genannte_zahl(muster: str) -> int:
    """Eine „rund 16.700"-Angabe aus dem Text, als Zahl."""
    m = re.search(muster, DATENSCHUTZ)
    assert m, f"Angabe nicht gefunden: {muster}"
    return int(m.group(1).replace(".", "").replace(" ", ""))


def nah_dran(genannt: int, wirklich: int, toleranz: float = 0.1) -> bool:
    """Gerundete Angaben dürfen abweichen — aber nicht um Größenordnungen."""
    return abs(genannt - wirklich) <= max(1, wirklich * toleranz)


def test_die_genannten_postleitzahlen_gibt_es_auch():
    """Die mitgelieferte Tabelle deckt DE, AT und CH ab — und nur die."""
    plz = json.loads((DATA / "plz.json").read_text(encoding="utf-8"))
    laender = {eintrag[4] for eintrag in plz if eintrag[4]}
    assert laender == {"DE", "AT", "CH"}, f"mitgeliefert: {sorted(laender)}"

    genannt = genannte_zahl(r"rund ([\d.]+)\s+Postleitzahlen\s+für\s+Deutschland")
    assert nah_dran(genannt, len(plz)), f"genannt {genannt}, wirklich {len(plz)}"


def test_die_genannten_ortsnamen_gibt_es_auch():
    orte = json.loads((DATA / "gazetteer.json").read_text(encoding="utf-8"))
    genannt = genannte_zahl(r"sowie rund ([\d.]+)\s*\n?\s*Ortsnamen")
    assert nah_dran(genannt, len(orte)), f"genannt {genannt}, wirklich {len(orte)}"


def test_das_nachgeladene_verzeichnis_steht_im_text():
    """Was nachgeladen wird, gehört genannt — auch wenn es vom eigenen Server kommt.

    Die grosse Verortungstabelle wird nicht mitversioniert; ohne sie lässt sich
    nur prüfen, dass der Text sie überhaupt erwähnt.
    """
    assert "nach" in DATENSCHUTZ and "Verzeichnis" in DATENSCHUTZ, \
        "das nachgeladene Verzeichnis kommt im Text nicht vor"

    verortung_datei = DATA / "verortung.json"
    if not verortung_datei.exists():
        pytest.skip("verortung.json liegt nicht vor (wird nicht mitversioniert)")

    verortung = json.loads(verortung_datei.read_text(encoding="utf-8"))
    plz_fern = verortung.get("plz_nachladen") or []
    orte_fern = verortung.get("orte") or []
    laender = {e[4] for e in plz_fern if len(e) > 4 and e[4]}

    genannt_plz = genannte_zahl(r"rund ([\d.]+) weitere Postleitzahlen")
    assert nah_dran(genannt_plz, len(plz_fern)), \
        f"genannt {genannt_plz}, wirklich {len(plz_fern)}"

    genannt_laender = genannte_zahl(r"Postleitzahlen aus (\d+) Ländern")
    assert genannt_laender == len(laender), \
        f"genannt {genannt_laender} Länder, wirklich {len(laender)}: {sorted(laender)}"

    genannt_orte = genannte_zahl(r"sowie rund ([\d.]+)\s*\n?\s*Ortsnamen weltweit")
    assert nah_dran(genannt_orte, len(orte_fern)), \
        f"genannt {genannt_orte}, wirklich {len(orte_fern)}"


def test_kein_versprechen_von_nur_dach():
    """Der alte Satz darf nicht zurückkommen.

    „Postleitzahlen für Deutschland, Österreich und die Schweiz" ist richtig,
    solange danebensteht, dass es noch mehr gibt. Ohne diesen Zusatz wäre es
    wieder die alte, falsche Aussage.
    """
    abschnitt = DATENSCHUTZ.split("<h2>Ortssuche</h2>", 1)[1].split("<h2>", 1)[0]
    assert "weitere Postleitzahlen" in abschnitt, \
        "der Abschnitt nennt nur die DACH-Postleitzahlen"


def test_die_quellen_der_fussnote_stimmen_mit_dem_scraper_ueberein():
    """Auf der Seite muss stehen, woher die Daten kommen — alle zwölf.

    Die Fussnote nannte lange acht, weil die vier weltweiten Quellen
    nachträglich dazukamen und niemand den Text mitzog.
    """
    from festivalfinder.quellen import BAUPLAN
    namen = [b.name for b in BAUPLAN]
    assert len(namen) >= 12, f"nur {len(namen)} Quellen erkannt"

    seite = (SITE / "index.html").read_text(encoding="utf-8")
    fuss = seite.split('<p class="src">Festival- und Lineup-Daten', 1)[1].split("</p>", 1)[0]
    # "festivalalarm" heisst im Netz "festival-alarm.com", "festapp" "festapp.io"
    ohne_striche = fuss.replace("-", "")
    fehlen = [n for n in namen if n not in ohne_striche]
    assert not fehlen, f"in der Fussnote fehlen: {fehlen}"
