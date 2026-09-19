import re
import sys
from pathlib import Path

import nowertransfer


def test_a_source_checkout_marks_itself_as_such(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert nowertransfer.resolve_version() == f"{nowertransfer.VERSION}-dev"


def test_a_build_reports_the_tag_it_was_made_from(tmp_path, monkeypatch):
    (tmp_path / nowertransfer.VERSION_STAMP).write_text("1.4.2\n", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert nowertransfer.resolve_version() == "1.4.2"


def test_an_unstamped_build_admits_it_does_not_know(tmp_path, monkeypatch):
    # Better than displaying a release number the binary cannot vouch for.
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert nowertransfer.resolve_version() == nowertransfer.UNKNOWN_LABEL


def test_an_empty_stamp_counts_as_unstamped(tmp_path, monkeypatch):
    (tmp_path / nowertransfer.VERSION_STAMP).write_text("  \n", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert nowertransfer.resolve_version() == nowertransfer.UNKNOWN_LABEL


def test_the_packaging_metadata_reads_the_same_line():
    # pyproject.toml takes its version from VERSION with this pattern, so
    # the two cannot drift apart. Guard the line it matches on.
    source = Path(nowertransfer.__file__).read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "(?P<version>[^"]+)"', source, re.MULTILINE)
    assert match and match.group("version") == nowertransfer.VERSION


def test_the_version_is_a_usable_release_number():
    # It ends up in packaging metadata, so it has to look like a version.
    assert re.fullmatch(r"\d+\.\d+\.\d+", nowertransfer.VERSION)
