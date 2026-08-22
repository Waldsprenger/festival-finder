"""Ordnet die Genre-Freitexte der Quellen einer Handvoll Oberbegriffen zu.

Die drei Quellen schreiben das Genre als Freitext: 1.544 verschiedene Angaben
von "Rock" bis "Psychedelic Minimal Techno". Als Filter taugt das nicht - danach
sucht niemand. Deshalb wird jede Angabe auf Oberbegriffe abgebildet.

Ein Genretext kann mehrere Oberbegriffe ergeben, und das ist Absicht:
"Ska Punk" gehoert zu Punk und zu Reggae/Ska, wer nach einem von beiden filtert,
soll das Festival finden.

    >>> oberbegriffe("Melodic Death Metal, Irish Folk")
    ['metal', 'folk']

Zwei Stufen: SPEZIAL faengt zuerst die Faelle ab, bei denen ein Wort in die
Irre fuehrt ("Hardcore Techno" ist kein Hardcore-Punk, "Classic Rock" keine
Klassik). Was dort nicht greift, laeuft durch STICHWORTE, wo jeder passende
Oberbegriff zaehlt.
"""

import re
import unicodedata

# Schluessel -> deutscher Name. Die Reihenfolge ist die der Filterliste auf der
# Webseite; uebersetzt werden die Namen in site/i18n.js unter "genre.<schluessel>".
OBERBEGRIFFE: dict[str, str] = {
    "rock": "Rock",
    "metal": "Metal",
    "punk": "Punk & Hardcore",
    "pop": "Pop",
    "hiphop": "Hip-Hop & Rap",
    "electronic": "Elektro, Techno & Dance",
    "reggae": "Reggae, Ska & Dancehall",
    "jazzblues": "Jazz, Blues & Swing",
    "soul": "Soul, Funk & R&B",
    "folk": "Folk, Country & Liedermacher",
    "world": "Weltmusik",
    "klassik": "Klassik & Chor",
    "schlager": "Schlager, Volksmusik & Blasmusik",
    "gothic": "Gothic, Wave & Industrial",
    "mittelalter": "Mittelalter",
    "buehne": "Kultur, Comedy & Bühne",
    "gemischt": "Genreübergreifend",
}

# Erst pruefen, dann Schluss: Hier stehen die Angaben, bei denen ein Stichwort
# sonst falsch greifen wuerde.
SPEZIAL: list[tuple[str, tuple[str, ...]]] = [
    # "Hardcore" ist im Technoumfeld ein Tempo, kein Punk.
    (r"hardcore techno|hardcore \(electro\)|uptempo|frenchcore|terrorcore|"
     r"darkcore|happy hardcore|uk hardcore|industrial hardcore|"
     r"hardcore hardstyle|gabber", ("electronic",)),
    (r"hardstyle|hardtekk|hardtek\b|tekstyle|raggatek|rawstyle|hard dance|"
     r"early rave|hands up|jumpstyle|bounce", ("electronic",)),
    (r"hardcore \(metal\)", ("punk", "metal")),
    # "Classic/Klassiker" meint hier die alten Platten, nicht das Orchester.
    (r"classic rock|classic metal|klassiker", ("rock",)),
    (r"^uk garage$|garage house", ("electronic",)),
    (r"black music", ("soul",)),
    (r"desert blues", ("jazzblues", "world")),
    # Buehnenprogramm ohne Musikbezug - sonst zoege "Horror" Horrorpunk mit.
    (r"^(horror|thriller|drama|film|filme|kurzfilme|dokumentarfilm|"
     r"animationsfilm|lesung|theater|comedy|kabarett|poetry|performance|"
     r"artistik|zirkus|kunst|tanz|sport|yoga|healing|percussion|show)$",
     ("buehne",)),
    (r"musik kabarett|kunst & kultur|kabarett", ("buehne",)),
]

