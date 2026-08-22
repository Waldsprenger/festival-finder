"""Die Kette: Was passiert, wenn ein Schritt scheitert - oder gar nicht endet.

Ein hängender Schritt ist schlimmer als ein gescheiterter: Das Ortsverzeichnis
lief einmal vierzehn Stunden, weil eine Prüfung in einer Schleife stand, und
niemandem fiel es auf. Seitdem gibt es eine Zeitgrenze.

Geprüft wird mit erfundenen Schritten in einem eigenen Verzeichnis — die echten
Schritte holen Seiten aus dem Netz und gehören nicht in einen Test.
"""

import pytest

import daily_update


@pytest.fixture
def kette(monkeypatch, tmp_path):
    """Führt eine Kette aus erfundenen Schritten aus und gibt Code und Protokoll."""
    (tmp_path / "scraper").mkdir()

    def bauen(schritte: list[tuple[str, str]], grenze=daily_update.STUNDE):
        gebaut = []
        for nr, (name, quelltext) in enumerate(schritte):
            datei = f"probe{nr}.py"
            (tmp_path / "scraper" / datei).write_text(quelltext, encoding="utf-8")
            gebaut.append((name, [datei]))
        monkeypatch.setattr(daily_update, "SCHRITTE", gebaut)
        monkeypatch.setattr(daily_update, "BASE", tmp_path)
        monkeypatch.setattr(daily_update, "LOG", tmp_path / "update.log")
        monkeypatch.setattr(daily_update, "STUNDE", grenze)
        code = daily_update.main()
        return code, (tmp_path / "update.log").read_text(encoding="utf-8")

    return bauen


def test_gelungener_schritt_steht_im_protokoll(kette):
    code, log = kette([("Probe", "print('fertig')")])
    assert code == 0
    assert "[Probe] ok" in log and "fertig" in log


def test_gescheiterter_schritt_wird_gezaehlt(kette):
    code, log = kette([("Probe", "raise SystemExit(3)")])
    assert code == 1
    assert "FEHLER (exit 3)" in log


def test_warnungen_stehen_im_protokoll(kette):
    code, log = kette([("Probe", "import sys; print('  ! Einbruch', file=sys.stderr)")])
    assert code == 0
    assert "! Einbruch" in log


def test_haengender_schritt_wird_abgebrochen(kette):
    code, log = kette([("Endlos", "import time; time.sleep(30)")], grenze=1)
    assert code == 1
    assert "ABBRUCH" in log and "Zeitgrenze 1s" in log


def test_nach_einem_abbruch_laufen_die_uebrigen_weiter(kette):
    code, log = kette([("Endlos", "import time; time.sleep(30)"),
                       ("Danach", "print('trotzdem gelaufen')")], grenze=1)
    assert code == 1
    assert "ABBRUCH" in log and "[Danach] ok" in log


def test_jeder_schritt_hat_eine_zeitgrenze():
    assert 1800 <= daily_update.STUNDE <= 7200


def test_das_einsammeln_hat_mehr_zeit():
    # Zwölf Quellen, 24.000 Seiten: Der erste weltweite Lauf ohne
    # Zwischenspeicher brauchte knapp zwei Stunden.
    schritt = daily_update.SCHRITTE[0]
    assert schritt[0] == "Festivaldaten"
    assert len(schritt) > 2 and schritt[2] >= 4 * 3600


def test_die_uebrigen_schritte_erben_die_stunde(kette):
    # Ohne eigene Angabe gilt STUNDE - geprüft am Verhalten, nicht am Wert
    code, log = kette([("Endlos", "import time; time.sleep(30)")], grenze=1)
    assert "Zeitgrenze 1s" in log
