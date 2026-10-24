"""
generate_content.py
Uses Claude (Anthropic) to generate a branded coaching tip for Travis Dixon.
Returns: { category, hook, tip, script, caption, hashtags }
"""

import os
import re
import json
import time
import anthropic
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

MODEL = "claude-opus-4-7"
REQUEST_TIMEOUT_S = 60.0
MAX_ATTEMPTS = 5
BACKOFF_BASE_S = 4  # 4s, 8s, 16s, 32s between attempts 1→5

CATEGORIES = [
    "COUPLES COACHING",
    "MEN'S COACHING",
    "COMMUNICATION",
    "TRUST & SAFETY",
]

LOG_FILE = Path(__file__).parent.parent / "post_log.json"
TOPIC_QUEUE = Path(__file__).parent.parent / "topic_queue.json"
RECENT_LOOKBACK = 20
MAX_FRESH_TRIES = 3  # regenerate when the headline repeats a past post


def _pop_queued_topic() -> str | None:
    """Return the next queued topic (and consume it), or None if the queue is
    empty/missing/invalid. topic_queue.json is a JSON list of topic strings;
    the daily workflow commits the consumed queue back to the repo."""
    if not TOPIC_QUEUE.exists():
        return None
    try:
        with open(TOPIC_QUEUE) as f:
            queue = json.load(f)
        if not isinstance(queue, list) or not queue:
            return None
        topic = queue.pop(0)
        with open(TOPIC_QUEUE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)
        if isinstance(topic, str) and topic.strip():
            return topic.strip()
        return None
    except Exception:
        return None


def _recent_tips(n: int = RECENT_LOOKBACK) -> list[str]:
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE) as f:
            history = json.load(f).get("history", [])
        return [h.get("tip", "") for h in history[-n:] if h.get("tip")]
    except Exception:
        return []


def _headline(tip: str) -> str:
    """First sentence of a tip: what the video shows and the website page title."""
    return re.split(r"(?<=[.!?])\s", tip.strip(), maxsplit=1)[0].rstrip(".")


def _headline_key(tip: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _headline(tip).lower())


def _past_headlines() -> list[str]:
    """Every distinct headline ever posted, oldest first. Tips repeated well
    outside the RECENT_LOOKBACK window, so the whole log is checked."""
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE) as f:
            history = json.load(f).get("history", [])
    except Exception:
        return []
    seen, out = set(), []
    for h in history:
        tip = h.get("tip") or ""
        key = _headline_key(tip)
        if key and key not in seen:
            seen.add(key)
            out.append(_headline(tip))
    return out

SYSTEM_PROMPT = """You are a content writer for Travis Dixon, a relationship coach.

Travis's brand: "Becoming A Trained Partner"
Core philosophy: Relationships fail from lack of TRAINING, not lack of love.
Book: "I Am A Dog: The Discipline of Becoming a Trained Partner"
Services: Couples coaching, men's coaching, individual coaching
Website: travisdixoncoaching.com

WRITING RULES:
- The "tip" must be 12-18 words MAX — it appears on screen and must fit cleanly
- Tone: direct, structured, authoritative but warm — like a coach, not a therapist
- Use the "trained partner" framework naturally (don't force it every time)
- No fluff, no clichés like "communication is key"
- The "caption" is for Instagram/TikTok — 2-3 sentences, punchy, ends with a CTA
- Always end the caption with EXACTLY these three lines (do NOT skip any):
  "📞 Book your FREE 15-min strategy call: https://travisdixoncoaching.com/freecall\n📖 Get the book: https://www.amazon.com/dp/B0GPSNXGY8\n🌐 Visit: https://travisdixoncoaching.com"
- The FREE call CTA must come FIRST — it's the primary action we want readers to take
- Hashtags: 8-12 relevant tags for relationship coaching, men, couples, personal growth
- The "hook" is the first thing spoken in the video (about 2 seconds): ONE short question, 10 words or fewer,
  in the voice of someone struggling in their relationship, that the tip answers.
  Examples: "Why does he shut down every time we argue?" / "Why does she bring up old fights?"
- The "script" is what Travis SAYS in the video right after the hook: 55-85 words, 4-6 short spoken
  sentences, first person, plain talk. Structure: name the real moment the viewer lives through,
  say why it happens, then give ONE specific thing a trained partner does instead. It must expand
  the tip, not repeat it word for word. No hashtags, emojis, links, or sign-off — the call to action
  is added separately.

Return ONLY valid JSON in this exact format, no extra text:
{
  "category": "CATEGORY NAME",
  "hook": "Question a struggling partner would ask, 10 words max?",
  "tip": "The short tip that appears on video (12-18 words)",
  "script": "What Travis says after the hook (55-85 words)",
  "caption": "Instagram/TikTok caption with CTA",
  "hashtags": "#tag1 #tag2 #tag3"
}"""


