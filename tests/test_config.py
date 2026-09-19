import pytest

from nowertransfer import config, secretstore


@pytest.fixture
def layers(tmp_path, monkeypatch):
    """Redirect every config layer into a temporary directory."""
    paths = {
        "env": tmp_path / ".env",
        "baked": tmp_path / "relay.toml",
        "portable": tmp_path / "nowertransfer.toml",
        "user": tmp_path / "user" / "config.toml",
    }
    monkeypatch.setattr(config, "env_file_path", lambda: paths["env"])
    monkeypatch.setattr(config, "baked_config_path", lambda: paths["baked"])
    monkeypatch.setattr(config, "portable_config_path", lambda: paths["portable"])
    monkeypatch.setattr(config, "user_config_path", lambda: paths["user"])
    monkeypatch.setattr(config, "is_frozen", lambda: False)
    for variable in (
        config.ENV_RELAY_HOST,
        config.ENV_RELAY_PASSWORD,
        config.ENV_LANGUAGE,
    ):
        monkeypatch.delenv(variable, raising=False)
    return paths


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ----------------------------------------------------------------------
#  Layering
# ----------------------------------------------------------------------
def test_missing_layers_are_not_an_error(layers):
    settings = config.load_settings()
    assert settings.relay_host == ""
    assert settings.is_configured is False
    # A download directory is always available.
    assert settings.download_dir


def test_a_source_checkout_is_configured_by_its_env_file(layers):
    write(layers["env"], "RELAY_HOST=dev.example.com:9009\nRELAY_PASSWORD=devpass\n")
    settings = config.load_settings()
    assert settings.relay_host == "dev.example.com:9009"
    assert settings.relay_password == "devpass"
    assert settings.source_of("relay_host") is config.Source.BUILD


def test_a_build_is_configured_by_its_baked_file(layers, monkeypatch):
    # The same layer, read from the file build.py put inside the binary.
    monkeypatch.setattr(config, "is_frozen", lambda: True)
    write(layers["env"], "RELAY_HOST=should-be-ignored:9009\n")
    write(layers["baked"], 'relay_host = "baked:9009"\n')
    settings = config.load_settings()
    assert settings.relay_host == "baked:9009"
    assert settings.source_of("relay_host") is config.Source.BUILD


def test_env_file_only_exposes_its_documented_keys(layers):
    write(layers["env"], "RELAY_HOST=dev:9009\nPATH=/nope\nNOWERTRANSFER_RELAY=x\n")
    assert config.build_layer() == {"relay_host": "dev:9009"}


def test_later_layers_win(layers, monkeypatch):
    write(layers["env"], "RELAY_HOST=dev:9009\n")
    write(layers["portable"], 'relay_host = "portable:9009"\n')
    write(layers["user"], 'relay_host = "user:9009"\n')
    assert config.load_settings().relay_host == "user:9009"

    monkeypatch.setenv(config.ENV_RELAY_HOST, "env:9009")
    settings = config.load_settings()
    assert settings.relay_host == "env:9009"
    assert settings.source_of("relay_host") is config.Source.ENVIRONMENT


def test_layers_merge_per_key(layers):
    write(layers["env"], "RELAY_HOST=dev:9009\nRELAY_PASSWORD=devpass\n")
    write(layers["user"], 'language = "de"\n')
    settings = config.load_settings()
    assert settings.relay_host == "dev:9009"
    assert settings.relay_password == "devpass"
    assert settings.language == "de"


def test_broken_config_file_is_ignored(layers):
    write(layers["user"], "this is not = = toml")
    write(layers["env"], "RELAY_HOST=dev:9009\n")
    assert config.load_settings().relay_host == "dev:9009"


def test_unknown_keys_are_dropped(layers):
    write(layers["user"], 'relay_host = "user:9009"\nsomething_else = "x"\n')
    assert config.read_config_file(layers["user"]) == {"relay_host": "user:9009"}


# ----------------------------------------------------------------------
#  Saving
# ----------------------------------------------------------------------
def test_saving_does_not_copy_a_baked_secret_into_plaintext(layers):
    write(layers["env"], "RELAY_HOST=dev:9009\nRELAY_PASSWORD=secret\n")
    settings = config.load_settings()
    settings.language = "de"

    config.save_settings(settings)

    stored = config.read_config_file(layers["user"])
    assert "relay_password" not in stored
    assert "relay_host" not in stored
    assert stored["language"] == "de"


def test_saving_persists_changed_values(layers):
    write(layers["env"], "RELAY_HOST=dev:9009\n")
    settings = config.with_relay(config.load_settings(), "other.example.com", "pw")
    config.save_settings(settings)

    reloaded = config.load_settings()
    assert reloaded.relay_host == "other.example.com:9009"
    assert reloaded.relay_password == "pw"
    assert reloaded.source_of("relay_host") is config.Source.USER


def test_the_saved_relay_password_is_not_in_the_clear(layers):
    settings = config.with_relay(config.load_settings(), "r.example.com", "hunter2")
    config.save_settings(settings)

    on_disk = layers["user"].read_text(encoding="utf-8")
    assert "hunter2" not in on_disk or not secretstore.is_encrypting()
    assert config.load_settings().relay_password == "hunter2"


