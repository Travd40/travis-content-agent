"""
render_video.py
Triggers Remotion CLI to render a branded coaching tip video.
Output: MP4 file at the specified path (1080x1920, 30fps, 7 seconds)
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

REMOTION_DIR = Path(__file__).parent.parent / "remotion"
OUTPUT_DIR   = Path(__file__).parent.parent / "output"


def render_video(content: dict, output_filename: str = None) -> str:
    """
    Renders a coaching tip video using Remotion.

    Args:
        content: dict with keys: category, tip (website/coachName pulled from env)
        output_filename: optional filename; auto-generated if not provided

    Returns:
        Absolute path to the rendered MP4 file
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    if not output_filename:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"coaching_tip_{ts}.mp4"

    output_path = OUTPUT_DIR / output_filename

    props = {
        "category":     content.get("category", "COACHING TIP"),
        "tip":          content.get("tip", ""),
        "website":      os.getenv("COACHING_WEBSITE", "travis-coaching-site-1.onrender.com"),
        "coachName":    os.getenv("COACHING_NAME", "Travis Dixon Coaching"),
        "bookLink":     os.getenv("BOOK_LINK", "https://www.amazon.com/dp/B0GPSNXGY8"),
        "calendlyLink": os.getenv("CALENDLY_LINK", "https://calendly.com/travd40/15-minute-strategy-call"),
    }

    props_path = REMOTION_DIR / "props.json"
    with open(props_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False)

    print(f"[render] Rendering: {props['category']} — \"{props['tip']}\"")
    print(f"[render] Output: {output_path}")

    # Ensure Node.js is on PATH for subprocess
    env = os.environ.copy()
    node_dir = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "nodejs")
    if os.path.isdir(node_dir) and node_dir not in env.get("PATH", ""):
        env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")

    cmd = [
        "npx", "remotion", "render",
        "src/index.jsx",
        "CoachingTip",
        str(output_path),
        f"--props={props_path}",
        "--log=verbose",
    ]

    result = subprocess.run(
        cmd,
        cwd=str(REMOTION_DIR),
        capture_output=False,   # stream output so user can see progress
        shell=True,             # required on Windows for npx
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Remotion render failed (exit code {result.returncode})")

    print(f"[render] Done: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    test_content = {
        "category": "COUPLES COACHING",
        "tip": "A trained partner speaks with intention, not just emotion.",
    }
    path = render_video(test_content)
    print(f"Video saved to: {path}")
