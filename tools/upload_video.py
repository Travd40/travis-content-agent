"""
upload_video.py
Uploads a video file to GitHub (Travd40/content-videos repo) and returns a public URL.
Buffer needs a hosted URL to attach video to TikTok posts.
"""

import os
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

REPO = "Travd40/content-videos"
BRANCH = "main"


def upload_video(video_path: str) -> str:
    """
    Uploads a video to GitHub and returns the public download URL.

    Args:
        video_path: Local path to the .mp4 file

    Returns:
        Public URL (raw.githubusercontent.com) for the video
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set in .env")

    video_file = Path(video_path)
    if not video_file.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    filename = video_file.name
    api_url = f"https://api.github.com/repos/{REPO}/contents/videos/{filename}"

    print(f"[upload] Reading {filename} ({video_file.stat().st_size // 1024}KB)...")
    with open(video_file, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    # Check if file already exists (need sha to update)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    existing = requests.get(api_url, headers=headers)
    payload = {"message": f"Upload {filename}", "content": content, "branch": BRANCH}
    if existing.status_code == 200:
        payload["sha"] = existing.json()["sha"]

    print(f"[upload] Uploading to GitHub ({REPO})...")
    resp = requests.put(api_url, headers=headers, json=payload)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"GitHub upload failed: {resp.json().get('message', resp.text[:200])}")

    download_url = resp.json()["content"]["download_url"]
    print(f"[upload] Done: {download_url}")
    return download_url


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        url = upload_video(sys.argv[1])
        print(f"URL: {url}")
    else:
        print("Usage: python upload_video.py <path_to_video.mp4>")
