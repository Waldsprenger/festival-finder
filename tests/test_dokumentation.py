"""Das README muss das Projekt beschreiben, das es gibt.

Viermal ist derselbe Fehler passiert: Die Fußnote nannte acht Quellen, während
zwölf sammelten. Die Datenschutzerklärung nannte Postleitzahlen für drei
Länder, während die Seite 36 kannte. Die Aufgabe, die den mitgebrachten Stand
auffrischte, war gelöscht und stand weiter im README. Und der ganze Ordner
`scraper/` hieß danach `festivalfinder/`.

Niemand liest die Beschreibung, wenn er den Code ändert. Also liest der Rechner
mit — nicht den Sinn, aber die Namen: Was hier steht, muss es geben, und was es
gibt, muss hier stehen.
"""

import re

from festivalfinder.pfade import BASE

README = (BASE / "README.md").read_text(encoding="utf-8")


def genannt(muster: str) -> set[str]:
    return set(re.findall(muster, README))


def vorhanden(ordner: str, muster: str) -> set[str]:
    return {str(p.relative_to(BASE)).replace("\\", "/")
            for p in (BASE / ordner).glob(muster)}


def test_jedes_genannte_modul_gibt_es_auch():
    """Ein Verweis auf eine gelöschte Datei schickt Leser ins Leere."""
    fehlt = {p for p in genannt(r"`(festivalfinder/[\w/]+\.py)`")
             if not (BASE / p).exists()}
    assert not fehlt, f"im README genannt, aber nicht vorhanden: {sorted(fehlt)}"


def test_jedes_modul_steht_auch_im_readme():
    """Ein neues Modul, das nirgends erklärt ist, findet niemand."""
    da = vorhanden("festivalfinder", "**/*.py")
    da -= {p for p in da if p.endswith("__init__.py")}
    fehlt = da - genannt(r"`(festivalfinder/[\w/]+\.py)`")
    assert not fehlt, f"vorhanden, aber im README nicht genannt: {sorted(fehlt)}"


def test_jedes_seitenmodul_steht_im_readme():
    da = vorhanden("site/js", "*.js")
    fehlt = da - genannt(r"`(site/js/[\w.]+\.js)`")
    assert not fehlt, f"nicht im README: {sorted(fehlt)}"


def test_die_testtabelle_ist_vollstaendig():
    """Auch die Prüfungen gehören in die Übersicht — sie sind die Begründung."""
    da = vorhanden("tests", "**/test_*.py")
    im_text = genannt(r"`(tests/[\w/]+\.py)`")
    assert not (da - im_text), f"nicht im README: {sorted(da - im_text)}"
    assert not (im_text - da), f"im README, aber gelöscht: {sorted(im_text - da)}"


def test_keine_verweise_auf_den_alten_aufbau():
    """`scraper/` gibt es nicht mehr, und die abendliche Auffrischung auch nicht."""
    for begriff in ("scraper/", "stand_auffrischen"):
        assert begriff not in README, f"README verweist noch auf {begriff}"
    assert not (BASE / "scraper").exists()


def test_der_mitgebrachte_stand_liegt_noch_da():
    """Er ist die letzte Abschrift — ohne ihn fehlen rund 1.900 Festivals.

    Diese Prüfung steht hier, damit ein Aufräumen die Datei nicht mitnimmt:
    Sie sieht wie ein Zwischenspeicher aus und ist keiner.
    """
    stand = BASE / "data" / "schnappschuss" / "festivalticker.json.gz"
    assert stand.exists(), "der mitgebrachte Stand von festivalticker fehlt"
    assert stand.stat().st_size > 100_000, "der Stand ist verdächtig klein"
