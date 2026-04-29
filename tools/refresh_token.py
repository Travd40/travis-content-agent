"""
refresh_token.py
Check the current Meta Page Access Token, or extend it to a 60-day version.

Usage:
    python tools/refresh_token.py              # Check current token status
    python tools/refresh_token.py --extend     # Exchange to 60-day long-lived

To extend, these must be in .env:
    META_APP_ID=1477854793939766
    META_APP_SECRET=<from Meta dashboard → App Settings → Basic → "Show">

And your fresh SHORT-LIVED USER TOKEN (not page token) must be saved to:
    .meta_token.txt  (in project root)

Fresh user token comes from Graph API Explorer → Get User Access Token.
"""

import os
import re
import sys
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
TOKEN_FILE = PROJECT_ROOT / ".meta_token.txt"


def _clean(raw: str) -> str:
    """Extract first valid-looking token from messy input."""
    raw = raw.strip()
    first = raw.find("EAA")
    if first < 0:
        return raw
    rest = raw[first + 3:]
    second = rest.find("EAA")
    candidate = raw[first : first + 3 + second] if second >= 0 else raw[first:]
    m = re.match(r"(EAA[A-Za-z0-9]+)", candidate)
    return m.group(1) if m else candidate


def _redact(text: str, *tokens: str) -> str:
    for t in tokens:
        if t:
            text = text.replace(t, "<TOKEN>")
    return text


def check_token() -> dict | None:
    """Debug the current META_PAGE_ACCESS_TOKEN — print validity + expiry."""
    token = os.getenv("META_PAGE_ACCESS_TOKEN")
    if not token:
        print("[check] No META_PAGE_ACCESS_TOKEN in .env — nothing to check.")
        return None

    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")
    # App access token is best for debug; fall back to debugging token with itself.
    access = f"{app_id}|{app_secret}" if (app_id and app_secret) else token

    resp = requests.get(
        f"{GRAPH}/debug_token",
        params={"input_token": token, "access_token": access},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"[check] debug_token failed: {resp.status_code} {_redact(resp.text, token)}")
        return None

    data = resp.json().get("data", {})
    is_valid = data.get("is_valid", False)
    expires = data.get("expires_at", 0)
    scopes = data.get("scopes", [])
    t_type = data.get("type", "unknown")

    if not is_valid:
        print(f"[check] Token is INVALID. Reason: {data.get('error', {}).get('message', 'unknown')}")
        print(f"[check] Fix: regenerate in Graph API Explorer and re-run tools/meta_setup.py")
        return data

    if expires == 0:
        age_str = "never expires (long-lived)"
    else:
        dt = datetime.fromtimestamp(expires)
        delta = dt - datetime.now()
        hours = delta.total_seconds() / 3600
        if hours < 0:
            age_str = f"EXPIRED {abs(hours):.1f} hours ago at {dt}"
        elif hours < 24:
            age_str = f"expires in {hours:.1f} hours ({dt})"
        else:
            age_str = f"expires in {hours/24:.1f} days ({dt})"

    print(f"[check] Type    : {t_type}")
    print(f"[check] Valid   : {is_valid}")
    print(f"[check] Expiry  : {age_str}")
    print(f"[check] Scopes  : {', '.join(scopes) if scopes else '(none shown)'}")

    return data


def extend_token() -> bool:
    """Exchange fresh short-lived user token → long-lived user → long-lived page token."""
    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")

    if not app_id or not app_secret:
        print("[extend] Missing META_APP_ID or META_APP_SECRET in .env")
        print()
        print("To get your App Secret:")
        print(f"  1. Open: https://developers.facebook.com/apps/{app_id or '1477854793939766'}/settings/basic/")
        print("  2. Scroll to 'App Secret' → click 'Show' → copy")
        print("  3. Add this line to .env (don't paste it in chat):")
        print("     META_APP_SECRET=<the value>")
        print("  4. Re-run this script.")
        return False

    if not TOKEN_FILE.exists():
        print(f"[extend] No {TOKEN_FILE} found.")
        print()
        print("Save a fresh USER access token (NOT page token) to that file:")
        print("  1. Open Graph API Explorer")
        print("  2. 'Get User Access Token' with your usual permissions")
        print("  3. Copy the token from the 'Access Token' field")
        print("  4. Save to .meta_token.txt in the project root")
        print("  5. Re-run this script")
        return False

    raw = TOKEN_FILE.read_text(encoding="utf-8")
    user_token = _clean(raw)
    if not user_token.startswith("EAA"):
        print(f"[extend] Couldn't find a valid token in {TOKEN_FILE.name}")
        return False

    print(f"[extend] Exchanging short-lived user token → long-lived user token...")
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": user_token,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"[extend] Exchange failed: {resp.status_code}")
        print(f"         {_redact(resp.text, user_token, app_secret)}")
        return False

    long_user = resp.json().get("access_token")
    if not long_user:
        print("[extend] Exchange returned no access_token")
        return False

    print(f"[extend] Got long-lived user token.")

    print(f"[extend] Fetching long-lived page token from /me/accounts...")
    pages = requests.get(
        f"{GRAPH}/me/accounts",
        params={"access_token": long_user, "fields": "id,name,access_token"},
        timeout=30,
    )
    if pages.status_code != 200:
        print(f"[extend] /me/accounts failed: {pages.status_code}")
        print(f"         {_redact(pages.text, long_user, user_token)}")
        return False

    data = pages.json().get("data", [])
    if not data:
        print("[extend] No pages on this account.")
        return False

    # Pick the Page matching META_FB_PAGE_ID, or first if not set
    target_id = os.getenv("META_FB_PAGE_ID")
    page = next((p for p in data if p.get("id") == target_id), data[0])
    page_token = page["access_token"]
    page_id = page["id"]
    page_name = page.get("name", "?")

    _update_env({
        "META_PAGE_ACCESS_TOKEN": page_token,
        "META_FB_PAGE_ID": page_id,
    })

    print(f"[extend] Page: {page_name} (id: {page_id})")
    print(f"[extend] .env updated with long-lived Page token.")

    try:
        TOKEN_FILE.unlink()
        print(f"[extend] Removed {TOKEN_FILE.name}.")
    except Exception:
        pass

    # Re-check expiry so user sees the win
    print()
    load_dotenv(override=True)
    check_token()
    return True


def _update_env(updates: dict):
    existing = {}
    order = []
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                k = k.strip()
                if k not in existing:
                    order.append(k)
                existing[k] = v
    for k, v in updates.items():
        if k not in existing:
            order.append(k)
        existing[k] = v
    lines = [f"{k}={existing[k]}" for k in order]
    ENV_PATH.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    if "--extend" in sys.argv:
        ok = extend_token()
        sys.exit(0 if ok else 1)
    else:
        check_token()
        print()
        print("To extend to a 60-day Page token, run:")
        print("  python tools/refresh_token.py --extend")
