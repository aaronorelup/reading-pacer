"""
llm_service.py — Question and passage generation via an OpenAI-compatible API
(DeepSeek by default) or a local GGUF model (llama-cpp-python, optional).

All public functions run the work on a daemon thread and report results via
callbacks. Callbacks are invoked FROM THE WORKER THREAD — UI code must
marshal back to the Tk main loop (e.g. widget.after(0, ...)).
"""

import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from reading_pacer.config import config

# ── Local model (lazy import + instance cache) ────────────────────────

_local_lock = threading.Lock()
_local_model = None
_local_model_key = None


def _get_local_model():
    """Load (or reuse) the llama-cpp model. Raises ImportError if not installed."""
    global _local_model, _local_model_key
    from llama_cpp import Llama

    key = (config.llm_local_path, config.llm_local_context_size, config.llm_local_gpu_layers)
    with _local_lock:
        if _local_model is None or _local_model_key != key:
            _local_model = Llama(
                model_path=config.llm_local_path,
                n_ctx=config.llm_local_context_size,
                n_gpu_layers=config.llm_local_gpu_layers,
                verbose=False,
            )
            _local_model_key = key
        return _local_model


# ── Public API ────────────────────────────────────────────────────────

def generate_questions(
    text: str,
    num_questions: int,
    on_done: Callable[[list], None],
    on_error: Callable[[str], None],
    cancelled: Callable[[], bool],
    log: Callable[[str], None],
):
    """Generate progressive-difficulty comprehension questions for `text`.

    Tries config.llm_default_provider first and falls back to the other
    provider if the preferred one fails or isn't configured.
    """
    def _work():
        primary_local = config.llm_default_provider == "local"
        order = ["local", "api"] if primary_local else ["api", "local"]
        available = [p for p in order if _provider_ready(p)]
        if not available:
            on_error("No LLM configured. Open Settings to add an API key or local model.")
            return
        last_err = ""
        for i, provider in enumerate(available):
            if cancelled():
                return
            try:
                if provider == "api":
                    log("Contacting API…")
                    raw = _api_chat(_question_messages(text, num_questions, local=False),
                                    max_tokens=_question_token_budget(num_questions),
                                    temperature=0.3, json_mode=True, cancelled=cancelled)
                else:
                    log("Loading local model…" if _local_model is None
                        else "Generating questions locally…")
                    raw = _local_complete(_question_prompt(text, num_questions, local=True),
                                          max_tokens=_question_token_budget(num_questions),
                                          temperature=0.4, cancelled=cancelled, log=log)
                if raw is None:
                    return  # cancelled
                questions = parse_questions(raw)
                if len(questions) < 3:
                    raise RuntimeError(f"Model returned only {len(questions)} usable questions")
                if not cancelled():
                    on_done(questions)
                return
            except Exception as e:
                last_err = str(e)
                if i + 1 < len(available):
                    log(f"{provider} failed ({last_err[:80]}) — trying "
                        f"{available[i + 1]} model…")
        if not cancelled():
            on_error(last_err[:300])

    threading.Thread(target=_work, daemon=True).start()


def generate_passage(
    topic: str,
    style: str,
    difficulty: str,
    word_count: int,
    on_done: Callable[[str], None],
    on_error: Callable[[str], None],
    cancelled: Callable[[], bool],
    log: Callable[[str], None],
):
    """Generate a reading passage with the preferred provider (API or local)."""
    def _work():
        prompt = _passage_prompt(topic, style, difficulty, word_count)
        max_tokens = min(word_count * 3, 6000)
        primary_local = config.llm_default_provider == "local"
        order = ["local", "api"] if primary_local else ["api", "local"]
        available = [p for p in order if _provider_ready(p)]
        if not available:
            on_error("No LLM configured. Open Settings to add an API key or local model.")
            return
        last_err = ""
        for i, provider in enumerate(available):
            if cancelled():
                return
            try:
                if provider == "api":
                    log("Generating passage…")
                    messages = [
                        {"role": "system", "content": "You are an educational content writer. "
                         "Write ONLY the passage, no meta-commentary."},
                        {"role": "user", "content": prompt},
                    ]
                    text = _api_chat(messages, max_tokens=max_tokens,
                                     temperature=0.7, json_mode=False, cancelled=cancelled)
                else:
                    log("Generating passage locally…")
                    text = _local_complete(prompt, max_tokens=max_tokens,
                                           temperature=0.7, cancelled=cancelled, log=log)
                if text is None:
                    return
                if not cancelled():
                    on_done(text.strip())
                return
            except Exception as e:
                last_err = str(e)
                if i + 1 < len(available):
                    log(f"{provider} failed ({last_err[:80]}) — trying "
                        f"{available[i + 1]} model…")
        if not cancelled():
            on_error(last_err[:300])

    threading.Thread(target=_work, daemon=True).start()


