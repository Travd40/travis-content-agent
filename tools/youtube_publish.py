"""
youtube_publish.py
Uploads the day's rendered video to YouTube as a public Short, right after
the Meta (IG/FB) publish. Title comes from the tip, description from the
caption + Travis's funnel CTAs, tags from the hashtags.

Env vars required (GitHub Actions secrets, same values as the
travis_coaching_site repo):
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN
Optional:
  YOUTUBE_PLAYLIST_ID     (auto-adds the upload to this playlist)
  COACHING_WEBSITE / BOOK_LINK / CALENDLY_LINK  (already set for the agent)
"""

import os
import re
import time
from pathlib import Path

MAX_TITLE = 100


# ---------------------------------------------------------------------------
# Metadata builders — pure functions so they're trivially unit-testable.
# ---------------------------------------------------------------------------
def build_title(tip: str) -> str:
    """Tip → YouTube title, capped at 100 chars on a word boundary."""
    t = " ".join(tip.split())
    if len(t) <= MAX_TITLE:
        return t
    cut = t[: MAX_TITLE - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"


def build_description(caption: str, hashtags: str) -> str:
    website = os.getenv("COACHING_WEBSITE", "travis-coaching-site-1.onrender.com")
    calendly = os.getenv("CALENDLY_LINK", "https://calendly.com/travd40/15-minute-strategy-call")
    book = os.getenv("BOOK_LINK", "https://www.amazon.com/dp/B0GPSNXGY8")
    site_url = website if website.startswith("http") else f"https://{website}"
    funnel = (
        "——————————\n\n"
        '📧 FREE 5-DAY EMAIL COURSE — "From Stray to Trained":\n'
        f"{site_url}/5days\n\n"
        "📅 BOOK A FREE 15-MIN STRATEGY CALL:\n"
        f"{calendly}\n\n"
        "📖 GET THE BOOK — I Am A Dog:\n"
        f"{book}\n\n"
        f"🌐 {website}"
    )
    return f"{caption.strip()}\n\n{funnel}\n\n{hashtags.strip()}"


def extract_tags(hashtags: str) -> list[str]:
    """Hashtags → YouTube tags, capped near YouTube's 500-char limit."""
    tags = re.findall(r"#(\w+)", hashtags)
    out, total = [], 0
    for t in tags:
        cost = len(t) + 2
        if total + cost > 480:
            break
        out.append(t)
        total += cost
    return out


# ---------------------------------------------------------------------------
# Auth + upload — google libs imported lazily so unit tests don't need them.
# ---------------------------------------------------------------------------
def _build_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request

    # .strip() guards against trailing newlines pasted into GitHub secrets.
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"].strip(),
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"].strip(),
    )
    try:
        creds.refresh(Request())
    except RefreshError as exc:
        raise RuntimeError(
            f"YouTube auth failed: Google rejected the refresh token ({exc}). "
            "Re-mint it (see travis_coaching_site: python youtube_upload.py --auth) "
            "and update the YOUTUBE_REFRESH_TOKEN secret in this repo."
        ) from exc
    return creds


def publish(video_path: str, tip: str, caption: str, hashtags: str) -> dict:
    """Uploads the video. Returns {'video_id': ..., 'url': ...}."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f"video not found: {video}")

    title = build_title(tip)
    description = build_description(caption, hashtags)
    tags = extract_tags(hashtags)

    print(f"[youtube] Title: {title}")
    print(f"[youtube] Tags:  {', '.join(tags) if tags else '(none)'}")

    youtube = build("youtube", "v3", credentials=_build_credentials(), cache_discovery=False)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }
    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retries = 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as exc:
            if exc.resp.status in (500, 502, 503, 504) and retries < 5:
                wait = 2 ** retries
                print(f"[youtube] transient {exc.resp.status}, retry in {wait}s")
                time.sleep(wait)
                retries += 1
                continue
            raise

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"[youtube] ✓ Uploaded: {url}")

    playlist_id = os.getenv("YOUTUBE_PLAYLIST_ID", "").strip()
    if playlist_id:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
        print(f"[youtube] ✓ Added to playlist {playlist_id}")

    return {"video_id": video_id, "url": url}
