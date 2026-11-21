"""
generate_content.py
Uses an AI model (free Gemini by default, see llm.py) to generate a branded coaching tip for Travis Dixon.
Returns: { category, hook, tip, script, caption, hashtags }
"""

import os
import re
import json
import time
import llm

from brand_caption import brand_caption, strip_dashes
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

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


def _hook_key(hook) -> str:
    if not isinstance(hook, str):
        return ""
    return re.sub(r"[^a-z0-9]", "", hook.lower())


def _past_hooks() -> list[str]:
    """Every distinct opening question ever posted, oldest first. The hook is
    spoken first and becomes the YouTube title, so a repeat reads as a rerun
    even when the tip under it is new."""
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE) as f:
            history = json.load(f).get("history", [])
    except Exception:
        return []
    seen, out = set(), []
    for h in history:
        hook = h.get("hook") or ""
        key = _hook_key(hook)
        if key and key not in seen:
            seen.add(key)
            out.append(hook.strip())
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
- Never use em dashes or en dashes anywhere. Use a comma, a period, or two sentences instead.
- The caption's first line is exactly "Travis Dixon Coaching | Relationship coach" so searches for the name find the post
- The "caption" is for Instagram/TikTok — 2-3 sentences, punchy, ends with a CTA
- Always end the caption with EXACTLY these three lines (do NOT skip any):
  "📞 Book your FREE 15-min strategy call: https://travisdixoncoaching.com/freecall\n📖 Get the book: https://www.amazon.com/dp/B0GPSNXGY8\n🌐 Visit: https://travisdixoncoaching.com"
- The FREE call CTA must come FIRST — it's the primary action we want readers to take
- Hashtags: 8-12 relevant tags for relationship coaching, men, couples, personal growth. Always include #TravisDixonCoaching #CoachTee #TrainedPartner #RelationshipCoach #CharlotteNC first
- The "hook" is the first thing spoken in the video (about 2 seconds): ONE short question, 10 words or fewer,
  in the voice of someone struggling in their relationship, that the tip answers.
  Examples: "Why does he shut down every time we argue?" / "Why does she bring up old fights?"
- The "script" is what Travis SAYS in the video right after the hook: 55-85 words, 4-6 short spoken
  sentences, first person, plain talk. Structure: name the real moment the viewer lives through,
  say why it happens, then give ONE specific thing a trained partner does instead. It must expand
  the tip, not repeat it word for word. No hashtags, emojis, links, or sign-off — the call to action
  is added separately.
- The "scene" opens the video before Travis speaks. It is a moment from a coaching session:
  a married couple, Logic (the husband) and Harmony (the wife), sit with Coach Tee and say the
  thing the tip answers. Write 2 or 3 lines, each 9 words or fewer, alternating speakers, in
  plain spoken words a real couple would say. The viewer should think "that is us".
  Example: Harmony: "I'm done." Logic: "Why? What did I do?"
  Rules for the scene: either one may be the partner who is struggling, so vary who starts and
  who is in the wrong from day to day. No yelling, insults, threats, profanity or anything
  physical. Never make either of them look stupid. Coach Tee does not speak in the scene.

