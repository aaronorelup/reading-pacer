"""Tests for session history recording (isolated via READING_PACER_HOME)."""

import pytest

from reading_pacer.services import stats_manager


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("READING_PACER_HOME", str(tmp_path))
    yield tmp_path


def test_empty_history():
    assert stats_manager.load_sessions() == []
    s = stats_manager.summary()
    assert s["sessions"] == 0
    assert s["avg_wpm"] is None
    assert s["avg_score"] is None


def test_record_and_summary():
    stats_manager.record_session(words=500, seconds=120.0, wpm=250.0,
                                 preview="once upon a time")
    stats_manager.record_session(words=300, seconds=60.0, wpm=300.0,
                                 quiz_correct=7, quiz_total=8)
    sessions = stats_manager.load_sessions()
    assert len(sessions) == 2
    assert sessions[0]["preview"] == "once upon a time"
    assert sessions[1]["quiz_total"] == 8

    s = stats_manager.summary()
    assert s["sessions"] == 2
    assert s["total_words"] == 800
    assert s["total_seconds"] == 180.0
    assert s["avg_wpm"] == 275.0
    assert s["avg_score"] == pytest.approx(87.5)


def test_update_session_adds_quiz_results():
    idx = stats_manager.record_session(words=400, seconds=90.0, wpm=266.7)
    stats_manager.update_session(idx, quiz_correct=5, quiz_total=8)
    sessions = stats_manager.load_sessions()
    assert sessions[idx]["quiz_correct"] == 5
    assert sessions[idx]["words"] == 400


def test_update_out_of_range_is_ignored():
    stats_manager.update_session(42, quiz_correct=1)  # no crash
    assert stats_manager.load_sessions() == []


def test_wpm_none_is_allowed():
    stats_manager.record_session(words=200, seconds=5.0, wpm=None,
                                 quiz_correct=3, quiz_total=8)
    s = stats_manager.summary()
    assert s["avg_wpm"] is None
    assert s["avg_score"] == pytest.approx(37.5)


def test_history_is_capped(monkeypatch):
    monkeypatch.setattr(stats_manager, "MAX_SESSIONS", 5)
    for i in range(8):
        stats_manager.record_session(words=i, seconds=1.0, wpm=100.0)
    sessions = stats_manager.load_sessions()
    assert len(sessions) == 5
    assert sessions[-1]["words"] == 7  # newest kept
