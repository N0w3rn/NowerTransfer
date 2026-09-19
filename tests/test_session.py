import pytest

from nowertransfer import paths, session


@pytest.fixture(autouse=True)
def isolated_session(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(session, "user_config_dir", lambda: tmp_path)


def test_round_trip(tmp_path):
    payload = tmp_path / "payload.txt"
    payload.write_text("hi", encoding="utf-8")

    session.save_send_session("falke-wolke-tiger-nebel-83", [str(payload)])
    restored = session.load_send_session()

    assert restored is not None
    assert restored.code == "falke-wolke-tiger-nebel-83"
    assert restored.paths == [str(payload)]


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
