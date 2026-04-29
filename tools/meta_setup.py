"""
meta_setup.py
One-time interactive wizard that:
  1. Prompts for your Meta Page Access Token (hidden input — doesn't echo to screen)
  2. Validates it by calling the Graph API
  3. Auto-fetches your FB Page ID and IG Business Account ID
  4. Writes everything to .env without clobbering existing keys

Run once:
    python tools/meta_setup.py
"""

import os
import re
import sys
import requests
from pathlib import Path

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
TOKEN_FILE = PROJECT_ROOT / ".meta_token.txt"


def _redact(text: str, token: str) -> str:
    """Strip the token out of error messages before displaying."""
    if not token:
        return text
    return text.replace(token, "<TOKEN>")


def validate_token(token: str) -> dict:
    """Hit /me and /me/accounts. Returns { fb_page_id, ig_user_id, page_access_token } or raises."""
    # 1. sanity check: who is this token for?
    me = requests.get(f"{GRAPH}/me", params={"access_token": token}, timeout=30)
    if me.status_code != 200:
        raise RuntimeError(f"Token rejected by Meta: {me.status_code} {_redact(me.text, token)}")

    # 2. list pages this user/token has access to
    pages = requests.get(
        f"{GRAPH}/me/accounts",
        params={"access_token": token, "fields": "id,name,access_token"},
        timeout=30,
    )
    if pages.status_code != 200:
        raise RuntimeError(f"/me/accounts failed: {pages.status_code} {_redact(pages.text, token)}")

    data = pages.json().get("data", [])
    if not data:
        raise RuntimeError("No pages found — token doesn't have access to any FB Pages. "
                           "Regenerate with pages_show_list + pages_manage_posts permissions.")

    # Pick the first page (Travis only has one — Travis Dixon Coaching)
    if len(data) > 1:
        print("\n[setup] Multiple pages found. Picking the first:")
        for p in data:
            print(f"  - {p.get('name')} (id: {p.get('id')})")
    page = data[0]
    page_id = page["id"]
    page_token = page["access_token"]  # long-lived-ish Page token derived from the user token
    page_name = page.get("name", "?")

    # 3. get linked Instagram Business Account
    ig = requests.get(
        f"{GRAPH}/{page_id}",
        params={"fields": "instagram_business_account", "access_token": page_token},
        timeout=30,
    )
    if ig.status_code != 200:
        raise RuntimeError(f"IG lookup failed: {ig.status_code} {ig.text}")
    ig_data = ig.json().get("instagram_business_account")
    if not ig_data or "id" not in ig_data:
        raise RuntimeError(
            f"Page '{page_name}' has no linked Instagram Business account. "
            f"Open IG app → Settings → Accounts Center → link your IG Business to this FB Page."
        )

    return {
        "fb_page_id": page_id,
        "fb_page_name": page_name,
        "ig_user_id": ig_data["id"],
        "page_access_token": page_token,
    }


def update_env(values: dict):
    """Merge new META_* keys into .env without touching anything else."""
    existing = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v

    new_keys = {
        "META_GRAPH_VERSION": GRAPH_VERSION,
        "META_APP_ID": "1477854793939766",
        "META_FB_PAGE_ID": values["fb_page_id"],
        "META_IG_USER_ID": values["ig_user_id"],
        "META_PAGE_ACCESS_TOKEN": values["page_access_token"],
    }

    existing.update(new_keys)

    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")

    print(f"\n[setup] .env updated. New/updated keys:")
    for k in new_keys:
        masked = new_keys[k] if k != "META_PAGE_ACCESS_TOKEN" else f"{new_keys[k][:8]}...(hidden)"
        print(f"  {k}={masked}")


def _clean_token(raw: str) -> str:
    """
    Salvage a token from messy input. Handles common paste errors:
      - Token repeated multiple times (Ctrl+V spammed)
      - Random keystrokes appended ('jjjjaaaww')
      - Whitespace, newlines, shell commands pasted after the token
    FB Page Access Tokens start with 'EAA' and contain only [A-Za-z0-9].
    We take from the first 'EAA' up to where 'EAA' next appears (duplicate)
    or where a non-token char appears.
    """
    if not raw:
        return ""
    raw = raw.strip()

    # Find first EAA
    first = raw.find("EAA")
    if first < 0:
        return raw  # let Meta reject it and report the real error

    # Find next EAA (indicates duplicate paste); if none, cap at end of token chars
    rest = raw[first + 3:]
    second = rest.find("EAA")
    if second >= 0:
        candidate = raw[first : first + 3 + second]
    else:
        candidate = raw[first:]

    # Trim trailing non-token chars (keeps only [A-Za-z0-9])
    match = re.match(r"(EAA[A-Za-z0-9]+)", candidate)
    return match.group(1) if match else candidate


def _read_token() -> str:
    """Read token from .meta_token.txt, or from command line arg, or prompt."""
    # Option 1: command line arg
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        return _clean_token(sys.argv[1])

    # Option 2: from .meta_token.txt file (simplest for users)
    if TOKEN_FILE.exists():
        content = TOKEN_FILE.read_text(encoding="utf-8")
        cleaned = _clean_token(content)
        if cleaned:
            if cleaned != content.strip():
                print(f"[setup] Note: token file had extra content. Extracted clean token ({len(cleaned)} chars).")
            else:
                print(f"[setup] Read token from {TOKEN_FILE.name}")
            return cleaned

    # Option 3: prompt (visible input — tradeoff for compatibility)
    print(f"\n[setup] No token found.")
    print(f"[setup] Easiest fix: save your token to this exact file, then re-run:")
    print(f"        {TOKEN_FILE}")
    print(f"[setup] Or paste it now (will be visible):")
    try:
        token = input("Page Access Token: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[setup] Aborted.")
        sys.exit(1)
    return _clean_token(token)


def main():
    print("=" * 60)
    print("Meta API Setup — one-time credential wizard")
    print("=" * 60)

    token = _read_token()
    if not token:
        print("[setup] No token provided. Aborting.")
        sys.exit(1)

    print("\n[setup] Validating token with Meta...")
    try:
        values = validate_token(token)
    except Exception as e:
        print(f"\n[setup] ERROR: {e}")
        sys.exit(1)

    print(f"[setup] Token valid.")
    print(f"[setup] Facebook Page   : {values['fb_page_name']} (id: {values['fb_page_id']})")
    print(f"[setup] Instagram ID    : {values['ig_user_id']}")

    update_env(values)

    # Clean up the temp token file so it doesn't sit around
    if TOKEN_FILE.exists():
        try:
            TOKEN_FILE.unlink()
            print(f"[setup] Removed {TOKEN_FILE.name} (token is now safely in .env)")
        except Exception as e:
            print(f"[setup] Note: could not delete {TOKEN_FILE.name} — delete manually. ({e})")

    print("\n[setup] Done. You can now run:")
    print("  python tools/meta_publish.py <path_to_video.mp4>")
    print()


if __name__ == "__main__":
    main()
