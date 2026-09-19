import sys

import nowertransfer


def test_a_source_checkout_reports_the_committed_version(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert nowertransfer.resolve_version() == nowertransfer.FALLBACK_VERSION


def test_a_build_reports_the_tag_it_was_made_from(tmp_path, monkeypatch):
    (tmp_path / nowertransfer.VERSION_STAMP).write_text("1.4.2\n", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert nowertransfer.resolve_version() == "1.4.2"


def test_a_build_without_a_stamp_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert nowertransfer.resolve_version() == nowertransfer.FALLBACK_VERSION


def test_an_empty_stamp_falls_back(tmp_path, monkeypatch):
    (tmp_path / nowertransfer.VERSION_STAMP).write_text("  \n", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert nowertransfer.resolve_version() == nowertransfer.FALLBACK_VERSION


def test_the_packaging_metadata_reads_the_same_line():
    # pyproject.toml takes its version from FALLBACK_VERSION, so the two
    # can never drift apart. Guard the line hatchling matches on.
    import re
    from pathlib import Path

    source = Path(nowertransfer.__file__).read_text(encoding="utf-8")
    assert re.search(r'FALLBACK_VERSION = "(?P<version>[^"]+)"', source)
