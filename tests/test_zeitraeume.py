"""Fehler, die nur an bestimmten Tagen auftreten.

Ein Festival dauert mehrere Tage. Vergleicht man nur seinen Beginn, verschwindet
es genau dann, wenn es stattfindet:

* Der Filter „ab heute" liess an einem beliebigen Tag rund hundert laufende
  Festivals aus der Liste fallen — sie hatten gestern angefangen.
* Der Jahrgangsschnitt hätte am Neujahrstag jedes Fest verworfen, das über
  Silvester läuft: „Edinburgh's Hogmanay" beginnt am 29.12.

Die Regel lautet in beiden Fällen: Zeiträume überschneiden sich oder nicht.
"""

import pytest
from quellen import ft_adressen
from zusammenfuehren import zeitraum_ueberlappt


def zeitraum(von, bis):
    return {"date_from": von, "date_to": bis or von}


class TestUeberlappung:
    """Die Regel, nach der sich beide Seiten richten sollen."""

    @pytest.mark.parametrize("a,b,erwartet", [
        (("01.06.2026", "05.06.2026"), ("03.06.2026", "09.06.2026"), True),
        (("01.06.2026", "05.06.2026"), ("05.06.2026", "09.06.2026"), True),
        (("01.06.2026", "05.06.2026"), ("06.06.2026", "09.06.2026"), False),
        (("29.12.2026", "01.01.2027"), ("01.01.2027", "03.01.2027"), True),
        (("01.06.2026", ""), ("01.06.2026", ""), True),
    ])
    def test_zeitraeume(self, a, b, erwartet):
        assert zeitraum_ueberlappt(zeitraum(*a), zeitraum(*b)) is erwartet


class TestJahrgangsschnitt:
    """Was der Lauf verwirft, richtet sich nach dem Ende, nicht nach dem Beginn."""

    def schnitt(self, festivals, since):
        # dieselbe Bedingung wie in festival_scraper.main()
        return [f for f in festivals
                if not f["date_from"]
                or int((f["date_to"] or f["date_from"])[-4:]) >= since]

    def test_silvesterfest_bleibt_im_neuen_jahr(self):
        hogmanay = {"date_from": "29.12.2026", "date_to": "01.01.2027"}
        assert self.schnitt([hogmanay], 2027) == [hogmanay]

    def test_vergangener_jahrgang_faellt_heraus(self):
        alt = {"date_from": "01.08.2018", "date_to": "03.08.2018"}
        assert self.schnitt([alt], 2026) == []

    def test_ohne_termin_bleibt_stehen(self):
        offen = {"date_from": "", "date_to": ""}
        assert self.schnitt([offen], 2026) == [offen]


class TestListenfilter:
    """Dieselbe Regel schon beim Einsammeln der Adressen (festivalticker)."""

    def liste(self, von, bis):
        return f"""<html><body><table><tbody class="vevent">
          <tr><td><a class="summary" href="/festivals/hogmanay/">Hogmanay</a></td>
          <td><span class="dtstart"><span class="value-title" title="{von}"></span></span>
              <span class="dtend"><span class="value-title" title="{bis}"></span></span>
              <span class="location">Edinburgh</span> Land: GB</td></tr>
        </tbody></table></body></html>"""

    def adressen(self, monkeypatch, html, since):
        import quellen
        monkeypatch.setattr(quellen, "FT_LISTEN", ["https://festivalticker.test/liste/"])
        monkeypatch.setattr(quellen, "fetch", lambda _url: html)
        return ft_adressen(since)

    def test_ueber_silvester_bleibt_in_der_liste(self, monkeypatch):
        gefunden = self.adressen(monkeypatch, self.liste("2026-12-29", "2027-01-01"), 2027)
        assert len(gefunden) == 1

    def test_altes_jahr_faellt_aus_der_liste(self, monkeypatch):
        gefunden = self.adressen(monkeypatch, self.liste("2018-08-01", "2018-08-03"), 2026)
        assert gefunden == []
