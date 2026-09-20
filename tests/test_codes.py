import re

import pytest

from nowertransfer import codes
from nowertransfer.codes import generate_code, is_our_code

CODE_PATTERN = re.compile(rf"^[a-z]+(-[a-z]+){{{codes.WORD_COUNT - 1}}}-\d{{2}}$")


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


def test_word_list_is_unique_and_ascii():
    assert len(set(codes.WORDS)) == len(codes.WORDS)
    assert all(word.isascii() and word.islower() for word in codes.WORDS)


def test_no_two_words_are_one_typo_apart():
    """A dictated code must not be able to land on a different word.

    This is what rules out pairs like stein/stern or boden/bogen: hearing
    one and typing the other would silently produce a valid but wrong
    code phrase, and the transfer would just never connect.
    """
    words = codes.WORDS
    clashes = [
        (a, b)
        for i, a in enumerate(words)
        for b in words[i + 1 :]
        if abs(len(a) - len(b)) <= 1 and edit_distance(a, b) < 2
    ]
    assert not clashes, f"one edit apart: {clashes}"


def test_the_list_is_big_enough_for_the_documented_entropy():
    assert len(codes.WORDS) >= 256


def test_generated_codes_have_the_documented_shape():
    for _ in range(50):
        assert CODE_PATTERN.match(codes.generate_code())


def test_generated_codes_use_distinct_words():
    words = codes.generate_code().split("-")[: codes.WORD_COUNT]
    assert len(set(words)) == codes.WORD_COUNT


def test_codes_are_not_trivially_repeated():
    generated = {codes.generate_code() for _ in range(200)}
    assert len(generated) == 200


def test_entropy_is_high_enough_to_be_a_secret():
    # The code phrase is croc's end-to-end encryption secret, not a label.
    assert codes.code_entropy_bits() > 45


def test_generator_is_cryptographically_seeded():
    import secrets

    assert isinstance(codes._random, secrets.SystemRandom)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", False), ("abc", False), ("  abc  ", False), ("falke-wolke", True)],
)
def test_plausible_code(value, expected):
    assert codes.is_plausible_code(value) is expected


# ----------------------------------------------------------------------
#  Recognising one of our own phrases
# ----------------------------------------------------------------------
def test_a_phrase_we_generated_is_recognised():
    for _ in range(50):
        assert is_our_code(generate_code())


@pytest.mark.parametrize(
    "text",
    [
        # Copied with the surrounding whitespace, or shouted.
        "  falke-wolke-tiger-nebel-quarz-83  ",
        "FALKE-WOLKE-TIGER-NEBEL-QUARZ-83",
    ],
)
def test_spacing_and_case_do_not_matter(text):
    assert is_our_code(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hello",
        # Long enough for is_plausible_code, which is why that one
        # cannot be trusted to fill a field from the clipboard.
        "have a look at this please",
        "https://example.com/some/path",
        # Right shape, but the words are not ours.
        "alpha-bravo-charlie-delta-echo-83",
        # Our words, wrong count.
        "falke-wolke-tiger-nebel-83",
        "falke-wolke-tiger-nebel-quarz-rabe-83",
        # Our words, but no digits where the digits go.
        "falke-wolke-tiger-nebel-quarz-ab",
        "falke-wolke-tiger-nebel-quarz-8",
        # One typo is enough to make it not ours.
        "falke-wolke-tiger-nebel-quarZz-83",
    ],
)
def test_anything_else_is_not_ours(text):
    assert not is_our_code(text)


def test_it_is_stricter_than_the_length_check():
    # The two exist for different jobs: one guards starting croc, the
    # other decides whether to put text in front of the user.
    loose = "have a look at this please"
    assert codes.is_plausible_code(loose)
    assert not is_our_code(loose)
