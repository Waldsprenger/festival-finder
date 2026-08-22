"""Genre-Freitext zu Oberbegriffen.

Die Stolpersteine sind Wörter, die in zwei Welten etwas anderes bedeuten:
"Hardcore" im Technoumfeld ist ein Tempo, kein Punk; "Classic Rock" hat mit
Klassik nichts zu tun.
"""

import pytest

from festivalfinder.kern.genres import OBERBEGRIFFE, normalisiere, oberbegriffe


class TestZuordnung:
    @pytest.mark.parametrize("text,erwartet", [
        ("Rock", ["rock"]),
        ("Melodic Death Metal", ["metal"]),
        ("Hip-Hop", ["hiphop"]),
        ("Techno", ["electronic"]),
        ("Schlager", ["schlager"]),
        ("Klassik", ["klassik"]),
        ("Mittelalter", ["mittelalter"]),
    ])
    def test_einfache_faelle(self, text, erwartet):
        assert oberbegriffe(text) == erwartet

    def test_mehrere_richtungen_sind_gewollt(self):
        # "Ska Punk" gehört zu beidem, wer nach einem filtert soll es finden
        assert set(oberbegriffe("Ska Punk")) == {"punk", "reggae"}

    def test_aufzaehlung_wird_zerlegt(self):
        assert set(oberbegriffe("Rock, Metal, Punk")) == {"rock", "metal", "punk"}
        assert set(oberbegriffe("Rock und Pop")) == {"rock", "pop"}
        assert set(oberbegriffe("Metal/Punk")) == {"metal", "punk"}

    @pytest.mark.parametrize("text,erwartet", [
        ("Hardcore Techno", ["electronic"]),      # kein Punk
        ("Classic Rock", ["rock"]),               # keine Klassik
        ("Hardstyle", ["electronic"]),
        ("Black Music", ["soul"]),
    ])
    def test_irrefuehrende_woerter(self, text, erwartet):
        assert oberbegriffe(text) == erwartet

    def test_sammelkategorie_nur_wenn_nichts_anderes_passt(self):
        assert oberbegriffe("Multi-Genre") == ["gemischt"]
        # Sobald eine Richtung erkennbar ist, fällt die Sammelkiste weg
        assert "gemischt" not in oberbegriffe("Multi-Genre: Rock, Metal, Punk")

    def test_reihenfolge_folgt_der_filterliste(self):
        treffer = oberbegriffe("Pop, Rock")
        assert treffer == [k for k in OBERBEGRIFFE if k in treffer]

    @pytest.mark.parametrize("text", ["", "   ", None])
    def test_ohne_angabe(self, text):
        assert oberbegriffe(text) == []


def test_normalisiere_zieht_schreibweisen_zusammen():
    assert normalisiere("Drum & Bass") == normalisiere("Drum & Bass ")
    assert normalisiere("Hip-Hop") == "hip hop"
    assert normalisiere("Größe") == "groesse"
