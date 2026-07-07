"""Tests for reading-state persistence (isolated via READING_PACER_HOME)."""

import pytest

from reading_pacer.services import save_manager


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("READING_PACER_HOME", str(tmp_path))
    # Keep tests hermetic: no legacy save to migrate
    monkeypatch.setattr(save_manager, "_legacy_save_path",
                        lambda: str(tmp_path / "legacy" / "current.json"))
    yield tmp_path


def test_no_save_initially():
    assert not save_manager.has_save()
    assert save_manager.load_state() is None


def test_save_and_load_roundtrip():
    save_manager.save_state("hello world " * 10, word_index=7, wpm=300,
                            actual_elapsed=12.5, font_size=19)
    assert save_manager.has_save()
    state = save_manager.load_state()
    assert state["word_index"] == 7
    assert state["wpm"] == 300
    assert state["actual_elapsed"] == 12.5
    assert state["font_size"] == 19
    assert state["text"].startswith("hello world")


def test_delete_save():
    save_manager.save_state("text", 0, 250, 0.0)
    save_manager.delete_save()
    assert not save_manager.has_save()
    save_manager.delete_save()  # deleting twice is fine


def test_corrupt_save_returns_none(isolated_home):
    path = isolated_home / "saves" / "current.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert save_manager.load_state() is None


def test_legacy_save_is_migrated(isolated_home, monkeypatch):
    legacy = isolated_home / "old" / "current.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"text": "legacy text", "word_index": 3}', encoding="utf-8")
    monkeypatch.setattr(save_manager, "_legacy_save_path", lambda: str(legacy))

    state = save_manager.load_state()
    assert state is not None
    assert state["text"] == "legacy text"
    # migrated copy now lives in the new location
    assert (isolated_home / "saves" / "current.json").exists()
