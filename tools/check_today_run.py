"""Check today's daily-post workflow run status + grab the FB error line if any."""
import io, os, sys, zipfile, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
GH = (os.getenv("GITHUB_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {GH}", "Accept": "application/vnd.github+json"}
REPO = "Travd40/travis-content-agent"

runs = requests.get(
    f"https://api.github.com/repos/{REPO}/actions/workflows/post-daily.yml/runs",
    headers=H, params={"per_page": 3},
).json()

for r in runs.get("workflow_runs", [])[:3]:
    print(f"{r['created_at']}  {r['status']:10}  {r['conclusion']}  ({r['event']})")
    print(f"  {r['html_url']}")

# Pull logs of the latest run
if runs.get("workflow_runs"):
    rid = runs["workflow_runs"][0]["id"]
    resp = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs/{rid}/logs",
                        headers=H, allow_redirects=True)
    if resp.status_code == 200:
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        for n in zf.namelist():
            if n.endswith("_post.txt"):
                raw = zf.read(n).decode("utf-8", errors="replace")
                lines = raw.splitlines()
                # Print last 40 lines + any line mentioning FB / facebook / error
                print("\n--- last 40 lines of run log ---")
                for line in lines[-40:]:
                    if len(line) > 30 and line[4] == "-" and line[10] == "T":
                        line = line[29:]
                    print(line)
                break
    else:
        print(f"\nLog fetch failed: {resp.status_code}")
