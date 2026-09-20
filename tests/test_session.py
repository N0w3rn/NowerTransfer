"""Remembering interrupted transfers, in both directions and several
at once."""

import json

import pytest

from nowertransfer import paths, secretstore, session

CODE = "falke-wolke-tiger-nebel-83"
OTHER = "rabe-quarz-tanne-segel-17"

encrypted_only = pytest.mark.skipif(
    not secretstore.is_encrypting(),
    reason="no OS keystore on this platform; values are stored in the clear",
)


@pytest.fixture(autouse=True)
def isolated_session(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(session, "user_config_dir", lambda: tmp_path)


@pytest.fixture
def a_file(tmp_path):
    payload = tmp_path / "payload.txt"
    payload.write_text("hi", encoding="utf-8")
    return payload


@pytest.fixture
def a_folder(tmp_path):
    folder = tmp_path / "downloads"
    folder.mkdir()
    return folder


# ----------------------------------------------------------------------
#  One transfer, either direction
# ----------------------------------------------------------------------
def test_a_send_round_trips(a_file):
    session.remember_send(CODE, [str(a_file)])
    (restored,) = session.unfinished()

    assert isinstance(restored, session.SendSession)
    assert restored.code == CODE
    assert restored.paths == [str(a_file)]


def test_a_receive_round_trips(a_folder):
    session.remember_receive(CODE, a_folder)
    (restored,) = session.unfinished()

    assert isinstance(restored, session.ReceiveSession)
    assert restored.code == CODE
    assert restored.target == str(a_folder)


def test_nothing_stored_yields_nothing():
    assert session.unfinished() == []


@encrypted_only
def test_neither_the_phrase_nor_the_paths_are_stored_in_the_clear(tmp_path):
    payload = tmp_path / "quarterly numbers.txt"
    payload.write_text("hi", encoding="utf-8")
    session.remember_send(CODE, [str(payload)])

    stored = session.session_path().read_text(encoding="utf-8")
    assert CODE not in stored
    assert "quarterly numbers" not in stored


@encrypted_only
def test_a_receive_target_is_not_stored_in_the_clear(tmp_path):
    folder = tmp_path / "tax returns"
    folder.mkdir()
    session.remember_receive(CODE, folder)

    stored = session.session_path().read_text(encoding="utf-8")
    assert CODE not in stored
    assert "tax returns" not in stored


# ----------------------------------------------------------------------
#  Several at once
# ----------------------------------------------------------------------
def test_several_transfers_are_all_kept(tmp_path, a_file, a_folder):
    second = tmp_path / "second.txt"
    second.write_text("x", encoding="utf-8")

    session.remember_send(CODE, [str(a_file)])
    session.remember_receive(OTHER, a_folder)
    session.remember_send("segel-rose-ufer-pilz-42", [str(second)])

    assert len(session.unfinished()) == 3


def test_the_newest_is_offered_first(a_file, a_folder):
    session.remember_send(CODE, [str(a_file)])
    session.remember_receive(OTHER, a_folder)

    first, second = session.unfinished()
    assert first.code == OTHER
    assert second.code == CODE


def test_starting_the_same_phrase_again_does_not_duplicate_it(a_file):
    session.remember_send(CODE, [str(a_file)])
    session.remember_send(CODE, [str(a_file)])

    assert len(session.unfinished()) == 1


def test_finishing_one_leaves_the_others(a_file, a_folder):
    session.remember_send(CODE, [str(a_file)])
    session.remember_receive(OTHER, a_folder)

    session.forget(CODE)

    remaining = session.unfinished()
    assert [entry.code for entry in remaining] == [OTHER]


def test_forgetting_the_last_one_removes_the_file(a_file):
    session.remember_send(CODE, [str(a_file)])
    session.forget(CODE)

    assert not session.session_path().exists()
    assert session.unfinished() == []


def test_forgetting_a_phrase_nobody_stored_changes_nothing(a_file):
    session.remember_send(CODE, [str(a_file)])
    session.forget("never-stored-this-one-99")

    assert len(session.unfinished()) == 1


def test_forget_all_empties_the_list(a_file, a_folder):
    session.remember_send(CODE, [str(a_file)])
    session.remember_receive(OTHER, a_folder)

    session.forget_all()

    assert session.unfinished() == []


# ----------------------------------------------------------------------
#  Entries that can no longer be resumed
# ----------------------------------------------------------------------
def test_files_that_disappeared_are_dropped(tmp_path, a_file):
    session.remember_send(CODE, [str(a_file), str(tmp_path / "gone.txt")])
    (restored,) = session.unfinished()
    assert restored.paths == [str(a_file)]


def test_a_send_whose_files_all_vanished_is_not_offered(tmp_path):
    session.remember_send(CODE, [str(tmp_path / "gone.txt")])
    assert session.unfinished() == []


def test_a_receive_whose_folder_is_gone_is_not_offered(a_folder):
    session.remember_receive(CODE, a_folder)
    a_folder.rmdir()
    assert session.unfinished() == []


def test_a_transfer_from_another_machine_is_not_offered(a_file):
    session.session_path().write_text(
        json.dumps(
            {
                "version": 2,
                "transfers": [
                    {
                        "mode": "send",
                        "code": "dpapi:AQAAANCMnd8BFdERjHoAwE/Cl+s=",
                        "paths": [str(a_file)],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert session.unfinished() == []


def test_a_corrupt_file_is_ignored():
    session.session_path().write_text("{not json", encoding="utf-8")
    assert session.unfinished() == []


def test_an_entry_of_an_unknown_kind_is_ignored(a_file):
    session.session_path().write_text(
        json.dumps(
            {
                "version": 2,
                "transfers": [
                    {"mode": "sideways", "code": secretstore.protect(CODE)},
                    {
                        "mode": "send",
                        "code": secretstore.protect(OTHER),
                        "paths": [secretstore.protect(str(a_file))],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    assert [entry.code for entry in session.unfinished()] == [OTHER]


# ----------------------------------------------------------------------
#  The file an older version wrote
# ----------------------------------------------------------------------
def test_a_file_from_the_single_transfer_version_still_resumes(a_file):
    # Version 1 wrote the one transfer as the whole file. Upgrading
    # must not silently throw somebody's resume point away.
    session.session_path().write_text(
        json.dumps(
            {
                "mode": "send",
                "code": secretstore.protect(CODE),
                "paths": [secretstore.protect(str(a_file))],
            }
        ),
        encoding="utf-8",
    )

    (restored,) = session.unfinished()
    assert restored.code == CODE
    assert restored.paths == [str(a_file)]


def test_an_older_file_with_plain_paths_still_resumes(a_file):
    # Older still: the paths were not encrypted at all.
    session.session_path().write_text(
        json.dumps(
            {
                "mode": "send",
                "code": secretstore.protect(CODE),
                "paths": [a_file.as_posix()],
            }
        ),
        encoding="utf-8",
    )

    (restored,) = session.unfinished()
    assert restored.paths == [a_file.as_posix()]
