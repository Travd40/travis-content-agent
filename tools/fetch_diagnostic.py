"""
fetch_diagnostic.py — pull the latest check-token workflow run output
from GitHub directly, plus run the same check locally. Prints both
side by side so we can compare local .env vs GH secret.
"""
import io
import os
import sys
import zipfile
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env", override=True)

REPO = "Travd40/travis-content-agent"
WORKFLOW_FILE = "check-token.yml"
GH_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()

if not GH_TOKEN:
    print("FAIL: GITHUB_TOKEN not in .env"); sys.exit(1)

H = {"Authorization": f"Bearer {GH_TOKEN}",
     "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2022-11-28"}

print("=" * 70)
print("PART 1 — what the GitHub Actions secret shows")
print("=" * 70)

# 1. Find the most recent run of check-token.yml
runs = requests.get(
    f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/runs",
    headers=H, params={"per_page": 1},
).json()

if not runs.get("workflow_runs"):
    print("No runs found for check-token.yml."); sys.exit(1)

run = runs["workflow_runs"][0]
run_id = run["id"]
print(f"Run ID    : {run_id}")
print(f"Status    : {run['status']}  ({run['conclusion']})")
print(f"Created   : {run['created_at']}")
print(f"URL       : {run['html_url']}")

# 2. Download the full log zip
print("\nDownloading logs...")
log_resp = requests.get(
    f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/logs",
    headers=H, allow_redirects=True,
)

if log_resp.status_code != 200:
    print(f"FAIL: couldn't fetch logs: {log_resp.status_code} {log_resp.text}")
    sys.exit(1)

# 3. Extract the Inspect token step output from the combined job log
zf = zipfile.ZipFile(io.BytesIO(log_resp.content))
job_log_name = next((n for n in zf.namelist() if n.endswith("_check.txt")), None)
if not job_log_name:
    print("Couldn't find check job log. Available files:")
    for name in zf.namelist():
        print(f"  {name}")
    sys.exit(1)

raw = zf.read(job_log_name).decode("utf-8", errors="replace")

# GH prefixes every line with an ISO timestamp + space. Strip it.
def strip_ts(line: str) -> str:
    if len(line) > 30 and line[4] == "-" and line[10] == "T":
        return line[29:] if len(line) > 29 else line
    return line

lines = [strip_ts(l) for l in raw.splitlines()]
text = "\n".join(lines)

# Find the section starting at "Token length" (the first line check_token.py prints)
start = text.find("Token length")
end = text.find("Done. No posts created.")
if start == -1:
    print("Couldn't find diagnostic output in log. Full log was:")
    print(text[-3000:])
    sys.exit(1)

if end != -1:
    end += len("Done. No posts created.")
    print(text[start:end])
else:
    print(text[start:start + 4000])

print("\n" + "=" * 70)
print("PART 2 — what your LOCAL .env shows (for comparison)")
print("=" * 70)
result = subprocess.run(
    [sys.executable, str(ROOT / "tools" / "check_token.py")],
    capture_output=True, text=True,
)
print(result.stdout)
if result.stderr:
    print("--- stderr ---")
    print(result.stderr)
