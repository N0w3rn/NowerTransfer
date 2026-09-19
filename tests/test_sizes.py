import pytest

from nowertransfer.paths import human_size, total_size


def test_a_single_file(tmp_path):
    payload = tmp_path / "a.bin"
    payload.write_bytes(b"x" * 1234)
    assert total_size([payload]) == 1234


def test_a_folder_is_walked(tmp_path):
    (tmp_path / "deep" / "deeper").mkdir(parents=True)
    (tmp_path / "a.bin").write_bytes(b"x" * 100)
    (tmp_path / "deep" / "b.bin").write_bytes(b"x" * 200)
    (tmp_path / "deep" / "deeper" / "c.bin").write_bytes(b"x" * 300)
    assert total_size([tmp_path]) == 600


def test_a_missing_path_does_not_raise(tmp_path):
    assert total_size([tmp_path / "gone.bin"]) == 0


def test_nothing_is_zero():
    assert total_size([]) == 0


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (999, "999 B"),
        (1024, "1.0 kB"),
        (1536, "1.5 kB"),
        (150 * 1024, "150 kB"),
        (5 * 1024**2, "5.0 MB"),
        (int(4.2 * 1024**3), "4.2 GB"),
        (3 * 1024**4, "3.0 TB"),
        (9000 * 1024**4, "9000 TB"),
    ],
)
def test_human_size(size, expected):
    assert human_size(size) == expected
