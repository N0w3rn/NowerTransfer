import json

import pytest

from nowertransfer import paths, secretstore, session

CODE = "falke-wolke-tiger-nebel-83"


@pytest.fixture(autouse=True)
def isolated_session(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(session, "user_config_dir", lambda: tmp_path)


def test_round_trip(tmp_path):
    payload = tmp_path / "payload.txt"
    payload.write_text("hi", encoding="utf-8")

    session.save_send_session(CODE, [str(payload)])
    restored = session.load_send_session()

    assert restored is not None
    assert restored.code == CODE
    assert restored.paths == [str(payload)]


@pytest.mark.skipif(
    not secretstore.is_encrypting(),
    reason="no OS keystore on this platform; values are stored in the clear",
)
def test_the_code_phrase_is_not_stored_in_the_clear(tmp_path):
    # The code phrase is croc's end-to-end encryption secret, so the
    # resume file must not hand it to anyone who opens it.
    payload = tmp_path / "payload.txt"
    payload.write_text("hi", encoding="utf-8")
    session.save_send_session(CODE, [str(payload)])

    assert CODE not in session.session_path().read_text(encoding="utf-8")


@pytest.mark.skipif(
    not secretstore.is_encrypting(),
    reason="no OS keystore on this platform; values are stored in the clear",
)
def test_the_paths_are_not_stored_in_the_clear(tmp_path):
    # A folder name says what was being sent. It is worth as little to
    # a reader of this file as the code phrase is.
    payload = tmp_path / "quarterly numbers.txt"
    payload.write_text("hi", encoding="utf-8")
    session.save_send_session(CODE, [str(payload)])

    stored = session.session_path().read_text(encoding="utf-8")
    assert "quarterly numbers" not in stored
    assert str(tmp_path) not in stored


def test_a_session_written_before_the_paths_were_encrypted_still_resumes(tmp_path):
    # Upgrading must not silently drop somebody's resume point.
    payload = tmp_path / "payload.txt"
    payload.write_text("hi", encoding="utf-8")
    session.session_path().write_text(
        json.dumps(
            {
                "mode": "send",
                "code": secretstore.protect(CODE),
                "paths": [payload.as_posix()],  # as an older version wrote it
            }
        ),
        encoding="utf-8",
    )

    restored = session.load_send_session()

    assert restored is not None
    assert restored.code == CODE
    assert restored.paths == [payload.as_posix()]


def test_a_session_from_another_machine_is_not_offered(tmp_path):
    payload = tmp_path / "payload.txt"
    payload.write_text("hi", encoding="utf-8")
    session.session_path().write_text(
        '{"mode": "send", "code": "dpapi:AQAAANCMnd8BFdERjHoAwE/Cl+s=",'
        f' "paths": ["{payload.as_posix()}"]}}',
        encoding="utf-8",
    )
    assert session.load_send_session() is None


def test_nothing_stored_yields_none():
    assert session.load_send_session() is None


def test_files_that_disappeared_are_dropped(tmp_path):
    kept = tmp_path / "kept.txt"
    kept.write_text("x", encoding="utf-8")
    session.save_send_session("code-word-here", [str(kept), str(tmp_path / "gone.txt")])
    restored = session.load_send_session()
    assert restored is not None
    assert restored.paths == [str(kept)]


def test_a_session_whose_files_all_vanished_is_not_offered(tmp_path):
    session.save_send_session("code-word-here", [str(tmp_path / "gone.txt")])
    assert session.load_send_session() is None


def test_corrupt_session_file_is_ignored():
    session.session_path().write_text("{not json", encoding="utf-8")
    assert session.load_send_session() is None


def test_clearing_is_idempotent():
    session.clear_send_session()
    session.clear_send_session()
    assert session.load_send_session() is None
