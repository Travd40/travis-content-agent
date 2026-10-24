"""
elevenlabs_tts.py
Generate a voiceover MP3 for the daily coaching tip via the ElevenLabs API.

Requires:
  ELEVENLABS_API_KEY   - API key (if unset, generate_voiceover returns None
                         and the video renders silent, exactly as before)
  ELEVENLABS_VOICE_ID  - optional; defaults to "Adam" (deep male narration)

Returns (mp3_path, duration_seconds, captions) or None on any failure — a
voiceover problem must never block the daily post. captions is a list of
{"text", "start", "end"} phrases timed to the speech (seconds), or None when
ElevenLabs sent no timing data.
"""

import os
import re
import json
import base64
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

OUTPUT_DIR = Path(__file__).parent.parent / "output"
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # "Adam" - warm, confident male
MODEL_ID = "eleven_multilingual_v2"
CAPTION_MAX_WORDS = 6


def captions_from_alignment(alignment: dict | None, max_words: int = CAPTION_MAX_WORDS):
    """ElevenLabs character timings -> short on-screen phrases.

    Words are grouped up to max_words, breaking early after punctuation so a
    phrase never runs across a sentence. Returns None if the alignment is
    missing or malformed.
    """
    try:
        chars = alignment["characters"]
        starts = alignment["character_start_times_seconds"]
        ends = alignment["character_end_times_seconds"]
    except (TypeError, KeyError):
        return None
    if not chars or not (len(chars) == len(starts) == len(ends)):
        return None

    words, cur, w_start, w_end = [], "", None, None
    for ch, st, en in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append((cur, w_start, w_end))
            cur, w_start = "", None
            continue
        if w_start is None:
            w_start = st
        cur += ch
        w_end = en
    if cur:
        words.append((cur, w_start, w_end))
    # "..." pauses between hook / script / CTA come through as their own words
    words = [w for w in words if re.search(r"\w", w[0])]
    if not words:
        return None

    # Split at punctuation first, then break long phrases into even pieces so
    # no caption ends with a lone word ("...the same" / "argument,").
    phrases, cur_phrase = [], []
    for word in words:
        cur_phrase.append(word)
        if re.search(r"[.!?,;:]$", word[0]):
            phrases.append(cur_phrase)
            cur_phrase = []
    if cur_phrase:
        phrases.append(cur_phrase)
    captions = []
    for phrase in phrases:
        pieces = -(-len(phrase) // max_words)
        size = -(-len(phrase) // pieces)
        captions.extend(phrase[i:i + size] for i in range(0, len(phrase), size))
    return [
        {"text": " ".join(w[0] for w in c), "start": round(c[0][1], 3), "end": round(c[-1][2], 3)}
        for c in captions
    ]


def _audio_duration_seconds(path: str) -> float:
    """Read the real duration of the MP3 with ffprobe (ships with ffmpeg)."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def generate_voiceover(text: str, filename: str = "voiceover.mp3"):
    """Generate an MP3 of `text`. Returns (path, duration_s, captions) or None."""
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        print("[tts] No ELEVENLABS_API_KEY - rendering without voiceover.")
        return None

    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_VOICE_ID
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / filename

    try:
        print(f"[tts] Generating voiceover ({len(text)} chars, voice {voice_id[:8]}...)")
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": MODEL_ID,
                "voice_settings": {
                    "stability": 0.55,
                    "similarity_boost": 0.8,
                    "style": 0.25,
                },
            },
            timeout=120,
        )
        if not r.ok:
            print(f"[tts] ElevenLabs error {r.status_code}: {r.text[:200]}")
            return None

        data = r.json()
        out_path.write_bytes(base64.b64decode(data["audio_base64"]))
        duration = _audio_duration_seconds(out_path)
        captions = captions_from_alignment(data.get("alignment"))
        print(f"[tts] Voiceover ready: {out_path} ({duration:.1f}s, "
              f"{len(captions) if captions else 0} caption phrases)")
        return str(out_path), duration, captions
    except Exception as e:
        print(f"[tts] Voiceover failed ({type(e).__name__}: {e}) - continuing silent.")
        return None