def test_connection(
    on_done: Callable[[str], None],
    on_error: Callable[[str], None],
):
    """Fire a minimal chat request at the configured API to verify it works."""
    def _work():
        try:
            start = time.monotonic()
            _api_chat(
                [{"role": "user", "content": "Reply with exactly: OK"}],
                max_tokens=8, temperature=0.0, json_mode=False, cancelled=lambda: False,
            )
            ms = int((time.monotonic() - start) * 1000)
            on_done(f"Connected — {config.llm_api_model} replied in {ms} ms")
        except Exception as e:
            on_error(str(e)[:300])

    threading.Thread(target=_work, daemon=True).start()


def _provider_ready(provider: str) -> bool:
    return config.has_api() if provider == "api" else config.has_local()


# ── Prompts ────────────────────────────────────────────────────────────

def _truncate_words(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    return cut[: cut.rfind(" ")] if " " in cut else cut


def _question_prompt(text: str, n: int, local: bool) -> str:
    if local:
        # Leave room in the context window for the template and the reply.
        budget_tokens = config.llm_local_context_size - _question_token_budget(n) - 300
        text = _truncate_words(text, max(budget_tokens, 500) * 3)
    else:
        text = _truncate_words(text, 150_000)  # ≈40k tokens, well inside DeepSeek's window
    return f"""Read this passage and create exactly {n} multiple choice comprehension questions.

PASSAGE:
{text}

REQUIREMENTS:
- Question 1 must be a simple surface-level question that anyone who skimmed could answer.
- Each question must be progressively more difficult than the last.
- Question {n} must target a very specific detail from deep in the passage.
- Each question has exactly 4 choices (A, B, C, D). All distractors must be plausible.
- Respond with ONLY valid JSON in exactly this format, no markdown fences, no other text:
{{"questions": [{{"question": "…", "A": "…", "B": "…", "C": "…", "D": "…", "answer": "A"}}]}}

JSON:"""


def _question_messages(text: str, n: int, local: bool) -> list[dict]:
    return [
        {"role": "system",
         "content": "You are a JSON generator. Output ONLY valid JSON, no other text."},
        {"role": "user", "content": _question_prompt(text, n, local)},
    ]


def _question_token_budget(n: int) -> int:
    return min(250 * n + 300, 4000)


def _passage_prompt(topic: str, style: str, difficulty: str, word_count: int) -> str:
    return f"""Write a reading passage.

TOPIC: {topic}
STYLE: {style}
DIFFICULTY: {difficulty}
TARGET LENGTH: approximately {word_count} words

Requirements:
- Write exactly about the topic specified
- Match the requested style and difficulty level
- Use clear prose with paragraphs
- Include specific facts, details, and concrete information
- Do NOT include any introduction like "Here is a passage about..."
- Do NOT include headings, bullet points, or lists
- Start directly with the content
- Aim for exactly {word_count} words

Begin now:"""


# ── API transport ─────────────────────────────────────────────────────

def _api_chat(messages: list[dict], max_tokens: int, temperature: float,
              json_mode: bool, cancelled: Callable[[], bool],
              timeout: int = 180) -> str | None:
    """POST a chat completion. Returns the reply text, or None if cancelled.

    When json_mode is requested but the server rejects it (HTTP 400 — some
    OpenAI-compatible servers don't support response_format), retries without.
    """
    if cancelled():
        return None
    payload = {
        "model": config.llm_api_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        return _post_json(payload, timeout)
    except _HTTPStatusError as e:
        if json_mode and e.status == 400:
            payload.pop("response_format", None)
            if cancelled():
                return None
            try:
                return _post_json(payload, timeout)
            except _HTTPStatusError as e2:
                raise RuntimeError(_friendly_http_error(e2.status, e2.message)) from e2
        raise RuntimeError(_friendly_http_error(e.status, e.message)) from e


class _HTTPStatusError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def _post_json(payload: dict, timeout: int) -> str:
    headers = {"Content-Type": "application/json"}
    if config.llm_api_key:
        headers["Authorization"] = f"Bearer {config.llm_api_key}"
    req = urllib.request.Request(
        config.llm_api_base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise _HTTPStatusError(e.code, _extract_api_error(body)) from e
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, socket.timeout):
            raise RuntimeError("Request timed out — the server took too long to respond.") from e
        raise RuntimeError(
            f"Network error: {reason}. Check the API URL and your connection.") from e
    except TimeoutError as e:
        raise RuntimeError("Request timed out — the server took too long to respond.") from e
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError("Unexpected response format — is the URL an OpenAI-compatible "
                           "chat completions endpoint?") from e


def _extract_api_error(body: str) -> str:
    try:
        data = json.loads(body)
        return data.get("error", {}).get("message") or body[:200]
    except (json.JSONDecodeError, AttributeError):
        return body[:200]


def _friendly_http_error(status: int, message: str) -> str:
    hints = {
        401: "Invalid API key (401). Check your key in Settings.",
        402: "Insufficient balance (402). Top up your account.",
        404: "Endpoint not found (404). Check the API base URL and model name in Settings.",
        422: f"Request rejected (422): {message}",
        429: "Rate limited (429). Wait a moment and try again.",
        500: "The API server had an internal error (500). Try again shortly.",
        503: "The API server is overloaded (503). Try again shortly.",
    }
    return hints.get(status, f"API error {status}: {message}")


# ── Local transport ───────────────────────────────────────────────────

def _local_complete(prompt: str, max_tokens: int, temperature: float,
                    cancelled: Callable[[], bool], log: Callable[[str], None]) -> str | None:
    try:
        llm = _get_local_model()
    except ImportError as e:
        raise RuntimeError(
            "llama-cpp-python is not installed. Run: pip install reading-pacer[local]"
        ) from e
    if cancelled():
        return None
    log("Generating locally…")
    response = llm(prompt, max_tokens=max_tokens, temperature=temperature,
                   stop=["\n\n\n", "PASSAGE:"])
    return response["choices"][0]["text"].strip()


# ── Question parsing (model output → normalized dicts) ───────────────

def parse_questions(raw: str) -> list[dict]:
    """Parse model output into question dicts, tolerating common malformations."""
    raw = _strip_fences(raw)
    # Direct parse: {"questions": [...]} or a bare array
    try:
        data = json.loads(raw)
        items = data.get("questions") if isinstance(data, dict) else data
        if isinstance(items, list):
            return _normalise(items)
    except json.JSONDecodeError:
        pass
    # Extract the first [...] block
    m = re.search(r"\[[\s\S]*\]", raw)
    if m:
        try:
            data = json.loads(m.group())
            if isinstance(data, list):
                return _normalise(data)
        except json.JSONDecodeError:
            pass
    # Last resort: salvage individual {...} objects
    result = []
    for obj_str in re.findall(r"\{[^{}]*\}", raw, re.DOTALL):
        try:
            fixed = re.sub(r",\s*}", "}", obj_str)
            q = _norm_q(json.loads(fixed))
            if q:
                result.append(q)
        except json.JSONDecodeError:
            continue
    return result


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", raw)
    return m.group(1) if m else raw


def _normalise(items: list) -> list[dict]:
    return [q for d in items if isinstance(d, dict) and (q := _norm_q(d))]


def _norm_q(d: dict) -> dict | None:
    qt = d.get("question") or d.get("Question")
    a = d.get("A") or d.get("a")
    b = d.get("B") or d.get("b")
    c = d.get("C") or d.get("c")
    d_ = d.get("D") or d.get("d")
    ans = d.get("answer") or d.get("Answer") or d.get("correct")
    if not all([qt, a, b, c, d_, ans]):
        return None
    ans = str(ans).strip().upper()[:1]
    if ans not in ("A", "B", "C", "D"):
        return None
    return {
        "question": str(qt).strip(),
        "choices": [str(a).strip(), str(b).strip(), str(c).strip(), str(d_).strip()],
        "correct": ans,
    }
