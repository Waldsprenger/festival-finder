"""Was alle zwölf Verzeichnisse gemeinsam haben.

Eine Quelle beantwortet zwei Fragen: Wie komme ich an ihre Detailseiten, und
wie lese ich eine davon? Was sie unterscheidet, steht in ihrer eigenen Datei —
früher standen alle zwölf in einer von 1.339 Zeilen, und wer wissen wollte, was
wannafest tut, las an elf anderen vorbei.

Zustand, den eine Quelle über ihre Seiten hinweg braucht, gehört ihr selbst:
festivalticker sammelt Stammdaten aus den Listenseiten und braucht sie später
beim Lesen der Detailseite. Das war ein Modulwörterbuch und ist jetzt ein Feld
ihres Objekts.
"""

from ..kern.fund import Fund
from ..netz import Abrufer


class Quelle:
    """Ein Verzeichnis: wo seine Seiten stehen und wie man sie liest."""

    #: Kurzname, wie er in den Daten und im Bericht auftaucht
    name: str = ""
    #: Startseite — steht in der Fußnote der Webseite
    startseite: str = ""
    #: Ein Satz dazu, wofür diese Quelle gut ist
    zweck: str = ""

    def adressen(self, netz: Abrufer, seit: int) -> list[str]:
        """Die Detailseiten ab Jahrgang `seit`."""
        return []

    def lesen(self, netz: Abrufer, url: str, html: str) -> Fund | None:
        """Eine Detailseite auswerten; None, wenn nichts Brauchbares dasteht."""
        raise NotImplementedError

    def sammeldatei(self, netz: Abrufer, seit: int) -> list[Fund] | None:
        """Quellen, die alles in einer Datei liefern, überschreiben das.

        Dann gibt es keine Adressen je Festival, sondern einen Abruf, der alle
        Datensätze auf einmal zurückgibt.
        """
        return None
