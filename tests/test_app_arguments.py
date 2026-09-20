"""Paths handed to the app on the command line.

This is the Explorer context menu's whole interface: Windows starts
the app with the selected path as an argument.
"""

from __future__ import annotations

from nowertransfer.app import preselected


def test_an_existing_file_is_taken_as_a_selection(tmp_path):
    chosen = tmp_path / "holiday.zip"
    chosen.write_text("x", encoding="utf-8")
    assert preselected([str(chosen)]) == [chosen]


def test_a_folder_counts_too(tmp_path):
    folder = tmp_path / "pictures"
    folder.mkdir()
    assert preselected([str(folder)]) == [folder]


def test_several_paths_keep_their_order(tmp_path):
    first, second = tmp_path / "a.txt", tmp_path / "b.txt"
    for path in (first, second):
        path.write_text("x", encoding="utf-8")
    assert preselected([str(first), str(second)]) == [first, second]


def test_nothing_on_the_command_line_selects_nothing():
    assert preselected([]) == []


def test_a_path_that_is_not_there_is_ignored(tmp_path):
    # A stale shortcut or a renamed file must not stop the app
    # starting; there is no console to complain to anyway.
    assert preselected([str(tmp_path / "gone.txt")]) == []


def test_flags_are_not_paths():
    assert preselected(["--version", "-v"]) == []


def test_a_flag_beside_a_file_leaves_the_file(tmp_path):
    chosen = tmp_path / "a.txt"
    chosen.write_text("x", encoding="utf-8")
    assert preselected(["--version", str(chosen)]) == [chosen]
