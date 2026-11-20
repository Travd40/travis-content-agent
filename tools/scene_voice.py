"""
scene_voice.py
Free voices for Logic and Harmony, the couple who open each video in a short
coaching session scene, plus the join that puts their lines in front of Coach
Tee's voiceover.

The couple speak with Kokoro (open source, Apache 2.0), which runs on the
GitHub Actions CPU runner with no API key or credits. The two model files are
downloaded once from the kokoro-onnx GitHub release and cached.

Nothing here may block the daily post: every public function returns None on
any failure, and the agent then posts the video without the scene.

Optional env vars:
  LOGIC_VOICE    (default am_michael)
  HARMONY_VOICE  (default af_heart)
  KOKORO_DIR     (default ~/.cache/kokoro)
  KOKORO_PYTHON  Python that has kokoro-onnx installed. Kokoro needs numpy 2
                 and the voice cloning package needs numpy 1, so the daily
                 workflow keeps Kokoro in its own virtual environment and
                 points this at it. Unset = use the current Python.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILE = "kokoro-v1.0.int8.onnx"
VOICES_FILE = "voices-v1.0.bin"

DEFAULT_VOICES = {"logic": "am_michael", "harmony": "af_heart"}
LINE_GAP_S = 0.45        # pause between the couple's lines
HANDOFF_GAP_S = 0.7      # pause before Coach Tee speaks
SAMPLE_RATE = 24000


def voice_for(speaker: str) -> str:
    return os.getenv(f"{speaker.upper()}_VOICE") or DEFAULT_VOICES[speaker]


def _model_dir() -> Path:
    return Path(os.getenv("KOKORO_DIR") or Path.home() / ".cache" / "kokoro")


def _ensure_models() -> tuple[Path, Path]:
    d = _model_dir()
    d.mkdir(parents=True, exist_ok=True)
    for name in (MODEL_FILE, VOICES_FILE):
        target = d / name
        if not target.exists() or target.stat().st_size == 0:
            print(f"[scene] Downloading {name}...")
            tmp = target.with_suffix(target.suffix + ".part")
            with urllib.request.urlopen(RELEASE + name, timeout=180) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            tmp.replace(target)
    return d / MODEL_FILE, d / VOICES_FILE


def speak_scene(scene: list[dict], filename: str = "scene.wav"):
    """Speak the couple's lines. scene is [{"speaker": "logic"|"harmony", "line": str}].
    Returns (wav_path, duration_s, captions) or None. Each caption is
    {"text", "start", "end", "speaker"} and covers one whole line."""
    if not scene:
        return None
    other_python = os.getenv("KOKORO_PYTHON")
    # Compare the paths as written: a virtual environment's python is a link to
    # the same program, so resolving the links would hide the difference.
    if other_python and os.path.abspath(other_python) != os.path.abspath(sys.executable):
        return _speak_scene_in(other_python, scene, filename)
    try:
        import numpy as np
        import soundfile as sf
        from kokoro_onnx import Kokoro
    except ImportError as e:
        print(f"[scene] Kokoro not installed ({e}) - skipping the scene.")
        return None
    try:
        model, voices = _ensure_models()
        kokoro = Kokoro(str(model), str(voices))
        gap = np.zeros(int(LINE_GAP_S * SAMPLE_RATE), dtype=np.float32)
        clips, captions, t = [], [], 0.0
        for i, item in enumerate(scene):
            samples, sr = kokoro.create(item["line"], voice=voice_for(item["speaker"]),
                                        speed=1.0, lang="en-us")
            if sr != SAMPLE_RATE:
                raise RuntimeError(f"unexpected sample rate {sr}")
            samples = np.asarray(samples, dtype=np.float32)
            seconds = len(samples) / sr
            captions.append({"text": item["line"], "start": round(t, 3),
                             "end": round(t + seconds, 3), "speaker": item["speaker"]})
            clips.append(samples)
            t += seconds
            if i < len(scene) - 1:
                clips.append(gap)
                t += LINE_GAP_S
            print(f"[scene]   {item['speaker']} ({seconds:.1f}s): {item['line']}")
        OUTPUT_DIR.mkdir(exist_ok=True)
        wav_path = OUTPUT_DIR / filename
        sf.write(str(wav_path), np.concatenate(clips), SAMPLE_RATE)
        return str(wav_path), round(t, 3), captions
    except Exception as e:
        print(f"[scene] Scene voices failed ({type(e).__name__}: {e}).")
        return None


def _speak_scene_in(python: str, scene: list[dict], filename: str):
    """Run speak_scene under another Python and read its result back."""
    try:
        env = {**os.environ, "KOKORO_PYTHON": ""}
        done = subprocess.run([python, __file__, "--speak", json.dumps(scene), filename],
                              capture_output=True, text=True, timeout=600, env=env)
        for line in done.stdout.splitlines():
            if line.startswith("RESULT "):
                result = json.loads(line[len("RESULT "):])
                return (result[0], result[1], result[2]) if result else None
            print(line)
        print(f"[scene] Kokoro run gave no result (exit {done.returncode}): {done.stderr[-400:]}")
        return None
    except Exception as e:
        print(f"[scene] Kokoro run failed ({type(e).__name__}: {e}).")
        return None


def join_scene_and_coach(scene_wav: str, scene_duration: float, scene_captions: list[dict],
                         coach_audio: str, coach_duration: float, coach_captions: list[dict] | None,
                         filename: str = "voiceover_scene.mp3"):
    """Put the couple's lines in front of Coach Tee's voiceover.
    Returns (mp3_path, duration_s, captions, scene_end_s) or None. Coach Tee's
    captions are moved later by the length of the scene plus the pause."""
    try:
        out_path = OUTPUT_DIR / filename
        offset = scene_duration + HANDOFF_GAP_S
        graph = (
            f"[0:a]loudnorm=I=-16:TP=-1.5,aresample=44100,apad=pad_dur={HANDOFF_GAP_S}[s];"
            f"[1:a]aresample=44100[c];"
            f"[s][c]concat=n=2:v=0:a=1[out]"
        )
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", scene_wav, "-i", coach_audio,
                        "-filter_complex", graph, "-map", "[out]", "-ac", "1",
                        "-b:a", "128k", str(out_path)],
                       check=True, timeout=120)
        captions = list(scene_captions)
        for c in coach_captions or []:
            captions.append({**c, "start": round(c["start"] + offset, 3),
                             "end": round(c["end"] + offset, 3), "speaker": "coach"})
        duration = round(offset + coach_duration, 3)
        print(f"[scene] Scene + Coach Tee voiceover ready: {out_path} ({duration:.1f}s)")
        return str(out_path), duration, captions, round(offset, 3)
    except Exception as e:
        print(f"[scene] Could not join the scene to the voiceover ({type(e).__name__}: {e}).")
        return None


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--speak":
        print("RESULT " + json.dumps(speak_scene(json.loads(sys.argv[2]), sys.argv[3])))
        sys.exit(0)
    demo = [
        {"speaker": "harmony", "line": "I'm done."},
        {"speaker": "logic", "line": "Why? What did I do?"},
    ]
    print(speak_scene(demo, "scene_test.wav"))
