"""
llm.py
One place that turns (system prompt, user prompt) into text, so the content
tools don't care which AI provider writes the words.

Provider order:
  1. Google Gemini, when GEMINI_API_KEY is set. A key from Google AI Studio
     (https://aistudio.google.com/apikey) works on the free tier with no card
     on file; one daily post and one weekly article are far below its limits.
  2. Anthropic Claude, when ANTHROPIC_API_KEY is set (paid, prepaid credits).

If Gemini is configured but fails (quota, outage, a retired model), Claude is
tried next when its key is present, so a paid key still acts as a safety net.

Env:
  GEMINI_API_KEY     free key from Google AI Studio
  GEMINI_MODEL       optional override; default tries the models below in order
  ANTHROPIC_API_KEY  optional paid fallback
"""

import json
import os
import time
import urllib.error
import urllib.request

# Free-tier text models, best first. A model Google retires (404) or that is
# out of quota for the day (429) is skipped and the next one is tried.
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
CLAUDE_MODEL = "claude-opus-4-7"

MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 4  # 4s, 8s, 16s


class LLMError(RuntimeError):
    pass


def _log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def _gemini_once(model: str, key: str, system: str, user: str, max_tokens: int, timeout: float) -> str:
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        # Newer Gemini models spend output tokens on hidden reasoning first,
        # so leave generous headroom or the visible answer gets cut off.
        "generationConfig": {"maxOutputTokens": max(8192, max_tokens * 4)},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    candidates = data.get("candidates") or []
    if not candidates:
        raise LLMError(f"Gemini returned no answer ({data.get('promptFeedback')})")
    cand = candidates[0]
    text = "".join(
        p.get("text", "")
        for p in (cand.get("content") or {}).get("parts", [])
        if not p.get("thought")
    ).strip()
    if not text:
        raise LLMError(f"Gemini returned empty text (finishReason={cand.get('finishReason')})")
    if cand.get("finishReason") == "MAX_TOKENS":
        raise LLMError("Gemini answer was cut off at the token limit")
    return text


def _gemini(system: str, user: str, max_tokens: int, timeout: float, tag: str) -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    override = os.getenv("GEMINI_MODEL", "").strip()
    models = [override] if override else GEMINI_MODELS
    last_err: Exception | None = None

    for model in models:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                text = _gemini_once(model, key, system, user, max_tokens, timeout)
                _log(tag, f"Written by {model} (Gemini free tier)")
                return text
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                last_err = LLMError(f"Gemini {model} HTTP {e.code}: {detail}")
                if e.code in (500, 502, 503, 504) and attempt < MAX_ATTEMPTS:
                    wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
                    _log(tag, f"{model} HTTP {e.code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                if e.code in (400, 401, 403) and "API key" in detail:
                    raise last_err  # a bad key fails the same way on every model
                _log(tag, f"{model} unavailable (HTTP {e.code}), trying the next model")
                break
            except (urllib.error.URLError, TimeoutError, LLMError) as e:
                last_err = e
                if attempt < MAX_ATTEMPTS:
                    wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
                    _log(tag, f"{model}: {e}; retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                break
    raise last_err or LLMError("Gemini failed")


def _claude(system: str, user: str, max_tokens: int, timeout: float, tag: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=timeout,
            )
            _log(tag, f"Written by {CLAUDE_MODEL} (Anthropic, paid)")
            return "".join(b.text for b in message.content if getattr(b, "type", "") == "text").strip()
        except (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        ) as e:
            last_err = e
            if attempt == MAX_ATTEMPTS:
                break
            wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
            _log(tag, f"{type(e).__name__} on attempt {attempt}/{MAX_ATTEMPTS}, retrying in {wait}s...")
            time.sleep(wait)
    raise last_err


def complete(system: str, user: str, max_tokens: int = 1024, timeout: float = 60.0, tag: str = "llm") -> str:
    """Return the model's text answer for this system + user prompt."""
    has_gemini = bool(os.getenv("GEMINI_API_KEY", "").strip())
    has_claude = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    if not has_gemini and not has_claude:
        raise LLMError(
            "No AI key configured. Add a free GEMINI_API_KEY from "
            "https://aistudio.google.com/apikey (or a paid ANTHROPIC_API_KEY)."
        )

    if has_gemini:
        try:
            return _gemini(system, user, max_tokens, timeout, tag)
        except Exception as e:
            if not has_claude:
                raise
            _log(tag, f"Gemini failed ({e}); falling back to Claude")
    return _claude(system, user, max_tokens, timeout, tag)
