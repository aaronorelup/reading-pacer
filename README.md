# Reading Pacer

**Train yourself to read faster *without* losing comprehension.**

A distraction-free desktop reading pacer with AI-generated comprehension quizzes.
Paste any text, set your words-per-minute, and a smooth arrow glides along the
words to keep your eyes moving. When you're done, take a quiz generated from
*exactly what you just read* — so you know whether that speed actually stuck.

![CI](https://github.com/Bloodtailor/reading-pacer/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

![Reading Pacer screenshot](docs/screenshot-reading.png)

<details>
<summary>More screenshots</summary>

The landing screen — paste text, open a file, or generate a passage:

![Main screen](docs/screenshot-main.png)

</details>

## Why a pacer?

Most people read far below the speed they're capable of, because their eyes
wander and re-read. A pacer gives your eyes a target to chase. But raw speed is
meaningless if nothing sinks in — that's why Reading Pacer pairs the pacer with
**progressive-difficulty comprehension quizzes** (question 1 is easy surface
recall; the last one targets a detail buried deep in the passage). Track both
numbers over time and find *your* optimal speed.

## Features

- **Smooth pacing arrow** that slides word-to-word at your chosen WPM, with
  line highlighting, auto-scroll, click-to-jump, and a scrubbable progress bar
- **Actual-speed tracking** — see the WPM you really read at, not just the dial
- **AI comprehension quizzes** on any text, with a review of what you missed
- **AI passage generation** — pick a topic, style, difficulty, and length
- **Reading stats** 📊 — words read, time, and a speed + comprehension trend chart
- **Save & resume** — close the app mid-chapter, pick up where you left off
- **Open files** (`.txt`, `.md`) or paste anything
- **Catppuccin themes** — Mocha (dark) and Latte (light)
- **Zero required dependencies** — pure Python standard library (tkinter)

## Install

### Windows — just download it

Grab **`ReadingPacer.exe`** from the [latest release](https://github.com/Bloodtailor/reading-pacer/releases/latest) —
no Python needed. Put it anywhere (e.g. a `Programs` folder), run it, and pin it
to your taskbar. Windows SmartScreen may warn because the exe is unsigned —
click *More info → Run anyway*.

You can rebuild it yourself from source: `powershell -File packaging\build-exe.ps1`.

### From source (any OS)

Requires Python 3.10+ with tkinter (included in the standard python.org installers).

```bash
git clone https://github.com/Bloodtailor/reading-pacer.git
cd reading-pacer
pip install .
reading-pacer
```

Or run straight from the checkout without installing:

```bash
python -m reading_pacer
```

> **Optional — local models:** to run quizzes fully offline with a GGUF model,
> `pip install ".[local]"` (installs `llama-cpp-python`).

## Setting up the AI (optional)

The pacer itself works with no setup at all. Quizzes and passage generation
need a language model — **either** an API key **or** a local model:

### Option A: DeepSeek API (recommended — cheap and good)

1. Create a key at [platform.deepseek.com](https://platform.deepseek.com)
2. Open **⚙ Settings** in the app, paste the key, click **⚡ Test Connection**
3. Done — DeepSeek is the default provider

A typical quiz costs a fraction of a cent.

### Option B: any OpenAI-compatible API

Pick a preset in Settings or enter a custom endpoint:

| Provider | Notes |
|---|---|
| **DeepSeek** | Default. `deepseek-chat` |
| **OpenAI** | e.g. `gpt-4o-mini` |
| **OpenRouter** | Hundreds of models, one key |
| **Ollama** | Local server — no API key needed |
| **LM Studio** | Local server — no API key needed |

### Option C: local GGUF model

Install the `[local]` extra, then point Settings at a `.gguf` file. If both an
API and a local model are configured, the app automatically falls back to the
other when one fails.

## Configuration

Everything is editable in **⚙ Settings**, which persists to a `.env` file in
your user data directory (`%APPDATA%\ReadingPacer` on Windows,
`~/Library/Application Support/ReadingPacer` on macOS,
`~/.local/share/reading-pacer` on Linux). A `.env` in the working directory or
repo root takes precedence — handy for development. See
[.env.example](.env.example) for all keys. Set `READING_PACER_HOME` to keep
everything in one folder (portable mode).

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `←` / `→` | Skip back / forward 5 words |
| `↑` / `↓` | Speed up / slow down (±25 WPM) |
| `+` / `-` | Font size |
| `Ctrl+S` | Save progress |
| `Ctrl+R` | Restart from the top |
| `1–4` or `A–D` | Answer quiz questions |

## Privacy

Your text stays on your machine. It is only sent to the API provider you
configured, and only when you press **Quiz** or **Generate Passage**. Use a
local model (Ollama, LM Studio, or a GGUF file) for fully offline operation.
Reading progress and stats are stored locally in your user data directory.

## Contributing

Issues and PRs are welcome!

```bash
pip install -e ".[dev]"
pytest        # run tests
ruff check .  # lint
```

## License

[MIT](LICENSE)
