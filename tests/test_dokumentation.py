"""Das README muss das Projekt beschreiben, das es gibt.

Dreimal ist derselbe Fehler passiert: Die Fußnote nannte acht Quellen, während
zwölf sammelten. Die Datenschutzerklärung nannte Postleitzahlen für drei
Länder, während die Seite 36 kannte. Und als die Aufgabe wegfiel, die den
mitgebrachten Stand auffrischte, beschrieb das README sie weiter.

Niemand liest die Beschreibung, wenn er den Code ändert. Also liest der
Rechner mit — nicht den Sinn, aber die Namen: Was hier steht, muss es geben,
und was es gibt, muss hier stehen.
"""

import re

from gemeinsam import BASE

README = (BASE / "README.md").read_text(encoding="utf-8")


def genannt(muster: str) -> set[str]:
    return set(re.findall(muster, README))


def vorhanden(ordner: str, muster: str) -> set[str]:
    return {p.name for p in (BASE / ordner).glob(muster)}


def test_jedes_genannte_skript_gibt_es_auch():
    """Ein Verweis auf eine gelöschte Datei schickt Leser ins Leere."""
    fehlt = genannt(r"scraper/(\w+\.(?:py|ps1))") - vorhanden("scraper", "*.*")
    assert not fehlt, f"im README genannt, aber nicht vorhanden: {sorted(fehlt)}"


def test_jedes_skript_steht_auch_im_readme():
    """Ein neues Modul, das nirgends erklärt ist, findet niemand."""
    fehlt = vorhanden("scraper", "*.py") - genannt(r"scraper/(\w+\.py)")
    assert not fehlt, f"vorhanden, aber im README nicht genannt: {sorted(fehlt)}"


def test_die_testtabelle_ist_vollstaendig():
    """Auch die Prüfungen gehören in die Übersicht — sie sind die Begründung."""
    da = vorhanden("tests", "test_*.py")
    im_text = genannt(r"tests/(test_\w+\.py)")
    assert not (da - im_text), f"nicht im README: {sorted(da - im_text)}"
    assert not (im_text - da), f"im README, aber gelöscht: {sorted(im_text - da)}"


def test_keine_verweise_auf_die_abgeschaffte_auffrischung():
    """Die Aufgabe der Windows-Aufgabenplanung gibt es nicht mehr.

    festivalticker weist seit dem 22. August 2026 auch den eigenen Rechner ab;
    aufzufrischen gibt es nichts mehr. Wer den Weg hier beschrieben fände,
    suchte vergeblich nach den Skripten.
    """
    for datei in (BASE / "README.md", BASE / "scraper" / "schnappschuss.py"):
        inhalt = datei.read_text(encoding="utf-8")
        assert "stand_auffrischen" not in inhalt, \
            f"{datei.name} verweist noch auf die entfernte Auffrischung"


def test_der_mitgebrachte_stand_liegt_noch_da():
    """Er ist die letzte Abschrift — ohne ihn fehlen rund 1.900 Festivals.

    Diese Prüfung steht hier, damit ein Aufräumen nicht versehentlich die
    Datei mitnimmt: Sie sieht wie ein Zwischenspeicher aus und ist keiner.
    """
    stand = BASE / "data" / "schnappschuss" / "festivalticker.json.gz"
    assert stand.exists(), "der mitgebrachte Stand von festivalticker fehlt"
    assert stand.stat().st_size > 100_000, "der Stand ist verdächtig klein"
