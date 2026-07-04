"""
elevenlabs_tts.py
Generate a voiceover MP3 for the daily coaching tip via the ElevenLabs API.

Requires:
  ELEVENLABS_API_KEY   - API key (if unset, generate_voiceover returns None
                         and the video renders silent, exactly as before)
  ELEVENLABS_VOICE_ID  - optional; defaults to "Adam" (deep male narration)

Returns (mp3_path, duration_seconds) or None on any failure — a voiceover
problem must never block the daily post.
"""

import os
import json
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

OUTPUT_DIR = Path(__file__).parent.parent / "output"
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # "Adam" - warm, confident male
MODEL_ID = "eleven_multilingual_v2"


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
    """Generate an MP3 of `text`. Returns (path, duration_s) or None."""
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
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
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

        out_path.write_bytes(r.content)
        duration = _audio_duration_seconds(out_path)
        print(f"[tts] Voiceover ready: {out_path} ({duration:.1f}s)")
        return str(out_path), duration
    except Exception as e:
        print(f"[tts] Voiceover failed ({type(e).__name__}: {e}) - continuing silent.")
        return None
