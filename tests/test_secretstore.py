import base64

import pytest

from nowertransfer import secretstore

SECRET = "HrAQLtRIRpeoG9cxWYnsfl4TkFThlVBF"

encrypted_only = pytest.mark.skipif(
    not secretstore.is_encrypting(),
    reason="no OS keystore on this platform; values are stored in the clear",
)


def test_round_trip():
    assert secretstore.unprotect(secretstore.protect(SECRET)) == SECRET


def test_round_trip_of_awkward_characters():
    secret = 'päss "wörd" \\ with\ttabs'
    assert secretstore.unprotect(secretstore.protect(secret)) == secret


def test_empty_stays_empty():
    assert secretstore.protect("") == ""
    assert secretstore.unprotect("") == ""


def test_stored_form_is_tagged():
    stored = secretstore.protect(SECRET)
    assert stored.startswith((secretstore.PREFIX_DPAPI, secretstore.PREFIX_PLAIN))


@encrypted_only
def test_the_secret_is_not_recoverable_from_the_stored_text():
    stored = secretstore.protect(SECRET)
    assert SECRET not in stored
    # Not merely encoded, either.
    blob = base64.b64decode(stored[len(secretstore.PREFIX_DPAPI) :])
    assert SECRET.encode() not in blob


@encrypted_only
def test_ciphertext_differs_between_calls():
    assert secretstore.protect(SECRET) != secretstore.protect(SECRET)


@encrypted_only
def test_tampered_ciphertext_does_not_decrypt():
    stored = secretstore.protect(SECRET)
    blob = bytearray(base64.b64decode(stored[len(secretstore.PREFIX_DPAPI) :]))
    # The blob's header is not authenticated, so flip a byte in the
    # encrypted payload near the end instead.
    blob[-8] ^= 0xFF
    tampered = secretstore.PREFIX_DPAPI + base64.b64encode(blob).decode("ascii")
    assert secretstore.unprotect(tampered) == ""


@encrypted_only
def test_a_blob_from_another_application_is_rejected(monkeypatch):
    # Same DPAPI, different entropy - the app-specific salt is what makes
    # a foreign blob unusable here.
    monkeypatch.setattr(secretstore, "_ENTROPY", b"some other application")
    foreign = secretstore.protect(SECRET)
    monkeypatch.undo()
    assert secretstore.unprotect(foreign) == ""


def test_garbage_does_not_raise():
    assert secretstore.unprotect(secretstore.PREFIX_DPAPI + "not base64!!") == ""


def test_a_hand_written_value_is_taken_as_is():
    # Someone editing the config file by hand, or a file written before
    # this module existed.
    assert secretstore.unprotect(SECRET) == SECRET
