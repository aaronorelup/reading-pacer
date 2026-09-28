"""READING_PACER_HOME must fully isolate data: no reading, migrating or deleting elsewhere."""

import importlib


def test_portable_mode_never_touches_legacy_save(tmp_path, monkeypatch):
    from reading_pacer import paths
    from reading_pacer.services import save_manager

    fake_repo = tmp_path / "repo"
    legacy = fake_repo / "saves" / "current.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"text": "old", "word_index": 3}', encoding="utf-8")
    monkeypatch.setattr(paths, "repo_root", lambda: str(fake_repo))
    monkeypatch.setenv("READING_PACER_HOME", str(tmp_path / "home"))
    importlib.reload(save_manager)

    assert save_manager.load_state() is None  # not migrated in
    save_manager.delete_save()
    assert legacy.exists()  # and never deleted


def test_portable_mode_uses_only_home_env(tmp_path, monkeypatch):
    from reading_pacer import config

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("THEME=latte\n", encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("READING_PACER_HOME", str(home))
    assert config.find_env() == str(home / ".env")