def _call_claude_with_retry(client, user_prompt: str):
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=REQUEST_TIMEOUT_S,
            )
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
            print(f"[generate_content] {type(e).__name__} on attempt {attempt}/{MAX_ATTEMPTS} — retrying in {wait}s...", flush=True)
            time.sleep(wait)
    raise last_err


def clean_hook(hook) -> str | None:
    """A usable opening question, or None so the video simply starts on the tip."""
    if not isinstance(hook, str):
        return None
    hook = hook.strip().strip('"').strip()
    if not hook.endswith("?") or len(hook.split()) > 12:
        return None
    return hook


def clean_script(script) -> str | None:
    """The spoken body, or None so the voiceover falls back to the short tip."""
    if not isinstance(script, str):
        return None
    script = " ".join(script.split())
    if len(script.split()) < 25:
        return None
    words = script.split()
    if len(words) > 110:
        script = " ".join(words[:110]).rstrip(",;:") + "."
    return script


def headline_already_posted(tip: str) -> bool:
    return _headline_key(tip) in {_headline_key(h) for h in _past_headlines()}


def generate_content(post_number: int = 0, topic: str | None = None) -> dict:
    """topic, when given, is used in place of the next queued topic."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    category = CATEGORIES[post_number % len(CATEGORIES)]

    recent = _recent_tips()
    avoid_block = ""
    if recent:
        numbered = "\n".join(f"  - {t}" for t in recent)
        avoid_block = (
            f"\n\nDO NOT repeat, paraphrase, or lightly reword any of these recent tips:\n"
            f"{numbered}\n\n"
            f"The new tip must use a different angle, different verb, different core insight. "
            f"If you are tempted to write 'Stop [doing X]...' and X appears above, pick a different X or a different frame entirely."
        )

    queued_topic = topic or _pop_queued_topic()
    if queued_topic:
        print(f"[generate_content] Using queued topic: {queued_topic[:80]}...", flush=True)
        user_prompt = (
            f"Generate a {category} coaching tip on this REQUIRED topic:\n\n{queued_topic}\n\n"
            f"The tip, caption, and hashtags must all be about this topic. "
            f"This topic was deliberately chosen, so cover it even if it resembles a past tip, "
            f"but phrase the on-screen tip with fresh wording. "
            f"This is post #{post_number + 1}.\n\n"
            f"Return valid JSON only, no markdown, no extra text."
        )
    else:
        user_prompt = (
            f"Generate a {category} coaching tip. "
            f"This is post #{post_number + 1} — make it fresh and distinct."
            f"{avoid_block}\n\n"
            f"Return valid JSON only, no markdown, no extra text."
        )

    past = _past_headlines()
    if past:
        used = "\n".join(f"  - {h}" for h in past)
        user_prompt += (
            f"\n\nThese headlines have ALREADY been posted. The first sentence of the new tip "
            f"must not match or lightly reword any of them:\n{used}"
        )
    used_keys = {_headline_key(h) for h in past}

    for attempt in range(1, MAX_FRESH_TRIES + 1):
        message = _call_claude_with_retry(client, user_prompt)

        raw = message.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        content = json.loads(raw, strict=False)

        headline = _headline(content.get("tip", ""))
        if _headline_key(headline) not in used_keys:
            break
        print(f"[generate_content] Headline already posted ({headline!r}), regenerating "
              f"({attempt}/{MAX_FRESH_TRIES})...", flush=True)
        user_prompt += (
            f"\n\nYour last answer opened with \"{headline}\", which was already posted. "
            f"Write a different first sentence."
        )

    # Trim tip if too long
    words = content.get("tip", "").split()
    if len(words) > 20:
        content["tip"] = " ".join(words[:18])

    content["hook"] = clean_hook(content.get("hook"))
    content["script"] = clean_script(content.get("script"))

    return content


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    result = generate_content(n)
    print(json.dumps(result, indent=2))
