"""
stats_manager.py — Records reading sessions so progress is visible over time.

A session is recorded when a text is finished or a comprehension quiz is
completed. Stored as JSON at <user data dir>/stats.json:

  {"sessions": [{"ts": iso8601, "words": int, "seconds": float,
                 "wpm": float|None, "quiz_correct": int|None,
                 "quiz_total": int|None, "preview": str}, ...]}
"""

import json
import os
from datetime import datetime

from reading_pacer import paths

MAX_SESSIONS = 500


def _stats_path() -> str:
    return os.path.join(paths.user_data_dir(), "stats.json")


def load_sessions() -> list[dict]:
    """All recorded sessions, oldest first."""
    try:
        with open(_stats_path(), encoding="utf-8-sig") as f:
            data = json.load(f)
        sessions = data.get("sessions", [])
        return sessions if isinstance(sessions, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write(sessions: list[dict]):
    path = _stats_path()
    paths.ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sessions": sessions[-MAX_SESSIONS:]}, f, indent=1)


def record_session(words: int, seconds: float, wpm: float | None,
                   quiz_correct: int | None = None, quiz_total: int | None = None,
                   preview: str = "") -> int:
    """Append a session; returns its index for later update_session calls."""
    sessions = load_sessions()
    sessions.append({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "words": int(words),
        "seconds": round(float(seconds), 1),
        "wpm": round(wpm, 1) if wpm else None,
        "quiz_correct": quiz_correct,
        "quiz_total": quiz_total,
        "preview": preview[:80],
    })
    _write(sessions)
    return len(sessions) - 1


def update_session(index: int, **fields):
    """Update an existing session record (e.g. add quiz results after reading)."""
    sessions = load_sessions()
    if 0 <= index < len(sessions):
        sessions[index].update(fields)
        _write(sessions)


def summary() -> dict:
    """Aggregate totals for the stats screen."""
    sessions = load_sessions()
    wpms = [s["wpm"] for s in sessions if s.get("wpm")]
    scored = [(s["quiz_correct"], s["quiz_total"]) for s in sessions
              if s.get("quiz_total")]
    return {
        "sessions": len(sessions),
        "total_words": sum(s.get("words", 0) for s in sessions),
        "total_seconds": sum(s.get("seconds", 0) for s in sessions),
        "avg_wpm": (sum(wpms) / len(wpms)) if wpms else None,
        "avg_score": (sum(c for c, _ in scored) / max(sum(t for _, t in scored), 1) * 100)
                     if scored else None,
    }
