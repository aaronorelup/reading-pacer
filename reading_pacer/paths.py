"""
paths.py — Platform-appropriate locations for user data (config, saves, stats).

All user data lives in one directory:
  Windows:  %APPDATA%\\ReadingPacer
  macOS:    ~/Library/Application Support/ReadingPacer
  Linux:    $XDG_DATA_HOME/reading-pacer  (or ~/.local/share/reading-pacer)

Set the READING_PACER_HOME environment variable to override (portable mode).
"""

import os
import sys

APP_NAME = "ReadingPacer"


def user_data_dir() -> str:
    """Directory for config, saves, and stats. Not created until needed."""
    override = os.environ.get("READING_PACER_HOME")
    if override:
        return override
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    if sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "reading-pacer")


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def repo_root() -> str:
    """Parent of the package directory — the repo root in a source checkout."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
