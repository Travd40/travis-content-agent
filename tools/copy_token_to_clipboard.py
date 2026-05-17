"""
copy_token_to_clipboard.py — copies META_PAGE_ACCESS_TOKEN from .env
straight to your Windows clipboard, ready to paste into GitHub Secrets.

Prints the fingerprint so you can confirm it matches what we expect.
Never prints the actual token.
"""
import os
import sys
import hashlib
import subprocess
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env", override=True)

token = (os.getenv("META_PAGE_ACCESS_TOKEN") or "").strip()
if not token:
    print("FAIL: META_PAGE_ACCESS_TOKEN is empty in .env")
    sys.exit(1)

# Copy to clipboard via Windows `clip`
proc = subprocess.run(["clip"], input=token.encode("utf-16le"), shell=True)
if proc.returncode != 0:
    print(f"FAIL: couldn't reach clipboard (clip.exe returned {proc.returncode})")
    sys.exit(1)

fp = hashlib.sha256(token.encode()).hexdigest()[:8]
print("Token copied to clipboard.")
print(f"  length      : {len(token)}")
print(f"  fingerprint : {fp}  <-- this should appear in the GH workflow log next time")
print(f"  first 4     : {token[:4]}")
print(f"  last 4      : {token[-4:]}")
print()
print("Now go to:")
print("  https://github.com/Travd40/travis-content-agent/settings/secrets/actions")
print("Click Update next to META_PAGE_ACCESS_TOKEN, paste with Ctrl+V, click Update secret.")
