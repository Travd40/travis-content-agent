"""
generate_content.py
Uses Claude (Anthropic) to generate a branded coaching tip for Travis Dixon.
Returns: { category, tip, caption, hashtags }
"""

import os
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
RECENT_LOOKBACK = 20


def _recent_tips(n: int = RECENT_LOOKBACK) -> list[str]:
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE) as f:
            history = json.load(f).get("history", [])
        return [h.get("tip", "") for h in history[-n:] if h.get("tip")]
    except Exception:
        return []

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
  "📞 Book your FREE 15-min strategy call: https://calendly.com/travd40/15-minute-strategy-call\n📖 Get the book: https://www.amazon.com/dp/B0GPSNXGY8\n🌐 Visit: https://travisdixoncoaching.com"
- The FREE call CTA must come FIRST — it's the primary action we want readers to take
- Hashtags: 8-12 relevant tags for relationship coaching, men, couples, personal growth

Return ONLY valid JSON in this exact format, no extra text:
{
  "category": "CATEGORY NAME",
  "tip": "The short tip that appears on video (12-18 words)",
  "caption": "Instagram/TikTok caption with CTA",
  "hashtags": "#tag1 #tag2 #tag3"
}"""


def _call_claude_with_retry(client, user_prompt: str):
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return client.messages.create(
                model=MODEL,
                max_tokens=512,
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


def generate_content(post_number: int = 0) -> dict:
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

    user_prompt = (
        f"Generate a {category} coaching tip. "
        f"This is post #{post_number + 1} — make it fresh and distinct."
        f"{avoid_block}\n\n"
        f"Return valid JSON only, no markdown, no extra text."
    )

    message = _call_claude_with_retry(client, user_prompt)

    raw = message.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    content = json.loads(raw, strict=False)

    # Trim tip if too long
    words = content.get("tip", "").split()
    if len(words) > 20:
        content["tip"] = " ".join(words[:18])

    return content


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    result = generate_content(n)
    print(json.dumps(result, indent=2))
