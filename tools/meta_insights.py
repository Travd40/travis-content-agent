"""
meta_insights.py
Pulls IG Reel + FB Page post insights for every post in post_log.json
that has a meta_result attached. Writes per-post stats to insights.csv
and can print the top performers.

Usage:
    python tools/meta_insights.py                # Pull all, write CSV
    python tools/meta_insights.py --recent       # Only posts in the last 14 days
    python tools/meta_insights.py --winners      # Print top 3 by engagement
    python tools/meta_insights.py --recent --winners
"""

import os
import sys
import csv
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

PROJECT_ROOT = Path(__file__).parent.parent
LOG_FILE = PROJECT_ROOT / "post_log.json"
INSIGHTS_CSV = PROJECT_ROOT / "insights.csv"


def _token() -> str:
    t = os.getenv("META_PAGE_ACCESS_TOKEN")
    if not t:
        raise RuntimeError("META_PAGE_ACCESS_TOKEN not set in .env")
    return t


def get_ig_reel_insights(media_id: str) -> dict:
    """
    Pull metrics for a published IG Reel.
    Step 1: basic fields (likes, comments, permalink) — needs only instagram_basic
    Step 2: insights endpoint (reach, saved, plays) — needs instagram_manage_insights,
            which we may not have. Fail soft so we still get basic numbers.
    """
    out: dict = {}

    # Step 1: basic media fields (always works with instagram_basic)
    basic = requests.get(
        f"{GRAPH}/{media_id}",
        params={
            "fields": "like_count,comments_count,caption,permalink,media_type,timestamp",
            "access_token": _token(),
        },
        timeout=30,
    )
    if basic.status_code == 200:
        bd = basic.json()
        out["likes"] = bd.get("like_count")
        out["comments"] = bd.get("comments_count")
        out["permalink"] = bd.get("permalink")
        out["media_type"] = bd.get("media_type")
        out["posted_at"] = bd.get("timestamp")
    else:
        out["_basic_error"] = f"{basic.status_code} {basic.text[:200]}"

    # Step 2: richer insights (reach, saved, plays, shares, avg watch time)
    metrics = "reach,shares,saved,plays,total_interactions,ig_reels_avg_watch_time"
    insights = requests.get(
        f"{GRAPH}/{media_id}/insights",
        params={"metric": metrics, "access_token": _token()},
        timeout=30,
    )
    if insights.status_code == 200:
        for m in insights.json().get("data", []):
            vals = m.get("values", [])
            if vals:
                out[m["name"]] = vals[0].get("value")
    else:
        # Don't mark the whole post as errored — basic data is still useful
        out["_insights_note"] = "needs instagram_manage_insights permission"

    return out


def get_fb_video_insights(video_id: str) -> dict:
    """Pull metrics for a FB Page video post."""
    fields = "views,length,permalink_url,likes.summary(total_count),comments.summary(total_count)"
    resp = requests.get(
        f"{GRAPH}/{video_id}",
        params={"fields": fields, "access_token": _token()},
        timeout=30,
    )
    if resp.status_code != 200:
        return {"_error": f"{resp.status_code} {resp.text[:200]}"}
    data = resp.json()
    return {
        "views": data.get("views"),
        "length": data.get("length"),
        "likes": data.get("likes", {}).get("summary", {}).get("total_count"),
        "comments": data.get("comments", {}).get("summary", {}).get("total_count"),
        "permalink": data.get("permalink_url"),
    }


def collect(recent_only: bool = False) -> list[dict]:
    """Walk post_log history, pull insights for any post with meta_result."""
    if not LOG_FILE.exists():
        print(f"[insights] No {LOG_FILE.name} found.")
        return []

    history = json.loads(LOG_FILE.read_text()).get("history", [])
    cutoff = datetime.now() - timedelta(days=14) if recent_only else None

    results = []
    for post in history:
        meta = post.get("meta_result")
        if not meta:
            continue

        ts = post.get("timestamp")
        if cutoff and ts:
            try:
                if datetime.fromisoformat(ts) < cutoff:
                    continue
            except Exception:
                pass

        ig = meta.get("instagram") or {}
        fb = meta.get("facebook") or {}
        ig_id = ig.get("id") if isinstance(ig, dict) else None
        fb_id = fb.get("id") if isinstance(fb, dict) else None

        if not (ig_id or fb_id):
            continue

        row = {
            "post_number": post.get("post_number"),
            "timestamp": ts,
            "category": post.get("category"),
            "tip": (post.get("tip") or "")[:100],
        }

        if ig_id:
            print(f"[insights] IG  post #{post.get('post_number')} ->{ig_id}")
            for k, v in get_ig_reel_insights(ig_id).items():
                row[f"ig_{k}"] = v

        if fb_id:
            print(f"[insights] FB  post #{post.get('post_number')} ->{fb_id}")
            for k, v in get_fb_video_insights(fb_id).items():
                row[f"fb_{k}"] = v

        results.append(row)

    return results


def write_csv(rows: list[dict]):
    if not rows:
        print("[insights] No rows to write.")
        return
    all_keys = set()
    for r in rows:
        all_keys.update(r.keys())

    # Sort columns: metadata ->ig_* ->fb_*
    def sort_key(k: str):
        return (0 if k in ("post_number", "timestamp", "category", "tip") else
                1 if k.startswith("ig_") else 2, k)

    keys = sorted(all_keys, key=sort_key)

    with open(INSIGHTS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"[insights] Wrote {len(rows)} rows to {INSIGHTS_CSV}")


def score(row: dict) -> int:
    """Weighted engagement score. Shares + saves count 3x (strongest virality signals)."""
    return (
        (row.get("ig_likes") or 0)
        + (row.get("ig_comments") or 0) * 2
        + (row.get("ig_shares") or 0) * 3
        + (row.get("ig_saved") or 0) * 3
        + (row.get("fb_likes") or 0)
        + (row.get("fb_comments") or 0) * 2
    )


def show_winners(rows: list[dict], top_n: int = 3):
    if not rows:
        print("[insights] No posts with insights to rank.")
        return
    ranked = sorted(rows, key=score, reverse=True)
    print(f"\n[insights] Top {top_n} winners by weighted engagement:")
    print("-" * 80)
    for i, r in enumerate(ranked[:top_n], 1):
        print(f"{i}. Post #{r.get('post_number')} | {r.get('category')} | score: {score(r)}")
        print(f"   Tip: {r.get('tip')}")
        ig_line = (
            f"IG reach={r.get('ig_reach')}  likes={r.get('ig_likes')}  "
            f"shares={r.get('ig_shares')}  saves={r.get('ig_saved')}  plays={r.get('ig_plays')}"
        )
        fb_line = (
            f"FB views={r.get('fb_views')}  likes={r.get('fb_likes')}  "
            f"comments={r.get('fb_comments')}  reactions={r.get('fb_reactions')}"
        )
        print(f"   {ig_line}")
        print(f"   {fb_line}")
        if r.get("ig_permalink"):
            print(f"   IG link: {r.get('ig_permalink')}")
        if r.get("fb_permalink"):
            print(f"   FB link: {r.get('fb_permalink')}")
        print()


if __name__ == "__main__":
    recent = "--recent" in sys.argv
    winners = "--winners" in sys.argv

    rows = collect(recent_only=recent)
    print(f"\n[insights] Collected insights for {len(rows)} post(s).")
    write_csv(rows)
    if winners:
        show_winners(rows)
