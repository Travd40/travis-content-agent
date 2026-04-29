"""
schedule_post.py
Posts caption + video to Buffer (Facebook + TikTok) using Buffer's GraphQL API.

Video is uploaded to GitHub first, then the public URL is passed to Buffer
so TikTok posts include the actual video (not just a logo image).

Setup: Generate a personal API key at publish.buffer.com/settings/api
       and set BUFFER_ACCESS_TOKEN in .env
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

BUFFER_API = "https://api.buffer.com"

CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
    createPost(input: $input) {
        ... on PostActionSuccess { post { id } }
        ... on NotFoundError { message }
        ... on UnauthorizedError { message }
        ... on UnexpectedError { message }
        ... on InvalidInputError { message }
        ... on LimitReachedError { message }
        ... on RestProxyError { message code }
    }
}
"""


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def get_channels(token):
    """Fetch all connected channels from Buffer."""
    resp = requests.post(
        BUFFER_API,
        headers=_headers(token),
        json={"query": "{ account { channels { id name service } } }"},
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Buffer API error: {data['errors']}")
    return data["data"]["account"]["channels"]


def _build_input(channel, text, category, video_url=None):
    """Build the createPost input for a specific channel's service."""
    base = {
        "channelId": channel["id"],
        "text": text,
        "mode": "addToQueue",
        "schedulingType": "automatic",
    }

    service = channel["service"]
    if service == "facebook":
        base["metadata"] = {"facebook": {"type": "post"}}
    elif service == "tiktok":
        base["metadata"] = {"tiktok": {"title": category or "Coaching Tip"}}
    elif service == "instagram":
        base["metadata"] = {"instagram": {"type": "reel", "shouldShareToFeed": True}}

    # Attach video if we have a URL
    if video_url:
        base["assets"] = {
            "videos": [{"url": video_url, "metadata": {"title": category or "Coaching Tip"}}]
        }

    return base


def schedule_post(video_path, caption, hashtags, scheduled_at, category="Coaching Tip"):
    token = os.getenv("BUFFER_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("BUFFER_ACCESS_TOKEN not set in .env")

    full_text = f"{caption}\n\n{hashtags}"

    # Upload video to GitHub to get a public URL
    video_url = None
    if video_path and os.path.exists(video_path):
        try:
            from upload_video import upload_video
            video_url = upload_video(video_path)
        except Exception as e:
            print(f"[buffer] WARNING: Video upload failed — {e}")
            print(f"[buffer] Posting text-only. Attach video manually in Buffer dashboard.")

    channels = get_channels(token)
    if not channels:
        raise RuntimeError("No channels found in Buffer account")

    print(f"[buffer] Found {len(channels)} channel(s):")
    for ch in channels:
        print(f"  - {ch['name']} ({ch['service']})")

    successes = 0
    for ch in channels:
        variables = {"input": _build_input(ch, full_text, category, video_url)}

        print(f"[buffer] Posting to {ch['name']} ({ch['service']})...")
        resp = requests.post(
            BUFFER_API,
            headers=_headers(token),
            json={"query": CREATE_POST_MUTATION, "variables": variables},
        )
        resp.raise_for_status()
        data = resp.json()

        result = data.get("data", {}).get("createPost", {})

        if "post" in result:
            print(f"[buffer] {ch['name']} — posted! (id: {result['post']['id']})")
            successes += 1
        elif "message" in result:
            print(f"[buffer] {ch['name']} — {result['message']}")
        else:
            print(f"[buffer] {ch['name']} — unexpected response: {result}")

    print(f"\n[buffer] Done! {successes}/{len(channels)} posted successfully.")
    return successes


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        schedule_post(
            video_path=sys.argv[1],
            caption="Becoming a trained partner starts with one decision. Are you making it? Book a free call — link in bio.",
            hashtags="#RelationshipCoach #CouplesCoaching #MensCoaching #BecomingATrainedPartner #TravisDixon",
            scheduled_at=datetime.utcnow(),
        )
