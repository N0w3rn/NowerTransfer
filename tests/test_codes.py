import re

import pytest

from nowertransfer import codes

CODE_PATTERN = re.compile(r"^[a-z]+(-[a-z]+){3}-\d{2}$")


def test_word_list_is_unique_and_ascii():
    assert len(set(codes.WORDS)) == len(codes.WORDS)
    assert all(word.isascii() and word.islower() for word in codes.WORDS)


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
    assert codes.code_entropy_bits() > 32


def test_generator_is_cryptographically_seeded():
    import secrets

    assert isinstance(codes._random, secrets.SystemRandom)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", False), ("abc", False), ("  abc  ", False), ("falke-wolke", True)],
)
def test_plausible_code(value, expected):
    assert codes.is_plausible_code(value) is expected
