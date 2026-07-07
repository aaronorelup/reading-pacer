"""Tests for .env parsing, config loading/validation, and save round-trips."""

from reading_pacer.config import Config, read_dotenv


def test_read_dotenv_basic(tmp_path):
    p = tmp_path / ".env"
    p.write_text(
        "# comment line\n"
        "\n"
        "KEY=value\n"
        "SPACED = padded \n"
        "QUOTED=\"with spaces\"\n"
        "EQUALS=a=b=c\n"
        "NOEQUALS_IGNORED\n",
        encoding="utf-8",
    )
    env = read_dotenv(str(p))
    assert env["KEY"] == "value"
    assert env["SPACED"] == "padded"
    assert env["QUOTED"] == "with spaces"
    assert env["EQUALS"] == "a=b=c"
    assert "NOEQUALS_IGNORED" not in env


def test_read_dotenv_missing_file(tmp_path):
    assert read_dotenv(str(tmp_path / "nope.env")) == {}


def test_load_defaults_when_empty(tmp_path):
    cfg = Config.load(str(tmp_path / ".env"))
    assert cfg.llm_api_model == "deepseek-chat"
    assert "deepseek.com" in cfg.llm_api_base_url
    assert cfg.theme == "mocha"
    assert cfg.quiz_questions == 8
    assert not cfg.has_api()
    assert not cfg.has_local()


def test_load_validates_bad_values(tmp_path):
    p = tmp_path / ".env"
    p.write_text(
        "THEME=neon\nQUIZ_QUESTIONS=99\nLLM_DEFAULT_PROVIDER=cloud\n"
        "LLM_LOCAL_CONTEXT_SIZE=not-a-number\n",
        encoding="utf-8",
    )
    cfg = Config.load(str(p))
    assert cfg.theme == "mocha"
    assert cfg.quiz_questions == 12  # clamped to max
    assert cfg.llm_default_provider == "api"
    assert cfg.llm_local_context_size == 4096


def test_save_roundtrip_preserves_comments(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# my comment\nLLM_API_KEY=old\nCUSTOM_KEY=untouched\n", encoding="utf-8")
    cfg = Config.load(str(p))
    cfg.llm_api_key = "new-key"
    cfg.theme = "latte"
    cfg.save()

    text = p.read_text(encoding="utf-8")
    assert "# my comment" in text
    assert "CUSTOM_KEY=untouched" in text
    assert "LLM_API_KEY=new-key" in text

    cfg2 = Config.load(str(p))
    assert cfg2.llm_api_key == "new-key"
    assert cfg2.theme == "latte"
    assert cfg2.quiz_questions == 8


def test_save_creates_file(tmp_path):
    p = tmp_path / "sub" / ".env"
    cfg = Config.load(str(p))
    cfg.llm_api_key = "abc"
    cfg.save()
    assert Config.load(str(p)).llm_api_key == "abc"


def test_has_api_allows_keyless_local_server(tmp_path):
    cfg = Config.load(str(tmp_path / ".env"))
    cfg.llm_api_base_url = "http://localhost:11434/v1/chat/completions"
    assert cfg.has_api()
    cfg.llm_api_base_url = "https://api.deepseek.com/v1/chat/completions"
    assert not cfg.has_api()
    cfg.llm_api_key = "sk-x"
    assert cfg.has_api()
