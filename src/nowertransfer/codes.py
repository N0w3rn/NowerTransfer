"""Generation of the code phrase that pairs sender and receiver.

The code phrase is not a convenience label - croc derives the end-to-end
encryption key from it via PAKE. It therefore has to be unguessable, which
rules out :mod:`random` (a Mersenne Twister whose state can be reconstructed
from earlier outputs) in favour of :mod:`secrets`.

Four words drawn without replacement from a 128 word list plus two digits
give 128*127*126*125*100 combinations, about 34.6 bits - comparable to
croc's own default and short enough to read out over the phone.
"""

from __future__ import annotations

import math
import secrets

#: Short, lowercase, ASCII-only words. No umlauts and no pairs that sound
#: alike, so a code phrase survives being dictated or typed on any keyboard.
WORDS: tuple[str, ...] = (
    "anker", "apfel", "arena", "atlas", "bagger", "balkon", "banane", "beere",
    "berg", "biber", "birke", "blume", "boden", "bogen", "boot", "brise",
    "bruecke", "buche", "dachs", "delfin", "diamant", "distel", "donner",
    "dorf", "drache", "duene", "ebene", "eiche", "eimer", "eisen", "elch",
    "engel", "falke", "feder", "fels", "feuer", "fisch", "flamme", "fluss",
    "garten", "gipfel", "glocke", "gras", "hafen", "hagel", "hase", "haus",
    "heide", "himmel", "honig", "hummel", "iglu", "insel", "jaeger", "kabel",
    "kaefer", "kamin", "kanu", "karte", "kerze", "kiesel", "klee", "komet",
    "koralle", "krone", "kueste", "lampe", "laterne", "leuchte", "linde",
    "luchs", "magnet", "mango", "marmor", "mond", "morgen", "motor",
    "muschel", "nadel", "nebel", "nektar", "nest", "norden", "oase", "ofen",
    "orgel", "otter", "palme", "pfad", "pfeil", "pilz", "pinsel", "planet",
    "quarz", "quelle", "rabe", "rakete", "regen", "ring", "robbe", "rose",
    "ruder", "sand", "schaf", "segel", "silber", "sonne", "specht", "stein",
    "stern", "sturm", "tanne", "tiger", "tunnel", "turm", "ufer", "uhr",
    "vogel", "wald", "welle", "wiese", "wolke", "wurzel", "zebra", "zeder",
    "zelt", "zimt",
)  # fmt: skip

WORD_COUNT = 4
DIGIT_COUNT = 2

#: Shortest input the receive screen accepts. croc's own default codes are
#: three short words, so anything below this is a typo rather than a code.
MIN_CODE_LENGTH = 6

_random = secrets.SystemRandom()


def generate_code() -> str:
    """Return a fresh code phrase such as ``falke-wolke-tiger-nebel-83``."""
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
