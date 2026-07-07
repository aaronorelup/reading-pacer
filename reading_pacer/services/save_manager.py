"""
save_manager.py — Persists reading state across sessions.

Saves to <user data dir>/saves/current.json:
  - text content
  - current word index
  - WPM setting
  - actual elapsed time
  - font size

Older versions saved to <repo>/saves/current.json; that file is migrated
automatically the first time the new location is used.
"""

import json
import os
import shutil

from reading_pacer import paths


def _save_path() -> str:
    return os.path.join(paths.user_data_dir(), "saves", "current.json")


def _legacy_save_path() -> str:
    return os.path.join(paths.repo_root(), "saves", "current.json")


def _migrate_legacy():
    """Copy a pre-1.0 save into the user data directory (once)."""
    new, old = _save_path(), _legacy_save_path()
    if os.path.exists(new) or not os.path.exists(old):
        return
    try:
        paths.ensure_dir(os.path.dirname(new))
        shutil.copy2(old, new)
    except OSError:
        pass


def has_save() -> bool:
    _migrate_legacy()
    return os.path.exists(_save_path())


def load_state() -> dict | None:
    """Load saved reading state; None if no save exists."""
    _migrate_legacy()
    try:
        with open(_save_path(), encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("text") else None
    except (json.JSONDecodeError, OSError):
        return None


def save_state(text: str, word_index: int, wpm: int, actual_elapsed: float,
               font_size: int = 17):
    """Save current reading state."""
    path = _save_path()
    paths.ensure_dir(os.path.dirname(path))
    data = {
        "text": text,
        "word_index": word_index,
        "wpm": wpm,
        "actual_elapsed": actual_elapsed,
        "font_size": font_size,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def delete_save():
    """Remove the save file (called on New Text)."""
    for p in (_save_path(), _legacy_save_path()):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
