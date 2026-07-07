# Changelog

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
