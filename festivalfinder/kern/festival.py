"""Ein Festival: was aus den Funden mehrerer Quellen wird.

Anders als ein `Fund` ist ein Festival veränderlich — beim Zusammenführen
wächst es, indem es sich aus einem zweiten Fund ergänzt. Es ist trotzdem ein
Datensatz mit festen Feldern (`slots=True`): Ein Tippfehler wirft, statt still
ein neues Feld anzulegen, das dann niemand ausliest.

Die ausgelieferte Form steht in `als_json()`. Ihre Feldnamen sind englisch und
bleiben es: `data/festivals.json` wird mitveröffentlicht, und wer sie
auswertet, soll das nach einem Umbau weiter tun können.
"""

from dataclasses import dataclass, field
from datetime import date

from . import zeit
from .fund import Fund


@dataclass(slots=True)
class Festival:
    """Eine Veranstaltung, wie sie am Ende auf der Seite steht."""

    name: str
    jahr: str = ""
    von: date | None = None
    bis: date | None = None
    stadt: str = ""
    land: str = ""
    ort: str = ""                                   # Spielstätte
    plz: str = ""
    lat: float | None = None
    lon: float | None = None
    preis: str = ""
    webseite: str = ""
    genre: str = ""
    besucher: str = ""
    hinweis: str = ""
    abgesagt: bool = False
    #: Quellenname → Adresse der Seite, von der es stammt
    quellen: dict[str, str] = field(default_factory=dict)
    #: Bandschlüssel → verbindliche Schreibweise
    bands: dict[str, str] = field(default_factory=dict)
    #: Rang der besten beteiligten Quelle; entscheidet, wessen Name gewinnt
    rang: int = 99
    #: Von `werkzeug.preisverlauf` gefüllt, sobald sich ein Preis geändert hat
    preis_start: str = ""
    preis_start_seit: str = ""

    @classmethod
    def aus_fund(cls, f: Fund, rang: int) -> "Festival":
        return cls(
            name=f.name, jahr=f.jahr, von=f.von, bis=f.bis,
            stadt=f.stadt, land=f.land, ort=f.ort, plz=f.plz,
            lat=f.lat, lon=f.lon, preis=f.preis, webseite=f.webseite,
            genre=f.genre, besucher=f.besucher, hinweis=f.hinweis,
            abgesagt=f.abgesagt, rang=rang,
        )

    @property
    def lineup(self) -> list[str]:
        """Die Acts, alphabetisch — so stehen sie auf der Karte."""
        return sorted(set(self.bands.values()), key=str.casefold)

    @property
    def location(self) -> str:
        """„Kiel, DE" — Ort und Land in einem Feld, für Liste und Suche."""
        return ", ".join(x for x in (self.stadt, self.land) if x)

    def als_json(self) -> dict:
        """Die ausgelieferte Form. Reihenfolge und Namen sind eine Zusage."""
        lineup = self.lineup
        return {
            "name": self.name,
            "year": self.jahr,
            "date_from": zeit.deutsch(self.von),
            "date_to": zeit.deutsch(self.bis),
            "city": self.stadt,
            "country": self.land,
            "venue": self.ort,
            "plz": self.plz,
            "lat": self.lat,
            "lon": self.lon,
            "location": self.location,
            "price": self.preis,
            "website": self.webseite,
            "genre": self.genre,
            "visitors": self.besucher,
            "note": self.hinweis,
            "cancelled": self.abgesagt,
            "sources": self.quellen,
            "price_start": self.preis_start,
            "price_start_seit": self.preis_start_seit,
            "lineup": lineup,
            "lineup_count": len(lineup),
        }
