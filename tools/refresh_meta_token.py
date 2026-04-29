"""
refresh_meta_token.py
Exchange a short-lived FB User token for a long-lived Page Access Token,
verify it can publish to the configured IG + FB Page, and (optionally)
write the result back to .env.

Usage:
  python tools/refresh_meta_token.py <SHORT_LIVED_USER_TOKEN>          # dry-run, prints token
  python tools/refresh_meta_token.py <SHORT_LIVED_USER_TOKEN> --write  # also updates .env
"""

import os
import sys
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
APP_ID = os.getenv("META_APP_ID")
APP_SECRET = os.getenv("META_APP_SECRET")
FB_PAGE_ID = os.getenv("META_FB_PAGE_ID")
IG_USER_ID = os.getenv("META_IG_USER_ID")
ENV_PATH = Path(__file__).parent.parent / ".env"

GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _check_env():
    missing = [k for k, v in {
        "META_APP_ID": APP_ID,
        "META_APP_SECRET": APP_SECRET,
        "META_FB_PAGE_ID": FB_PAGE_ID,
        "META_IG_USER_ID": IG_USER_ID,
    }.items() if not v]
    if missing:
        sys.exit(f"[refresh] Missing env vars: {', '.join(missing)}")


def exchange_for_long_lived_user_token(short_token: str) -> str:
    print("[refresh] Step 1/3: short-lived User token -> long-lived User token...")
    r = requests.get(f"{GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short_token,
    }, timeout=30)
    if not r.ok:
        sys.exit(f"[refresh] Exchange failed: {r.status_code} {r.text}")
    data = r.json()
    expires = data.get("expires_in", "unknown")
    print(f"[refresh]   long-lived User token acquired (expires_in={expires}s ~ {int(expires)//86400 if isinstance(expires, int) else '?'} days)")
    return data["access_token"]


def get_page_token(long_user_token: str) -> str:
    print("[refresh] Step 2/3: fetching Page Access Token from /me/accounts...")
    r = requests.get(f"{GRAPH}/me/accounts", params={
        "access_token": long_user_token,
        "fields": "id,name,access_token",
        "limit": 100,
    }, timeout=30)
    if not r.ok:
        sys.exit(f"[refresh] /me/accounts failed: {r.status_code} {r.text}")
    pages = r.json().get("data", [])
    if not pages:
        sys.exit("[refresh] No pages returned. The User token must be for an admin of the Page.")
    match = next((p for p in pages if p["id"] == FB_PAGE_ID), None)
    if not match:
        listing = "\n  ".join(f"{p['id']} — {p['name']}" for p in pages)
        sys.exit(f"[refresh] Page {FB_PAGE_ID} not in returned pages. Found:\n  {listing}")
    print(f"[refresh]   matched page: {match['name']} ({match['id']})")
    return match["access_token"]


def verify_page_token(page_token: str) -> None:
    print("[refresh] Step 3/3: verifying token can reach Page + IG account...")
    r = requests.get(f"{GRAPH}/{FB_PAGE_ID}", params={
        "access_token": page_token,
        "fields": "id,name,instagram_business_account",
    }, timeout=30)
    if not r.ok:
        sys.exit(f"[refresh] Page verify failed: {r.status_code} {r.text}")
    data = r.json()
    ig = data.get("instagram_business_account", {}).get("id")
    print(f"[refresh]   page OK: {data.get('name')} ({data.get('id')})")
    if not ig:
        sys.exit("[refresh] Page has no linked instagram_business_account — check FB Business settings.")
    if ig != IG_USER_ID:
        print(f"[refresh]   WARNING: linked IG id {ig} != META_IG_USER_ID {IG_USER_ID} — update .env if intentional.")
    else:
        print(f"[refresh]   IG link OK: {ig}")


def write_to_env(page_token: str) -> None:
    text = ENV_PATH.read_text(encoding="utf-8")
    new_line = f"META_PAGE_ACCESS_TOKEN={page_token}"
    if re.search(r"^META_PAGE_ACCESS_TOKEN=.*$", text, flags=re.MULTILINE):
        text = re.sub(r"^META_PAGE_ACCESS_TOKEN=.*$", new_line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip() + "\n" + new_line + "\n"
    ENV_PATH.write_text(text, encoding="utf-8")
    print(f"[refresh] .env updated: META_PAGE_ACCESS_TOKEN")


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python tools/refresh_meta_token.py <SHORT_LIVED_USER_TOKEN> [--write]")
    short_token = sys.argv[1]
    write = "--write" in sys.argv

    _check_env()
    long_user = exchange_for_long_lived_user_token(short_token)
    page_token = get_page_token(long_user)
    verify_page_token(page_token)

    print("\n[refresh] New Page Access Token:")
    print(page_token)
    if write:
        write_to_env(page_token)
    else:
        print("\n[refresh] (dry-run; pass --write to update .env)")


if __name__ == "__main__":
    main()
