import string

import pytest

from nowertransfer.i18n import CATALOG, DEFAULT_LANGUAGE, LANGUAGES, Translator


def placeholders(text):
    return {
        name for _, name, _, _ in string.Formatter().parse(text) if name is not None
    }


@pytest.mark.parametrize("key", sorted(CATALOG))
def test_every_key_is_translated_into_every_language(key):
    missing = [code for code in LANGUAGES if not CATALOG[key].get(code)]
    assert not missing, f"{key} is missing: {missing}"


@pytest.mark.parametrize("key", sorted(CATALOG))
def test_translations_agree_on_their_placeholders(key):
    # A placeholder present in one language but not another makes the
    # other language crash at format() time.
    expected = placeholders(CATALOG[key][DEFAULT_LANGUAGE])
    for code in LANGUAGES:
        assert placeholders(CATALOG[key][code]) == expected, key


def test_translator_formats_fields():
    translator = Translator("en")
    assert "17" in translator("status.retry", seconds=17)


def test_translator_falls_back_to_the_default_language():
    assert Translator("klingon").language == DEFAULT_LANGUAGE


def test_unknown_key_returns_itself_rather_than_raising():
    assert Translator("de")("no.such.key") == "no.such.key"


def test_error_keys_emitted_by_the_worker_exist():
    from nowertransfer import transfer

    assert transfer.ERROR_RELAY_UNREACHABLE in CATALOG
    assert transfer.ERROR_CROC_START_FAILED in CATALOG
