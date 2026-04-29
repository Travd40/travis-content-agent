"""
save_token.py
Creates .meta_token.txt in the project root and opens it in Notepad for you.
No Save-As dialog, no extension-doubling, no "All Files" dropdown gotcha.

Workflow:
    1. Run this script.
    2. Notepad opens an empty .meta_token.txt.
    3. Paste your token (Ctrl+V), press Ctrl+S to save, close Notepad.
    4. Script checks what you saved and tells you if it looks right.
    5. Run: python tools/refresh_token.py --extend

Usage: python tools/save_token.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TOKEN_FILE = PROJECT_ROOT / ".meta_token.txt"


def main():
    # Create the file if missing — filename is already correct, so
    # user just does Ctrl+S in Notepad (no Save-As dialog at all)
    created = not TOKEN_FILE.exists()
    if created:
        TOKEN_FILE.write_text("", encoding="utf-8")
        print(f"[save] Created empty file: {TOKEN_FILE}")
    else:
        print(f"[save] Opening existing file: {TOKEN_FILE}")

    print(f"[save] Opening in Notepad...")
    print(f"[save] Instructions:")
    print(f"         1. Paste your token (Ctrl+V) — ONCE")
    print(f"         2. Press Ctrl+S to save")
    print(f"         3. Close Notepad")
    print(f"[save] Waiting for you to close Notepad...")
    print()

    try:
        subprocess.run(["notepad.exe", str(TOKEN_FILE)], check=False)
    except FileNotFoundError:
        print("[save] Couldn't find notepad.exe. Open the file manually:")
        print(f"       {TOKEN_FILE}")
        print("       Paste the token, save, close, then run refresh_token.py --extend")
        sys.exit(1)

    # After Notepad closes, inspect the file
    if not TOKEN_FILE.exists():
        print("[save] File disappeared. Something went wrong — try again.")
        sys.exit(1)

    content = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not content:
        print("[save] File is empty — did you paste and press Ctrl+S?")
        print("[save] Re-run this script and try again.")
        sys.exit(1)

    # Sanity checks (without ever printing the token)
    print(f"[save] File saved: {len(content)} chars.")

    if not content.startswith("EAA"):
        print(f"[save] WARNING: content doesn't start with 'EAA'.")
        print(f"[save] That's not a Meta Page/User token. Double-check you copied the right thing.")
        sys.exit(1)

    # Count EAA occurrences — more than 1 means accidental double-paste
    eaa_count = content.count("EAA")
    if eaa_count > 3:  # "EAA" can appear inside a valid token a few times legitimately
        print(f"[save] NOTE: 'EAA' appears {eaa_count} times — token may be pasted multiple times.")
        print(f"[save] That's OK — refresh_token.py will auto-extract the first valid token.")

    print()
    print(f"[save] Looks good. Next step:")
    print(f"[save]   python tools/refresh_token.py --extend")
    print(f"[save] (first make sure META_APP_SECRET is in your .env)")


if __name__ == "__main__":
    main()
