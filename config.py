"""
config — Application configuration persistence.

Stores user settings in ~/.macsystemmonitor/config.json so the app
can read them regardless of how it was launched (Finder, terminal, etc.).
This avoids the macOS limitation where GUI apps don't inherit shell
environment variables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _config_dir() -> Path:
    """Return the configuration directory, creating it if needed."""
    path = Path.home() / ".macsystemmonitor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_file() -> Path:
    """Return the path to the JSON config file."""
    return _config_dir() / "config.json"


def _read_config() -> dict[str, str]:
    """Read the full config dictionary from disk."""
    path = _config_file()
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_config(data: dict[str, str]) -> None:
    """Write the config dictionary to disk."""
    path = _config_file()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def get_api_key() -> str | None:
    """Return the stored DeepSeek API key, or None if not configured.

    Priority:
    1. ``DEEPSEEK_API_KEY`` environment variable (terminal launch)
    2. Config file (Finder / GUI launch)
    """
    env_val = os.getenv("DEEPSEEK_API_KEY")
    if env_val:
        return env_val
    return _read_config().get("deepseek_api_key")


def set_api_key(key: str) -> None:
    """Persist the DeepSeek API key to the config file."""
    key = key.strip()
    data = _read_config()
    data["deepseek_api_key"] = key
    _write_config(data)


def delete_api_key() -> None:
    """Remove the stored API key."""
    data = _read_config()
    data.pop("deepseek_api_key", None)
    _write_config(data)
