"""
agent.py — Travis Dixon Content Agent
--------------------------------------
Runs automatically every day.
Each run:
  1. Generates a coaching tip (Anthropic Claude, dedupes against last 20)
  2. Renders a branded 9:16 video (Remotion)
  3. Saves video + caption to output/ folder
  4. Publishes to Instagram Reels + Facebook Page via Meta Graph API

Usage:
  python agent.py        # Start scheduler (daily at POST_TIME, runs forever)
  python agent.py --now  # Run once right now (for testing)
"""

import os
import sys
import json
import traceback
import schedule
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Flush prints immediately so failures show up in scheduler.log instead of
# disappearing when the process is killed mid-run.
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

load_dotenv(override=True)

sys.path.insert(0, str(Path(__file__).parent / "tools"))

from generate_content import generate_content
from render_video import render_video
from blog_promo import get_blog_promo

POST_TIME = os.getenv("POST_TIME", "10:00")
LOG_FILE  = Path(__file__).parent / "post_log.json"
OUTPUT_DIR = Path(__file__).parent / "output"
FAILURE_LOG = Path(__file__).parent / "failures.log"
LAST_FAILURE_FILE = Path(__file__).parent / "LAST_FAILURE.txt"


def record_failure(stage: str, err: BaseException) -> None:
    """Append a failure entry to failures.log AND overwrite LAST_FAILURE.txt
    so a missed post is visible at a glance instead of buried in scheduler.log."""
    ts = datetime.now().isoformat()
    tb = traceback.format_exc()
    summary = f"{ts}  [{stage}]  {type(err).__name__}: {err}"
    block = summary + "\n" + tb + "\n"
    try:
        with open(FAILURE_LOG, "a", encoding="utf-8") as f:
            f.write(block + ("-" * 60) + "\n")
        with open(LAST_FAILURE_FILE, "w", encoding="utf-8") as f:
            f.write(block)
    except Exception as write_err:
        print(f"[agent] could not write failure log: {write_err}", flush=True)
    print(f"[agent] FAILURE recorded → failures.log / LAST_FAILURE.txt", flush=True)


def load_post_count() -> int:
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f).get("total_posts", 0)
    return 0


def save_post_log(count: int, content: dict, video_path: str, caption_path: str,
                  meta_result: dict | None = None, youtube_result: dict | None = None):
    existing = []
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            existing = json.load(f).get("history", [])

    entry = {
        "post_number": count,
        "timestamp": datetime.now().isoformat(),
        "category": content.get("category"),
        "tip": content.get("tip"),
        "video": video_path,
        "caption_file": caption_path,
    }
    if meta_result:
        entry["meta_result"] = meta_result
    if youtube_result:
        entry["youtube_result"] = youtube_result

    with open(LOG_FILE, "w") as f:
        json.dump({
            "total_posts": count,
            "history": existing + [entry],
        }, f, indent=2)


def run_pipeline():
    print("\n" + "=" * 60)
    print(f"[agent] Running — {datetime.now().strftime('%A %Y-%m-%d %H:%M')}")
    print("=" * 60)

    post_count = load_post_count()

    # Step 1: Generate content
    # Friday = blog promo day (drives traffic to /blog posts).
    # Other days = normal coaching tip from Claude.
    is_friday = datetime.now().weekday() == 4
    if is_friday:
        print(f"\n[agent] Friday → using blog promo rotation for post #{post_count + 1}...")
        try:
            content = get_blog_promo(post_count)
        except Exception as e:
            record_failure("blog_promo", e)
            raise
    else:
        print(f"\n[agent] Generating coaching tip #{post_count + 1}...")
        try:
            content = generate_content(post_count)
        except Exception as e:
            record_failure("generate_content", e)
            raise
    print(f"[agent] Category : {content['category']}")
    print(f"[agent] Tip      : {content['tip']}")

    # Step 2: Render video
    print(f"\n[agent] Rendering video...")
    safe_cat = content['category'].replace(' ', '_').replace("'", '').replace('&', 'and').replace('/', '-')
    filename = f"post_{post_count + 1:04d}_{safe_cat}.mp4"
    try:
        video_path = render_video(content, filename)
    except Exception as e:
        record_failure("render_video", e)
        raise

    # Step 3: Save caption + hashtags as a text file next to the video
    caption_filename = filename.replace(".mp4", "_caption.txt")
    caption_path = str(OUTPUT_DIR / caption_filename)
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(f"CATEGORY: {content['category']}\n")
        f.write(f"TIP: {content['tip']}\n\n")
        f.write("--- CAPTION (copy & paste) ---\n\n")
        f.write(content["caption"])
        f.write("\n\n")
        f.write(content["hashtags"])
        f.write("\n")

    # Step 4: Publish to IG Reels + FB Page via Meta Graph API (non-blocking)
    meta_result = None
    if os.getenv("META_PAGE_ACCESS_TOKEN"):
        print(f"\n[agent] Publishing to Instagram + Facebook...")
        try:
            from meta_publish import publish
            meta_result = publish(
                video_path=video_path,
                caption=content["caption"],
                hashtags=content["hashtags"],
            )
            print(f"[agent] Meta result: {meta_result}")
        except Exception as e:
            print(f"[agent] ERROR: Meta publish failed — {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            record_failure("meta_publish", e)
            raise
    else:
        print(f"\n[agent] No META_PAGE_ACCESS_TOKEN found — skipping auto-post.")

    # Step 5: Publish the same video to YouTube as a public Short.
    # A YouTube failure must not lose the post log (IG/FB already went out),
    # so the error is recorded, the log is saved, THEN the run fails loudly.
    youtube_result = None
    youtube_error = None
    if os.getenv("YOUTUBE_REFRESH_TOKEN"):
        print(f"\n[agent] Publishing to YouTube...")
        try:
            from youtube_publish import publish as youtube_publish
            youtube_result = youtube_publish(
                video_path=video_path,
                tip=content["tip"],
                caption=content["caption"],
                hashtags=content["hashtags"],
            )
            print(f"[agent] YouTube result: {youtube_result}")
        except Exception as e:
            print(f"[agent] ERROR: YouTube publish failed — {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()
            record_failure("youtube_publish", e)
            youtube_error = e
    else:
        print(f"\n[agent] No YOUTUBE_REFRESH_TOKEN found — skipping YouTube upload.")

    # Log it (including meta_result so insights can look up this post later)
    new_count = post_count + 1
    save_post_log(new_count, content, video_path, caption_path,
                  meta_result=meta_result, youtube_result=youtube_result)

    if youtube_error:
        raise youtube_error

    print(f"\n[agent] Done! Post #{new_count} ready.")
    print(f"[agent] Video  : {video_path}")
    print(f"[agent] Caption: {caption_path}")
    print("=" * 60 + "\n")


def safe_run_pipeline():
    """Wrapper for the scheduler: log failures but don't kill the long-running loop."""
    try:
        run_pipeline()
    except Exception as e:
        if not LAST_FAILURE_FILE.exists() or LAST_FAILURE_FILE.stat().st_mtime < time.time() - 60:
            record_failure("run_pipeline", e)
        print(f"[agent] Run failed: {type(e).__name__}: {e}", flush=True)


def start_scheduler():
    print(f"[agent] Scheduler started — daily at {POST_TIME}")
    print("[agent] Videos saved to output/ folder. Press Ctrl+C to stop.\n")

    schedule.every().day.at(POST_TIME).do(safe_run_pipeline)

    print(f"[agent] Next run: {schedule.next_run()}\n")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    if "--now" in sys.argv:
        run_pipeline()
    else:
        start_scheduler()
