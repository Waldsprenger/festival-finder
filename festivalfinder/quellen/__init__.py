"""Die zwölf Verzeichnisse — und die Reihenfolge, in der sie zählen.

Die Reihenfolge ist keine Geschmackssache: Sie entscheidet beim Zusammenführen,
wessen Schreibweise gewinnt. Vorn stehen die gepflegten deutschsprachigen
Verzeichnisse, weil sie die gewohnte Schreibweise deutscher Festivals führen;
die weltweiten Ergänzungen folgen dahinter.

Eine Quelle hinzuzufügen heißt: eine Datei danebenlegen und hier eine Zeile
eintragen. Nichts anderes im Programm muss davon wissen.
"""

from .basis import Quelle
from .festapp import Festapp
from .festivalabroad import FestivalAbroad
from .festivalalarm import FestivalAlarm
from .festivalfinder_eu import FestivalFinderEu
from .festivalflyer import FestivalFlyer
from .festivalhopper import FestivalHopper
from .festivalnetworks import FestivalNetworks
from .festivalsunited import FestivalsUnited
from .festivalticker import Festivalticker
from .festivism import Festivism
from .jambase import JamBase
from .wannafest import WannaFest

#: Alle Quellen in der Reihenfolge ihres Rangs
BAUPLAN = [
    Festivalticker,
    FestivalsUnited,
    FestivalAlarm,
    FestivalHopper,
    Festapp,
    WannaFest,
    FestivalFlyer,
    FestivalFinderEu,
    # Weltweit. Sie stehen hinten, weil die deutschsprachigen Quellen die
    # gewohnte Schreibweise deutscher Festivals führen.
    FestivalAbroad,
    JamBase,
    FestivalNetworks,
    Festivism,
]


def alle() -> list[Quelle]:
    """Frische Quellenobjekte — jeder Lauf bekommt seine eigenen.

    Objekte statt eines Modulzustands: festivalticker sammelt Stammdaten aus
    seinen Listenseiten, und zwei Läufe hintereinander sollen sich davon nichts
    borgen.
    """
    return [bauart() for bauart in BAUPLAN]


#: Rang je Quellenname; kleiner ist besser
RANG = {bauart.name: i for i, bauart in enumerate(BAUPLAN)}

__all__ = ["Quelle", "BAUPLAN", "alle", "RANG"]
