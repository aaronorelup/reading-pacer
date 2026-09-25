# Changelog

## 1.1.0 — 2026-09-25

### Added
- **Windows installer**: per-user install with no admin prompt, Start Menu and
  optional desktop shortcut, and an uninstaller in Settings → Apps that asks
  whether to keep your settings and reading history.
- **Automatic updates**: the app checks GitHub for a new version at startup.
  On Windows it downloads the new installer, checks it against GitHub's
  SHA-256 digest, and upgrades and restarts in one click. Turn it off, or check
  manually, in Settings → Updates.
- **macOS app**: a universal (Apple Silicon + Intel) `.dmg` for macOS 11+.
- **Portable Windows zip** for people who'd rather not install.
- **Error reporting**: unexpected errors are logged to
  `logs/reading-pacer.log` in your data folder, with a friendly window that
  can copy the details or open a pre-filled GitHub issue.
- `--self-test` / `--version` command-line options. CI uses the self-test to
  install and check the real app on fresh Windows, macOS and Linux machines
  for every change.

### Fixed
- Buttons on macOS showed as grey system buttons with unreadable text; they
  now match the theme.
- Scrolling the Settings screen with the mouse wheel did nothing on macOS and
  Linux.
- Cmd+S / Cmd+R now work on macOS.
- Pressing Save and then New Text within a second and a half raised an error.
- Closing the window could lose up to 5 seconds of reading progress; it is
  now saved on close.
- HTTPS (AI quizzes and update checks) now works in the macOS app, which
  doesn't use the system certificate store.
- Portable/test mode (`READING_PACER_HOME`) could read, and on New Text
  delete, a pre-1.0 save file in the source folder. It now only ever uses its
  own folder.

### Changed
- The Windows app is now a folder install instead of a single self-extracting
  exe, so it starts faster and antivirus software is less likely to flag it.

## 1.0.0 — 2026-07-07

First public release. 🎉

### Added
- Installable package: `pip install .` gives you a `reading-pacer` command
  (or run `python -m reading_pacer`).
- **DeepSeek API support out of the box** — plus provider presets for OpenAI,
  OpenRouter, Ollama, and LM Studio, or any custom OpenAI-compatible endpoint.
  Local servers work without an API key.
- **Test Connection** button in Settings with friendly, specific error messages
  (invalid key, no balance, rate limit, wrong URL, network down…).
- **Reading stats**: sessions are recorded when you finish a text or complete a
  quiz; a new 📊 Stats screen shows totals, a WPM + comprehension trend chart,
  and recent sessions.
- **Quiz review**: after a quiz, see every question you missed with the correct
  answer. Question count is configurable (3–12).
- **Open File…** button to load `.txt` / `.md` files.
- **Latte light theme** alongside the Mocha dark theme.
- Passage generation now works with local GGUF models too (previously API-only),
  and the local model stays loaded between requests.
- User data (config, save, stats) now lives in a platform-appropriate directory
  (`%APPDATA%\ReadingPacer`, `~/Library/Application Support/ReadingPacer`, or
  `~/.local/share/reading-pacer`); set `READING_PACER_HOME` to override.
  Old saves are migrated automatically.
- Tests and CI.

### Fixed
- LLM callbacks previously touched Tk widgets from a worker thread; they are
  now marshalled onto the main loop.
- Global keyboard shortcuts (space, arrows, Ctrl+S…) no longer fire on hidden
  or destroyed reading screens (e.g. while typing in Settings).
- Word-position indexing is now O(n) instead of O(n²) — long texts load fast.
- Windows/old-Mac line endings are normalized so the pacing arrow can't drift.
- JSON question output is requested in strict JSON mode where supported, with
  automatic fallback for servers that reject `response_format`.
