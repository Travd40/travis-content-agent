"""
check_token.py — diagnostic only. Read-only. Posts nothing.

Reports what the META_PAGE_ACCESS_TOKEN env var actually contains:
who it belongs to, what scopes it has, whether it's still valid, and
whether it has the FB video-publish permission. Use to compare local
.env vs GitHub Actions secret when posting fails.
"""
import os
import sys
import hashlib
import requests
from pathlib import Path

# When run locally, load .env. In GH Actions the env vars come from secrets.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except Exception:
    pass

GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
TOKEN = (os.getenv("META_PAGE_ACCESS_TOKEN") or "").strip()
PAGE_ID = (os.getenv("META_FB_PAGE_ID") or "").strip()
APP_ID = (os.getenv("META_APP_ID") or "").strip()
APP_SECRET = (os.getenv("META_APP_SECRET") or "").strip()

if not TOKEN:
    print("FAIL: META_PAGE_ACCESS_TOKEN is empty.")
    sys.exit(1)

# A token fingerprint we can safely log to compare local vs GH without
# revealing the actual token. First 8 chars of SHA-256.
fp = hashlib.sha256(TOKEN.encode()).hexdigest()[:8]
print(f"Token length      : {len(TOKEN)}")
print(f"Token fingerprint : {fp}  <-- compare local vs GH; same fp = same token")
print(f"Token first 4     : {TOKEN[:4]}")
print(f"Token last 4      : {TOKEN[-4:]}")

print("\n--- /me ---")
me = requests.get(f"{GRAPH}/me", params={"access_token": TOKEN, "fields": "id,name,category"}).json()
print(me)

print("\n--- /debug_token ---")
if APP_ID and APP_SECRET:
    dbg = requests.get(f"{GRAPH}/debug_token", params={
        "input_token": TOKEN,
        "access_token": f"{APP_ID}|{APP_SECRET}",
    }).json()
    d = dbg.get("data", {})
    print(f"  type       : {d.get('type')}")
    print(f"  app_id     : {d.get('app_id')}")
    print(f"  is_valid   : {d.get('is_valid')}")
    print(f"  expires_at : {d.get('expires_at')} (0 = never)")
    print(f"  scopes     : {d.get('scopes')}")
    if "pages_manage_posts" in (d.get("scopes") or []):
        print("  pages_manage_posts: PRESENT")
    else:
        print("  pages_manage_posts: *** MISSING — this is why FB video publish fails ***")
    if d.get("error"):
        print(f"  ERROR      : {d['error']}")
else:
    print("  (skipping — META_APP_ID or META_APP_SECRET not set)")

print("\nDone. No posts created.")
