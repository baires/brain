import pytest

import brain.remote as remote_mod
from brain.remote import RemoteConfig, add_remote, get_remote, list_remotes, remove_remote


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.toml"
    monkeypatch.setattr(remote_mod, "DEFAULT_CONFIG_PATH", config_file)
    return config_file


@pytest.fixture
def mock_keyring(monkeypatch):
    store = {}

    def fake_get(service, username):
        return store.get((service, username))

    def fake_set(service, username, password):
        store[(service, username)] = password

    def fake_delete(service, username):
        store.pop((service, username), None)

    monkeypatch.setattr(remote_mod.keyring, "get_password", fake_get)
    monkeypatch.setattr(remote_mod.keyring, "set_password", fake_set)
    monkeypatch.setattr(remote_mod.keyring, "delete_password", fake_delete)
    return store


def test_add_remote_saves_to_config_and_keyring(tmp_config, mock_keyring):
    add_remote(
        name="work",
        bucket="my-bucket",
        prefix="notes/",
        endpoint="https://s3.amazonaws.com",
        key_id="AKIAIOSFODNN7",
        secret="wJalrXUtnFEMI",
    )

    import tomli

    data = tomli.loads(tmp_config.read_text())
    assert data["remote"]["work"]["bucket"] == "my-bucket"
    assert data["remote"]["work"]["prefix"] == "notes/"
    assert data["remote"]["work"]["endpoint"] == "https://s3.amazonaws.com"

    creds = mock_keyring.get(("brain", "remote/work"))
    assert creds == "AKIAIOSFODNN7:wJalrXUtnFEMI"


def test_get_remote_retrieves_stored_remote(tmp_config, mock_keyring):
    add_remote("work", "my-bucket", "notes/", "https://s3.amazonaws.com", "KEYID", "SECRET")
    cfg = get_remote("work")

    assert isinstance(cfg, RemoteConfig)
    assert cfg.bucket == "my-bucket"
    assert cfg.prefix == "notes/"
    assert cfg.endpoint == "https://s3.amazonaws.com"
    assert cfg.key_id == "KEYID"
    assert cfg.secret == "SECRET"


def test_get_remote_raises_for_unknown_name(tmp_config, mock_keyring):
    with pytest.raises(KeyError, match="nope"):
        get_remote("nope")


def test_list_remotes_returns_all_names(tmp_config, mock_keyring):
    add_remote("work", "b1", "", "https://s3.amazonaws.com", "K1", "S1")
    add_remote("r2", "b2", "docs/", "https://r2.example.com", "K2", "S2")

    names = list_remotes()
    assert sorted(names) == ["r2", "work"]


def test_remove_remote_deletes_config_and_keyring(tmp_config, mock_keyring):
    add_remote("work", "my-bucket", "", "https://s3.amazonaws.com", "K", "S")
    remove_remote("work")

    assert "work" not in list_remotes()
    assert mock_keyring.get(("brain", "remote/work")) is None


def test_get_remote_no_credentials_returns_none(tmp_config, mock_keyring):
    add_remote("internal", "internal-bucket", "", "https://s3.amazonaws.com", None, None)
    cfg = get_remote("internal")

    assert cfg.key_id is None
    assert cfg.secret is None
