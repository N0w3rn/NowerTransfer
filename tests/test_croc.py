from nowertransfer import croc


def test_the_bundled_binary_is_preferred():
    # Its checksum was verified at build time. A binary next to the .exe
    # is whatever anyone who can write to that directory put there.
    order = list(croc.candidate_paths())
    from nowertransfer.paths import bundle_dir, executable_dir

    assert order[0] == bundle_dir() / croc.BINARY_NAME
    assert order.index(executable_dir() / croc.BINARY_NAME) == len(order) - 1


def test_every_candidate_is_named_after_the_platform():
    assert all(path.name == croc.BINARY_NAME for path in croc.candidate_paths())


def test_nothing_found_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(croc, "candidate_paths", lambda: iter([tmp_path / "nope"]))
    monkeypatch.setattr(croc.shutil, "which", lambda _name: None)
    assert croc.find_croc() is None


def test_an_existing_candidate_wins_over_path(monkeypatch, tmp_path):
    present = tmp_path / croc.BINARY_NAME
    present.write_bytes(b"")
    monkeypatch.setattr(croc, "candidate_paths", lambda: iter([present]))
    monkeypatch.setattr(croc.shutil, "which", lambda _name: "/usr/bin/croc")
    assert croc.find_croc() == present


def test_path_is_the_last_resort(monkeypatch, tmp_path):
    monkeypatch.setattr(croc, "candidate_paths", lambda: iter([tmp_path / "nope"]))
    monkeypatch.setattr(croc.shutil, "which", lambda _name: str(tmp_path / "onpath"))
    assert croc.find_croc() == tmp_path / "onpath"
