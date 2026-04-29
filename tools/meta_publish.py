"""
meta_publish.py
Publishes a video as an Instagram Reel and a Facebook video using the Meta Graph API.

Requires the following in .env:
    META_GRAPH_VERSION=v21.0
    META_PAGE_ACCESS_TOKEN=...      # Long-lived Page Access Token
    META_FB_PAGE_ID=...             # Facebook Page numeric ID
    META_IG_USER_ID=...             # Instagram Business Account ID (NOT the handle)
    META_VIDEO_HOST=github          # how we expose the video publicly (github | supabase | s3)

IG publishing requires a PUBLIC https URL for the video. We reuse upload_video.py
(which pushes to GitHub and returns a raw.githubusercontent.com URL) to get one.

Returns a dict summarizing what posted:
    { "instagram": {"id": ...} | {"error": ...},
      "facebook":  {"id": ...} | {"error": ...},
      "video_url": "..." }
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"{name} not set in .env")
    return val


def _public_video_url(video_path: str) -> str:
    """Upload local video to GitHub and return its public raw URL."""
    from upload_video import upload_video
    return upload_video(video_path)


def publish_instagram_reel(video_url: str, caption: str) -> dict:
    """
    IG Reels is a 2-step publish:
      1) POST /{ig-user-id}/media with media_type=REELS, video_url, caption
      2) Poll /{container-id}?fields=status_code until FINISHED
      3) POST /{ig-user-id}/media_publish with creation_id={container-id}
    """
    ig_user_id = _require("META_IG_USER_ID")
    token = _require("META_PAGE_ACCESS_TOKEN")

    # Step 1: create container
    create = requests.post(
        f"{GRAPH}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": token,
        },
        timeout=60,
    )
    if create.status_code != 200:
        return {"error": f"IG container create failed: {create.status_code} {create.text}"}

    container_id = create.json().get("id")
    if not container_id:
        return {"error": f"IG container create returned no id: {create.json()}"}

    # Step 2: poll until processing finishes (Meta recommends up to ~5 min for Reels)
    deadline = time.time() + 300
    last_status = None
    while time.time() < deadline:
        status = requests.get(
            f"{GRAPH}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=30,
        ).json()
        last_status = status.get("status_code")
        if last_status == "FINISHED":
            break
        if last_status == "ERROR":
            return {"error": f"IG container errored: {status}"}
        time.sleep(5)
    else:
        return {"error": f"IG container never finished processing (last status: {last_status})"}

    # Step 3: publish
    publish = requests.post(
        f"{GRAPH}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )
    if publish.status_code != 200:
        return {"error": f"IG publish failed: {publish.status_code} {publish.text}"}

    return {"id": publish.json().get("id"), "container_id": container_id}


def publish_facebook_video(video_url: str, caption: str) -> dict:
    """Post a hosted video to a FB Page. Uses file_url for async ingest."""
    page_id = _require("META_FB_PAGE_ID")
    token = _require("META_PAGE_ACCESS_TOKEN")

    resp = requests.post(
        f"{GRAPH}/{page_id}/videos",
        data={
            "file_url": video_url,
            "description": caption,
            "access_token": token,
        },
        timeout=120,
    )
    if resp.status_code != 200:
        return {"error": f"FB publish failed: {resp.status_code} {resp.text}"}
    return {"id": resp.json().get("id")}


def publish(video_path: str, caption: str, hashtags: str = "") -> dict:
    """Publish to IG Reel + FB video. Returns per-platform result + the public URL used."""
    full_caption = f"{caption}\n\n{hashtags}".strip()

    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)

    print(f"[meta] Uploading video to public host...")
    video_url = _public_video_url(video_path)
    print(f"[meta] Public URL: {video_url}")

    print(f"[meta] Publishing to Instagram Reels...")
    ig_result = publish_instagram_reel(video_url, full_caption)
    print(f"[meta] IG: {ig_result}")

    print(f"[meta] Publishing to Facebook Page...")
    fb_result = publish_facebook_video(video_url, full_caption)
    print(f"[meta] FB: {fb_result}")

    return {"instagram": ig_result, "facebook": fb_result, "video_url": video_url}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python meta_publish.py <video_path> [caption]")
        sys.exit(1)

    path = sys.argv[1]
    cap = sys.argv[2] if len(sys.argv) >= 3 else (
        "Becoming a trained partner starts with one decision. "
        "Book a free 15-min call — link in bio."
    )
    result = publish(path, cap)
    print("\n[meta] Result:", result)