def test_a_password_from_another_machine_is_dropped_not_shown(layers):
    write(layers["env"], "RELAY_HOST=dev:9009\nRELAY_PASSWORD=frombuild\n")
    # A dpapi blob this account cannot decrypt, e.g. a copied config.
    write(
        layers["user"],
        'relay_password = "dpapi:AQAAANCMnd8BFdERjHoAwE/Cl+sAAAAA"\n',
    )
    settings = config.load_settings()
    assert settings.relay_password == "frombuild"
    assert settings.source_of("relay_password") is config.Source.BUILD


def test_a_default_is_not_saved_as_though_it_were_chosen(layers):
    # load_settings fills in a download directory. Saving used to write
    # that back, so the config recorded a path the user never picked.
    config.save_settings(config.load_settings())
    assert "download_dir" not in config.read_config_file(layers["user"])


def test_a_chosen_download_directory_is_saved(layers, tmp_path):
    settings = config.load_settings()
    settings.download_dir = str(tmp_path / "elsewhere")
    config.save_settings(settings)

    assert config.load_settings().download_dir == str(tmp_path / "elsewhere")


def test_saved_file_round_trips_awkward_characters(layers, tmp_path):
    settings = config.with_relay(
        config.load_settings(), "relay.example.com", 'a"b\\c\td'
    )
    config.save_settings(settings)
    assert config.load_settings().relay_password == 'a"b\\c\td'


# ----------------------------------------------------------------------
#  Relay endpoint
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("relay.example.com", "relay.example.com:9009"),
        ("relay.example.com:9100", "relay.example.com:9100"),
        ("  relay.example.com  ", "relay.example.com:9009"),
        ("https://relay.example.com/", "relay.example.com:9009"),
        ("tcp://10.0.0.5", "10.0.0.5:9009"),
        ("10.0.0.5:9009", "10.0.0.5:9009"),
        ("::1", "[::1]:9009"),
        ("[::1]:9009", "[::1]:9009"),
        ("[::1]", "[::1]:9009"),
        ("", ""),
    ],
)
def test_relay_host_normalisation(typed, expected):
    assert config.normalise_relay_host(typed) == expected


# ----------------------------------------------------------------------
#  Relay mode
# ----------------------------------------------------------------------
def test_the_default_keeps_everything_on_your_own_relay(layers):
    write(layers["env"], "RELAY_HOST=dev:9009\n")
    settings = config.load_settings()
    assert settings.mode is config.RelayMode.OWN
    assert settings.allows_public_fallback is False


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("own", config.RelayMode.OWN),
        ("fallback", config.RelayMode.FALLBACK),
        ("public", config.RelayMode.PUBLIC),
        ("  PUBLIC  ", config.RelayMode.PUBLIC),
        # A hand-edited config must not crash the app, and must not
        # silently end up on someone else's relay.
        ("nonsense", config.RelayMode.OWN),
        ("", config.RelayMode.OWN),
    ],
)
def test_relay_mode_parsing(stored, expected):
    assert config.RelayMode.parse(stored) is expected


def test_the_public_relay_needs_no_address(layers):
    write(layers["env"], "RELAY_MODE=public\n")
    settings = config.load_settings()
    assert settings.relay_host == ""
    assert settings.is_configured is True


def test_public_mode_ignores_a_stored_address(layers):
    # The settings screen keeps the address so switching back is easy.
    # It must not win over the mode the user actually chose.
    write(layers["env"], "RELAY_HOST=mine:9009\nRELAY_PASSWORD=pw\n")
    write(layers["user"], 'relay_mode = "public"\n')
    settings = config.load_settings()

    assert settings.relay_host == "mine:9009"  # still remembered
    assert settings.relay.is_set is False  # but not used
    assert settings.relay.host == ""


def test_switching_back_from_public_restores_the_relay(layers):
    write(layers["env"], "RELAY_HOST=mine:9009\nRELAY_PASSWORD=pw\n")
    write(layers["user"], 'relay_mode = "own"\n')
    settings = config.load_settings()
    assert settings.relay.host == "mine:9009"
    assert settings.relay.croc_password() == "pw"


def test_own_mode_without_an_address_is_not_configured(layers):
    assert config.load_settings().is_configured is False


def test_fallback_requires_an_address_to_fall_back_from(layers):
    write(layers["env"], "RELAY_MODE=fallback\n")
    assert config.load_settings().allows_public_fallback is False

    write(layers["env"], "RELAY_MODE=fallback\nRELAY_HOST=dev:9009\n")
    assert config.load_settings().allows_public_fallback is True


def test_relay_mode_can_be_baked_in_and_overridden(layers, monkeypatch):
    write(layers["env"], "RELAY_HOST=dev:9009\nRELAY_MODE=fallback\n")
    assert config.load_settings().mode is config.RelayMode.FALLBACK

    monkeypatch.setenv(config.ENV_RELAY_MODE, "own")
    assert config.load_settings().mode is config.RelayMode.OWN


def test_empty_relay_password_falls_back_to_crocs_default():
    endpoint = config.RelayEndpoint("relay.example.com:9009")
    assert endpoint.croc_password() == config.CROC_DEFAULT_RELAY_PASSWORD


def test_relay_password_is_used_when_set():
    endpoint = config.RelayEndpoint("relay.example.com:9009", "hunter2")
    assert endpoint.croc_password() == "hunter2"