Return ONLY valid JSON in this exact format, no extra text:
{
  "category": "CATEGORY NAME",
  "hook": "Question a struggling partner would ask, 10 words max?",
  "tip": "The short tip that appears on video (12-18 words)",
  "script": "What Travis says after the hook (55-85 words)",
  "scene": [{"speaker": "harmony", "line": "..."}, {"speaker": "logic", "line": "..."}],
  "caption": "Instagram/TikTok caption with CTA",
  "hashtags": "#tag1 #tag2 #tag3"
}"""


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


SCENE_SPEAKERS = ("logic", "harmony")
SCENE_MAX_WORDS = 12
# A scene is dropped, never repaired, when a line would not be safe to voice.
SCENE_BLOCKED = re.compile(
    r"\b(hate you|shut up|stupid|idiot|kill|hit you|slap|divorce you|damn|hell|"
    r"bitch|ass|crazy|worthless|pathetic)\b", re.IGNORECASE)


def clean_scene(scene) -> list[dict] | None:
    """The couple's opening lines, or None so the video opens the classic way.
    Needs 2 or 3 short lines, both partners speaking, nothing harsh."""
    if not isinstance(scene, list) or not 2 <= len(scene) <= 3:
        return None
    out = []
    for item in scene:
        if not isinstance(item, dict):
            return None
        speaker = str(item.get("speaker", "")).strip().lower()
        line = item.get("line")
        if speaker not in SCENE_SPEAKERS or not isinstance(line, str):
            return None
        line = " ".join(line.replace("\u2014", ", ").replace("\u2013", ", ").split()).strip('"').strip()
        if not line or len(line.split()) > SCENE_MAX_WORDS or SCENE_BLOCKED.search(line):
            return None
        if line[-1] not in ".!?":
            line += "."
        out.append({"speaker": speaker, "line": line})
    if {i["speaker"] for i in out} != set(SCENE_SPEAKERS):
        return None
    return out


def headline_already_posted(tip: str) -> bool:
    return _headline_key(tip) in {_headline_key(h) for h in _past_headlines()}


def generate_content(post_number: int = 0, topic: str | None = None) -> dict:
    """topic, when given, is used in place of the next queued topic."""
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

    past_hooks = _past_hooks()
    if past_hooks:
        asked = "\n".join(f"  - {h}" for h in past_hooks)
        user_prompt += (
            f"\n\nThese hook questions have ALREADY opened a video. The new hook must ask "
            f"something different, not the same question reworded:\n{asked}"
        )
    used_hook_keys = {_hook_key(h) for h in past_hooks}

    for attempt in range(1, MAX_FRESH_TRIES + 1):
        raw = llm.complete(SYSTEM_PROMPT, user_prompt, max_tokens=1024,
                           timeout=REQUEST_TIMEOUT_S, tag="generate_content")
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        content = json.loads(raw, strict=False)

        headline = _headline(content.get("tip", ""))
        hook = content.get("hook") or ""
        headline_repeat = _headline_key(headline) in used_keys
        hook_repeat = bool(hook) and _hook_key(hook) in used_hook_keys
        if not headline_repeat and not hook_repeat:
            break
        if headline_repeat:
            print(f"[generate_content] Headline already posted ({headline!r}), regenerating "
                  f"({attempt}/{MAX_FRESH_TRIES})...", flush=True)
            user_prompt += (
                f"\n\nYour last answer opened with \"{headline}\", which was already posted. "
                f"Write a different first sentence."
            )
        if hook_repeat:
            print(f"[generate_content] Hook already used ({hook!r}), regenerating "
                  f"({attempt}/{MAX_FRESH_TRIES})...", flush=True)
            user_prompt += (
                f"\n\nYour last hook \"{hook}\" already opened a video. "
                f"Ask a different question."
            )

    # Trim tip if too long
    words = content.get("tip", "").split()
    if len(words) > 20:
        content["tip"] = " ".join(words[:18])

    content["hook"] = clean_hook(content.get("hook"))
    if content["hook"] and _hook_key(content["hook"]) in used_hook_keys:
        # Still a repeat after every retry: start the video on the tip instead.
        print(f"[generate_content] Dropping repeated hook ({content['hook']!r})", flush=True)
        content["hook"] = None
    content["script"] = clean_script(content.get("script"))
    content["scene"] = clean_scene(content.get("scene"))
    content["tip"] = strip_dashes(content.get("tip", ""))
    if content["script"]:
        content["script"] = strip_dashes(content["script"])
    content["caption"], content["hashtags"] = brand_caption(content.get("caption", ""), content.get("hashtags", ""))

    return content


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    result = generate_content(n)
    print(json.dumps(result, indent=2))
