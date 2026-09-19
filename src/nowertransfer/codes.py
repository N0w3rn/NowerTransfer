"""Generation of the code phrase that pairs sender and receiver.

The code phrase is not a convenience label - croc derives the end-to-end
encryption key from it via PAKE. It therefore has to be unguessable, which
rules out :mod:`random` (a Mersenne Twister whose state can be reconstructed
from earlier outputs) in favour of :mod:`secrets`.

Five words drawn without replacement from a 256 word list plus two digits
give 256*255*254*253*252*100 combinations, about 46.6 bits. Guessing is
online-only - croc's PAKE gives an attacker nothing to grind offline, and
every attempt costs a connection to the relay - so this is far past what
is reachable, while still being something you can read out over the phone.
"""

from __future__ import annotations

import math
import secrets

#: Short, lowercase, ASCII-only words. No umlauts, so they type the same
#: on any keyboard, and no two words within one edit of each other, so a
#: dictated code cannot land on a different valid word. The word list
#: test enforces both; it is what caught "stein"/"stern", "turm"/"sturm"
#: and "boden"/"bogen" in the first version of this list.
WORDS: tuple[str, ...] = (
    "abend", "adler", "ahorn", "amboss", "ananas", "anker", "apfel", "arena",
    "arktis", "asche", "atlas", "auge", "bagger", "balkon", "bambus", "banane",
    "basalt", "becher", "beere", "berg", "besen", "biber", "biene", "birke",
    "blatt", "blume", "boden", "boot", "brett", "brise", "bruecke", "brunnen",
    "buche", "butter", "dachs", "daumen", "deich", "delfin", "delta", "diamant",
    "distel", "docht", "donner", "dorf", "drache", "draht", "duene", "dunst",
    "ebene", "echse", "efeu", "eibe", "eiche", "eimer", "eisen", "elch",
    "engel", "eule", "faden", "fahne", "falke", "farn", "feder", "fels",
    "fenster", "ferkel", "fichte", "filter", "fisch", "flamme", "flieder",
    "floete", "fluss", "forelle", "fossil", "frost", "funke", "galerie",
    "gans", "garten", "gerste", "geysir", "gipfel", "gitter", "glocke",
    "granit", "gras", "grotte", "gurke", "hafen", "hagel", "hammer", "hang",
    "harfe", "hase", "haus", "hecke", "heide", "helm", "herd", "himmel",
    "hirsch", "hobel", "holz", "honig", "iglu", "imker", "indigo", "insel",
    "iris", "jade", "jaeger", "kabel", "kaefer", "kaktus", "kalk", "kamin",
    "kanu", "kapsel", "karren", "karte", "kaskade", "keller", "kerze", "kette",
    "kiesel", "kissen", "klee", "klinge", "knospe", "kobalt", "kohle", "kolben",
    "komet", "koralle", "korb", "krebs", "kreide", "kristall", "krone",
    "kueste", "kupfer", "lagune", "lampe", "laterne", "laub", "lawine",
    "leiter", "lerche", "leuchte", "licht", "lilie", "linde", "loewe", "lotus",
    "luchs", "luft", "magnet", "mandel", "mango", "marmor", "meer", "melone",
    "messer", "metall", "mine", "mond", "moos", "morgen", "motor", "muehle",
    "muschel", "muskat", "nacht", "nadel", "narwal", "nashorn", "nebel",
    "nektar", "nelke", "nest", "nische", "norden", "notiz", "nuss", "obst",
    "ofen", "olive", "opal", "orgel", "orkan", "otter", "ozean", "palme",
    "pappel", "paprika", "perle", "pfad", "pfeffer", "pfeil", "pfirsich",
    "pflaume", "pforte", "pilz", "pinguin", "planet", "platin", "prisma",
    "puma", "quarz", "quelle", "rabe", "radar", "rakete", "raupe", "regen",
    "ring", "robbe", "rose", "rubin", "ruder", "salbei", "sand", "schaf",
    "schilf", "schnee", "schotter", "segel", "seil", "senf", "sichel", "silber",
    "sirup", "sofa", "sonne", "spatel", "specht", "speer", "spindel", "spirale",
    "stein", "sturm", "tanne", "tiger", "tunnel", "ufer", "uhr", "vogel",
    "wald", "welle", "wiese", "wolke", "wurzel", "zebra", "zelt", "zimt",
)  # fmt: skip

WORD_COUNT = 5
DIGIT_COUNT = 2

#: Shortest input the receive screen accepts. croc's own default codes are
#: three short words, so anything below this is a typo rather than a code.
MIN_CODE_LENGTH = 6

_random = secrets.SystemRandom()


def generate_code() -> str:
    """Return a fresh phrase such as ``falke-wolke-tiger-nebel-quarz-83``."""
    words = _random.sample(WORDS, WORD_COUNT)
    digits = "".join(str(_random.randrange(10)) for _ in range(DIGIT_COUNT))
    return "-".join([*words, digits])


def code_entropy_bits() -> float:
    """Entropy of :func:`generate_code` in bits, for tests and docs."""
    combinations = math.perm(len(WORDS), WORD_COUNT) * 10**DIGIT_COUNT
    return math.log2(combinations)


def is_plausible_code(code: str) -> bool:
    """Cheap sanity check before starting croc on a receive."""
    return len(code.strip()) >= MIN_CODE_LENGTH
