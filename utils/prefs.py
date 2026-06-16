"""Lightweight user preferences (JSON file in the app data dir).

Currently just the theme choice ("light" / "dark" / None = follow OS). Kept
separate from the credentials DB so a missing/corrupt prefs file can never
affect login state.
"""

from __future__ import annotations

import json
import os

from utils.db import get_data_dir

_PATH = os.path.join(get_data_dir(), "prefs.json")


def _load() -> dict:
    try:
        with open(_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    try:
        with open(_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def get_theme_pref() -> str | None:
    """Return the saved theme ("light"/"dark"), or None to follow the OS."""
    value = _load().get("theme")
    return value if value in ("light", "dark") else None


def set_theme_pref(mode: str) -> None:
    data = _load()
    data["theme"] = mode
    _save(data)