# Ein Stichwort je Oberbegriff. Alle passenden zaehlen.
STICHWORTE: dict[str, str] = {
    "rock": r"rock|n roll|billy\b|grunge|britpop|shoegaze|gazepunk|doomgaze|"
            r"kraut|stoner|psychedelic|\bpsych\b|\bgarage\b|\bsurf\b|"
            r"\bindie\b|\bbeat\b|\bjam\b|\bfuzz\b|\bemo\b|hamburger schule|"
            r"\btrash\b|\boldies\b|\bzappa",
    "metal": r"metal|deathcore|grind|thrash|\bdoom\b|\bsludge\b|death|black|"
             r"\bdjent\b|\bviking\b|kammercore|\bslam\b|\bheavy\b",
    "punk": r"punk|hardcore|\boi!?\b|crust|core|beatdown|powerviolence|"
            r"screamo|riot|\bd beat\b|\bschrammel",
    "pop": r"pop|chanson|\bcharts\b|\bndw\b|neue deutsche welle|\bmalle\b|"
           r"\bpink\b|spice girls",
    "hiphop": r"hip.?hop|trip.?hop|\brap\b|rapcore|\btrap\b|\bgrime\b|"
              r"beatbox|\burban\b|\bcrunk\b|\bdrill\b|freestyle|spoken word",
    "electronic": r"techno|house|trance|electro|elektro|\bedm\b|\bdance\b|"
                  r"eurodance|\brave\b|\bgoa\b|\bpsy|dubstep|psydub|"
                  r"drum ?& ?bass|\bdnb\b|\bidm\b|\bjungle\b|breakbeat|bass|"
                  r"minimal|ambient|downtempo|downbeat|chill|\bsynth|tronic|"
                  r"glitch|schranz|crossbreed|oldschool|hard groove|houese|"
                  r"\bdisco\b|\bclub\b|\bacid\b|moombahton|\bhitech\b|"
                  r"\bforest\b|\bfull ?on\b|\bbig beat\b|\bbig room\b|"
                  r"\bmashup\b|\bcosmic\b|amapiano",
    "reggae": r"reggae|dancehall|\bska|\bdub\b|rocksteady|\bragga\b|calypso|"
              r"reggaeton|\b2 tone\b",
    "jazzblues": r"jazz|blues|blies|\bswing\b|dixie|boogie|new orleans|bebop|"
                 r"\bold time\b|easy listening",
    "soul": r"\bsoul\b|funk|r ?& ?b|rhythm ?& ?blues|motown|gospel",
    "folk": r"folk|singer|songwriter|liedermach|americana|bluegrass|country|"
            r"celtic|\birish\b|scottish|breton|nordic|shanty|acoustic|"
            r"acustic|akustik|\broots\b|\bpipes\b|\bmundart\b|\bfado\b|"
            r"\bpolka\b|handpan|didgeridoo|dudelsack|fingerstyle|"
            r"traditionelle musik|\btrad\b",
    "world": r"world|woldmusic|weltmusik|balkan|latin|altin|salsa|cumbia|"
             r"samba|afro|afrika|africa|gypsy|klezmer|flamenco|tango|"
             r"reggaeton|kuduro|bachata|rumba|zouk|kologo|chicha|turkish|"
             r"tribal|brass|caribbean|brazilian|mantra|kirtan|merengue|"
             r"russendisko|mbalax|global|zouglou|soukous|soca|sevdalinka|"
             r"son cubano|taiko|marimba|wienerlied|wiener lied|jiddisch|"
             r"wassoulou|exotica|offbeat",
    "klassik": r"klassik|klassisch|classical|a.?cap+ella|\bchor\b|\boper\b|"
               r"orchester|kammermusik|neue musik|alte musik|gregorian",
    "schlager": r"schlager|volksmusik|blasmusik|marschmusik|militaermusik|"
                r"volkstuemlich|boehmische|mallorca|\bmalle\b|tanzmusik|"
                r"dixie|\bhumpa\b|schrammel|alpen",
    "gothic": r"\bgoth|dark ?wave|cold ?wave|\bwave\b|\bebm\b|industrial|"
              r"aggrotech|neue deutsche haerte|\bndh\b|dark electro|"
              r"\boccult\b|\bdrone\b|\bnoise\b|cyber",
    "mittelalter": r"mittelalter|medieval|\bpirat|wikinger|\bviking\b|"
                   r"\bshanty\b|\bfantasy\b",
    "buehne": r"comedy|kabarett|theater|lesung|poetry|film|kino|\bkunst\b|"
              r"artistik|akrobatik|jonglage|zauberei|magie|zirkus|"
              r"performance|\btanz\b|\bsport\b|\byoga\b|meditation|healing|"
              r"kindermusik|kinderlieder|beatboxing|\bdrama\b|\bthriller\b|"
              r"\btalk\b|trommeln|perkussion|satsang|looping|serien|sakral|"
              r"medicine music|community",
    "gemischt": r"genreuebergreifend|gemischt|sonstiges|\bcover|tribute|"
                r"crossover|\bparty\b|\bcharts\b|\bdiverse|experimental|"
                r"avantgarde|avant\b|\bmixed\b|multi ?genre|"
                r"\balternative$|^\d+(er|s)?$|neue musik|blockbuster|"
                r"mash ?up|coveer|\buvm\b|querbeet|alles dabei",
}

_SPEZIAL = [(re.compile(muster), keys) for muster, keys in SPEZIAL]
_STICHWORTE = {k: re.compile(v) for k, v in STICHWORTE.items()}

# "Rock und Pop", "Chanson. Rap", "Metal/Punk" sind zwei Angaben in einem Feld.
_TRENNER = re.compile(r"\s+und\s+|\s*[/|;]\s*|\.\s+")


def normalisiere(text: str) -> str:
    """Kleinschreibung, Umlaute ausgeschrieben, Satzzeichen als Leerzeichen."""
    t = unicodedata.normalize("NFC", text).casefold()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                     ("é", "e"), ("è", "e"), ("’", "'")):
        t = t.replace(alt, neu)
    t = re.sub(r"[.'`´\-_]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _zuordnen(teil: str) -> list[str]:
    for muster, keys in _SPEZIAL:
        if muster.search(teil):
            return list(keys)
    return [k for k, muster in _STICHWORTE.items() if muster.search(teil)]


def oberbegriffe(genre_text: str) -> list[str]:
    """Oberbegriffe eines Genrefeldes, in der Reihenfolge von OBERBEGRIFFE.

    "Genreuebergreifend" ist der Rueckfall und faellt weg, sobald eine
    Richtung erkennbar ist: Bei "Rock im Park" nennt eine Quelle
    "Multi-Genre", die andere acht konkrete Stile - dann taugt die Sammelkiste
    nicht mehr als Beschreibung, sie waere nur noch ein Ort zum Verlieren.
    """
    treffer: set[str] = set()
    for angabe in (genre_text or "").split(","):
        roh = normalisiere(angabe)
        if not roh:
            continue
        for teil in _TRENNER.split(roh):
            teil = teil.strip()
            if teil:
                treffer.update(_zuordnen(teil))
    if len(treffer) > 1:
        treffer.discard("gemischt")
    return [k for k in OBERBEGRIFFE if k in treffer]
