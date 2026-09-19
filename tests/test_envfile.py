import pytest

from nowertransfer.envfile import parse_env, read_env_file


def test_plain_assignments():
    assert parse_env("RELAY_HOST=relay.example.com:9009\nRELAY_PASSWORD=hunter2") == {
        "RELAY_HOST": "relay.example.com:9009",
        "RELAY_PASSWORD": "hunter2",
    }


def test_comments_and_blank_lines_are_skipped():
    text = "# a comment\n\n  \nRELAY_HOST=x\n"
    assert parse_env(text) == {"RELAY_HOST": "x"}


def test_surrounding_whitespace_is_trimmed():
    assert parse_env("  RELAY_HOST  =  x  ") == {"RELAY_HOST": "x"}


def test_export_prefix_is_accepted():
    assert parse_env("export RELAY_HOST=x") == {"RELAY_HOST": "x"}


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('RELAY_PASSWORD="a b"', "a b"),
        ("RELAY_PASSWORD='a b'", "a b"),
        # A '#' only starts a comment outside quotes.
        ('RELAY_PASSWORD="pw #1"', "pw #1"),
        ("RELAY_PASSWORD=pw # trailing note", "pw"),
        # Hashes without a preceding space stay part of the value.
        ("RELAY_PASSWORD=pw#1", "pw#1"),
        ('RELAY_PASSWORD="say \\"hi\\""', 'say "hi"'),
        ("RELAY_PASSWORD=", ""),
    ],
)
def test_value_quoting_and_comments(line, expected):
    assert parse_env(line)["RELAY_PASSWORD"] == expected


def test_values_may_contain_equals_signs():
    assert parse_env("RELAY_PASSWORD=a=b=c") == {"RELAY_PASSWORD": "a=b=c"}


def test_lines_without_an_equals_sign_are_ignored():
    assert parse_env("nonsense\nRELAY_HOST=x") == {"RELAY_HOST": "x"}


def test_missing_file_is_empty(tmp_path):
    assert read_env_file(tmp_path / "nope.env") == {}


def test_reading_a_real_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text("RELAY_HOST=x\n", encoding="utf-8")
    assert read_env_file(path) == {"RELAY_HOST": "x"}
