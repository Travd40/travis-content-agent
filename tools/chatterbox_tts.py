"""
chatterbox_tts.py
Free voiceover in Travis's own voice, cloned on the fly by Chatterbox
(Resemble AI, MIT license) from voice/travis-reference.wav. Runs on the
GitHub Actions CPU runner, no API key or credits needed.

Same contract as elevenlabs_tts.generate_voiceover: returns
(mp3_path, duration_seconds, captions) or None on any failure, so a voice
problem never blocks the daily post. Chatterbox has no word timestamps, so
the script is spoken one sentence at a time; each sentence's real start and
end come from the audio, and the words inside it are spread by length.

Optional env vars:
  CHATTERBOX_EXAGGERATION  (default 0.5; higher = more emotion)
  CHATTERBOX_CFG           (default 0.5; lower = slower, steadier pacing)
"""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
REFERENCE = ROOT / "voice" / "travis-reference.wav"
SENTENCE_GAP_S = 0.25
CAPTION_MAX_WORDS = 6


def split_sentences(text: str) -> list[str]:
    """Script -> sentences. The ' ... ' joins between hook, script and CTA
    count as breaks too."""
    text = text.replace("...", ". ")
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    out = []
    for p in parts:
        p = p.strip(" .")
        if re.search(r"\w", p):
            out.append(p if p[-1] in "!?" else p + ".")
    return out


def sentence_captions(sentence: str, start: float, end: float,
                      max_words: int = CAPTION_MAX_WORDS) -> list[dict]:
    """One spoken sentence -> even caption phrases, timed by character count."""
    words = sentence.split()
    if not words:
        return []
    pieces = -(-len(words) // max_words)
    size = -(-len(words) // pieces)
    chunks = [words[i:i + size] for i in range(0, len(words), size)]
    total = sum(len(" ".join(c)) for c in chunks) or 1
    out, t = [], start
    for c in chunks:
        text = " ".join(c)
        span = (end - start) * len(text) / total
        out.append({"text": text, "start": round(t, 3), "end": round(t + span, 3)})
        t += span
    return out


def generate_voiceover(text: str, filename: str = "voiceover.mp3"):
    """Generate an MP3 of `text` in Travis's voice. Returns (path, duration_s, captions) or None."""
    if not REFERENCE.exists():
        print(f"[chatterbox] No reference voice at {REFERENCE} - skipping.")
        return None
    try:
        import torch
        import torchaudio
        from chatterbox.tts import ChatterboxTTS
    except ImportError as e:
        print(f"[chatterbox] Not installed ({e}) - skipping.")
        return None

    OUTPUT_DIR.mkdir(exist_ok=True)
    wav_path = OUTPUT_DIR / (Path(filename).stem + ".wav")
    out_path = OUTPUT_DIR / filename
    exaggeration = float(os.getenv("CHATTERBOX_EXAGGERATION", "0.5"))
    cfg = float(os.getenv("CHATTERBOX_CFG", "0.5"))

    try:
        sentences = split_sentences(text)
        print(f"[chatterbox] Speaking {len(sentences)} sentences in Travis's voice (CPU)...")
        model = ChatterboxTTS.from_pretrained(device="cpu")
        model.prepare_conditionals(str(REFERENCE), exaggeration=exaggeration)
        sr = model.sr
        gap = torch.zeros(1, int(SENTENCE_GAP_S * sr))

        clips, captions, t = [], [], 0.0
        for i, sentence in enumerate(sentences, 1):
            wav = model.generate(sentence, exaggeration=exaggeration, cfg_weight=cfg)
            seconds = wav.shape[-1] / sr
            captions += sentence_captions(sentence, t, t + seconds)
            clips += [wav, gap]
            t += seconds + SENTENCE_GAP_S
            print(f"[chatterbox]   {i}/{len(sentences)} ({seconds:.1f}s): {sentence[:60]}")

        torchaudio.save(str(wav_path), torch.cat(clips, dim=-1), sr)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
                        "-af", "loudnorm=I=-16:TP=-1.5", "-b:a", "128k", str(out_path)],
                       check=True, timeout=120)
        duration = round(t - SENTENCE_GAP_S, 3)
        print(f"[chatterbox] Voiceover ready: {out_path} ({duration:.1f}s, {len(captions)} caption phrases)")
        return str(out_path), duration, captions
    except Exception as e:
        print(f"[chatterbox] Voiceover failed ({type(e).__name__}: {e}).")
        return None


if __name__ == "__main__":
    import sys
    line = " ".join(sys.argv[1:]) or (
        "Why does he shut down every time we argue? ... He's not ignoring you. "
        "He's flooded. Give him twenty minutes, then come back to the conversation."
    )
    print(generate_voiceover(line, "chatterbox_test.mp3"))
