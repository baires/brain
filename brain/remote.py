from dataclasses import dataclass
from pathlib import Path

import keyring
import tomli
import tomli_w

DEFAULT_CONFIG_PATH = Path.home() / ".brain" / "config.toml"

_KEYRING_SERVICE = "brain"


@dataclass
class RemoteConfig:
    name: str
    bucket: str
    prefix: str
    endpoint: str
    key_id: str | None
    secret: str | None


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomli.load(f)


def _save_toml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def add_remote(
    name: str,
    bucket: str,
    prefix: str,
    endpoint: str,
    key_id: str | None,
    secret: str | None,
) -> None:
    data = _load_toml(DEFAULT_CONFIG_PATH)
    data.setdefault("remote", {})[name] = {
        "bucket": bucket,
        "prefix": prefix,
        "endpoint": endpoint,
    }
    _save_toml(DEFAULT_CONFIG_PATH, data)

    if key_id and secret:
        keyring.set_password(_KEYRING_SERVICE, f"remote/{name}", f"{key_id}:{secret}")


def get_remote(name: str) -> RemoteConfig:
    data = _load_toml(DEFAULT_CONFIG_PATH)
    remotes = data.get("remote", {})
    if name not in remotes:
        raise KeyError(name)

    entry = remotes[name]
    raw = keyring.get_password(_KEYRING_SERVICE, f"remote/{name}")
    key_id, secret = None, None
    if raw:
        parts = raw.split(":", 1)
        if len(parts) == 2:
            key_id, secret = parts

    return RemoteConfig(
        name=name,
        bucket=entry["bucket"],
        prefix=entry.get("prefix", ""),
        endpoint=entry.get("endpoint", "https://s3.amazonaws.com"),
        key_id=key_id,
        secret=secret,
    )


def list_remotes() -> list[str]:
    data = _load_toml(DEFAULT_CONFIG_PATH)
    return list(data.get("remote", {}).keys())


def remove_remote(name: str) -> None:
    data = _load_toml(DEFAULT_CONFIG_PATH)
    remotes = data.get("remote", {})
    if name in remotes:
        del remotes[name]
        _save_toml(DEFAULT_CONFIG_PATH, data)
    keyring.delete_password(_KEYRING_SERVICE, f"remote/{name}")
