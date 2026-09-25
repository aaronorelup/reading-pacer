"""
config.py — Loads settings from a .env file, provides a typed Config singleton.

Search order for the .env file (unless READING_PACER_HOME is set, in which
case only that folder is used):
  1. ./.env                      (current working directory)
  2. <repo root>/.env            (source checkout)
  3. <user data dir>/.env        (installed app — see paths.user_data_dir)

Settings are saved back to whichever file was found; if none exists yet,
they are saved to the user data directory.
"""

import os
from dataclasses import dataclass

from reading_pacer import paths

VALID_THEMES = ("mocha", "latte")
MIN_QUIZ_QUESTIONS, MAX_QUIZ_QUESTIONS = 3, 12


def find_env() -> str:
    """Return the path of the first .env found, else the user-dir default.

    When READING_PACER_HOME is set (portable mode, tests), only that folder is used.
    """
    if os.environ.get("READING_PACER_HOME"):
        return os.path.join(paths.user_data_dir(), ".env")
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(paths.repo_root(), ".env"),
        os.path.join(paths.user_data_dir(), ".env"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return candidates[-1]


def read_dotenv(path: str) -> dict:
    """Minimal .env parser: KEY=VALUE lines, # comments, blanks ignored."""
    env = {}
    if not os.path.isfile(path):
        return env
    with open(path, encoding="utf-8-sig") as f:  # -sig: tolerate a BOM from Notepad
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            env[key.strip()] = val
    return env


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # ── API model (DeepSeek by default; any OpenAI-compatible endpoint works) ──
    llm_api_key: str = ""
    llm_api_model: str = "deepseek-chat"
    llm_api_base_url: str = "https://api.deepseek.com/v1/chat/completions"

    # ── Local model (GGUF via llama-cpp-python, optional) ──
    llm_local_path: str = ""
    llm_local_context_size: int = 4096
    llm_local_gpu_layers: int = 35

    # ── Preferences ──
    llm_default_provider: str = "api"  # "api" or "local"
    theme: str = "mocha"               # "mocha" (dark) or "latte" (light)
    quiz_questions: int = 8
    check_for_updates: bool = True
    skipped_version: str = ""          # "Skip this version" in the update banner

    # Where settings are persisted (set by load(); not written to the file itself)
    env_path: str = ""

    # ── Capability checks ──────────────────────────────────────────────

    def is_local_server(self) -> bool:
        """True when the API URL points at a machine-local server (Ollama, LM Studio)."""
        url = self.llm_api_base_url.lower()
        return "localhost" in url or "127.0.0.1" in url or "0.0.0.0" in url

    def has_api(self) -> bool:
        """A key is required, except for local OpenAI-compatible servers."""
        return bool(self.llm_api_base_url) and (bool(self.llm_api_key) or self.is_local_server())

    def has_local(self) -> bool:
        return bool(self.llm_local_path) and os.path.exists(self.llm_local_path)

    def has_any_llm(self) -> bool:
        return self.has_api() or self.has_local()

    # ── Load / save ────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        path = path or find_env()
        env = read_dotenv(path)
        cfg = cls(
            llm_api_key=env.get("LLM_API_KEY", ""),
            llm_api_model=env.get("LLM_API_MODEL", "deepseek-chat"),
            llm_api_base_url=env.get(
                "LLM_API_BASE_URL", "https://api.deepseek.com/v1/chat/completions"
            ),
            llm_local_path=env.get("LLM_LOCAL_PATH", ""),
            llm_local_context_size=_to_int(env.get("LLM_LOCAL_CONTEXT_SIZE"), 4096),
            llm_local_gpu_layers=_to_int(env.get("LLM_LOCAL_GPU_LAYERS"), 35),
            llm_default_provider=env.get("LLM_DEFAULT_PROVIDER", "api"),
            theme=env.get("THEME", "mocha"),
            quiz_questions=_to_int(env.get("QUIZ_QUESTIONS"), 8),
            check_for_updates=_to_bool(env.get("CHECK_FOR_UPDATES"), True),
            skipped_version=env.get("SKIPPED_VERSION", ""),
            env_path=path,
        )
        if cfg.theme not in VALID_THEMES:
            cfg.theme = "mocha"
        if cfg.llm_default_provider not in ("api", "local"):
            cfg.llm_default_provider = "api"
        cfg.quiz_questions = max(MIN_QUIZ_QUESTIONS, min(MAX_QUIZ_QUESTIONS, cfg.quiz_questions))
        return cfg

    def save(self):
        """Write settings back to the .env file, preserving comments and unknown keys."""
        path = self.env_path or find_env()
        lines: list[str] = []
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()

        def _set(key: str, value: str):
            for i, line in enumerate(lines):
                if line.strip().startswith(f"{key}="):
                    lines[i] = f"{key}={value}\n"
                    return
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"{key}={value}\n")

        _set("LLM_API_KEY", self.llm_api_key)
        _set("LLM_API_MODEL", self.llm_api_model)
        _set("LLM_API_BASE_URL", self.llm_api_base_url)
        _set("LLM_LOCAL_PATH", self.llm_local_path)
        _set("LLM_LOCAL_CONTEXT_SIZE", str(self.llm_local_context_size))
        _set("LLM_LOCAL_GPU_LAYERS", str(self.llm_local_gpu_layers))
        _set("LLM_DEFAULT_PROVIDER", self.llm_default_provider)
        _set("THEME", self.theme)
        _set("QUIZ_QUESTIONS", str(self.quiz_questions))
        _set("CHECK_FOR_UPDATES", "true" if self.check_for_updates else "false")
        _set("SKIPPED_VERSION", self.skipped_version)

        paths.ensure_dir(os.path.dirname(os.path.abspath(path)))
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        self.env_path = path


config = Config.load()
